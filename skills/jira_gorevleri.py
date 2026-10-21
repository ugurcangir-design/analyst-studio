"""Jira Görevleri Skill — Epic/Story altındaki bir-seviye-alt görevleri çek,
'hazır / detay gerekir' olarak sınıflandır (yapısal + AI), ve iki manuel aksiyon:

  Özellik 1 — gorev_standart_formatla(): mevcut görevi agent'ın standart görev
              formatına (Amaç / Değişiklikler / Referans / Kabul Kriteri) çevirir.
  Özellik 2 — gorev_analiz_et(): teknik analiz motoruyla görevi detaylandırır.

Her iki çıktı da analist onayından sonra gorev_jiraya_yaz() ile Jira görevinin
description'ına (markdown→ADF) yazılır. Okuma/yazma canonical skills/atlassian.py
üzerinden; format jira_agent.markdown_to_adf ile (teknik analiz task'ı formatı).
"""

import json
import os
import re
import sys
from pathlib import Path

from .atlassian import env_oku, atlassian_post, atlassian_put
from .base import (
    _api_cagri, _xml_ayir, _metin_sikistir, asama_ayarla,
    prompt_yukle, extended_thinking_acik,
    referans_dosyalari_hazirla, _ref_bloklari_olustur, load_context_filter,
    canli_uygulama_baglami_hazirla,
    yonetici_ozeti_olustur, yonetici_ozetini_cikar, jira_icin_temizle,
    ai_ara_sozleri_temizle,
    MAX_TOKENS_KISA, MAX_TOKENS_COMBINED, MAX_TOKENS_UZUN,
)

# Hafif modelin tam kimliği — Standart Formatla için sonnet yerine kullanılır.
# CLAUDE.md ve jira_agent.py ile aynı haiku sürümü.
MODEL_HAFIF = "claude-haiku-4-5-20251001"

# ─── Meta-Not Temizleyici (Jira description'a sızmasın) ─────────────────────
# Modelin (her promptta yasakladığımız halde) bazen yazdığı içsel/yönlendirme
# notlarını çıktıdan siler. Yasak kalıplar:
#  - "> Not — 12. Karar Bekleyen Konular: ... AYRI bir adımda üretilir..."
#  - "Açık Sorular ayrı çıktıda detaylandırılmalıdır"
#  - "[K: ❓ Belirsiz] olarak işaretlenen maddeler ayrı çıktıda..."
_META_NOT_DESENLERI = [
    # Tüm satır: "> **Not — ...Karar Bekleyen Konular: ... AYRI bir adımda...**" türü
    re.compile(r"(?im)^\s*>?\s*\*?\*?Not[^\n]*(?:Karar Bekleyen Konular|Aç[ıi]k Sorular)[^\n]*ayr[ıi][^\n]*ad[ıi]mda[^\n]*\n?"),
    # "Açık Sorular ayrı çıktıda detaylandırılmalıdır" türü
    re.compile(r"(?im)^[^\n]*aç[ıi]k\s*sorular[^\n]*(ayr[ıi]\s*ç[ıi]kt[ıi]da|ayr[ıi]\s*dok[üu]mantasyonda)[^\n]*\n?"),
    # "[K: ❓ Belirsiz] olarak işaretlenen maddeler ayrı çıktıda..."
    re.compile(r"(?im)^[^\n]*\[K:\s*❓?\s*Belirsiz\][^\n]*ayr[ıi]\s*ç[ıi]kt[ıi]da[^\n]*\n?"),
]


def _meta_notlari_temizle(metin: str) -> str:
    """Üretilen markdown çıktısındaki içsel/yönlendirme notlarını siler.
    Bunlar promptta yasak olmasına rağmen bazen çıkıyor; Jira description'a
    gitmeden burada kesilir. Birden çok arka arkaya boş satır da sıkıştırılır.
    AI'ın süreç anlatımı ara sözleri ("Şimdi raporu yazıyorum." vb.) de temizlenir."""
    for desen in _META_NOT_DESENLERI:
        metin = desen.sub("", metin)
    metin = ai_ara_sozleri_temizle(metin)
    return re.sub(r"\n{3,}", "\n\n", metin).strip()

# markdown_to_adf — jira_agent.py'den (teknik analiz task'ı açarkenki format)
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from jira_agent import markdown_to_adf  # noqa: E402


# ─── Standart Görev Şablonu (Özellik 1 hedef formatı) ────────────────────────

STANDART_GOREV_SABLONU = """## Amaç
[1-2 cümle: ne geliştirilecek ve neden — iş gerekçesi]

## Değişiklikler
- [somut, madde madde değişiklikler]

## Referans / Yaklaşım
- [etkilenen ekran/dosyalar (örn. src/...), teknik yaklaşım, backend/i18n notu]

## Kabul Kriteri
- [test edilebilir, gözlemlenebilir kriterler]"""


# ─── Cloud ID ────────────────────────────────────────────────────────────────

def _cloud_id() -> str:
    cid = env_oku().get("JIRA_CLOUD_ID", "")
    if not cid:
        raise RuntimeError("Jira bağlı değil (JIRA_CLOUD_ID yok). Ayarlar'dan Jira'ya bağlanın.")
    return cid


# ─── ADF Okuma (description → düz metin) ─────────────────────────────────────

def _adf_to_text(node) -> str:
    """ADF description'ı okunabilir düz metne çevirir (kart görünümü +
    sınıflandırma/analiz girdisi). Başlıkları boş satırla ayırır, madde
    işaretlerini korur — yapıyı düzgün ayrıştırır."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    tip = node.get("type")
    if tip == "text":
        return node.get("text", "")
    if tip == "hardBreak":
        return "\n"
    icerik = "".join(_adf_to_text(c) for c in node.get("content", []) or [])
    if tip == "heading":
        # Başlık seviyesi korunur ('#' × level) → köprü düzelt/cevap gövdedeki analizi yeniden yazarken
        # bölüm yapısı (ve `_orijinal_talep_ayikla` marker'ları) bozulmaz.
        try:
            seviye = max(1, min(6, int((node.get("attrs") or {}).get("level") or 2)))
        except (TypeError, ValueError):
            seviye = 2
        return "\n" + "#" * seviye + " " + icerik.strip() + "\n"        # başlık öncesi boş satır
    if tip == "paragraph":
        return icerik + "\n"
    if tip == "listItem":
        return "• " + icerik.strip() + "\n"
    if tip in ("tableCell", "tableHeader"):
        return "| " + " ".join(icerik.split()) + " "
    if tip == "tableRow":
        return icerik.rstrip() + " |\n"
    if tip in ("bulletList", "orderedList"):
        return icerik + "\n"
    if tip == "table":
        return icerik + "\n"
    return icerik


# ─── Alt Görevleri Çek (bir seviye alt) ──────────────────────────────────────

_ID_DESENI = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")

# Bir bağlı task'ın BE/BFF (sunucu) tarafı olduğuna dair deterministik sinyaller.
# summary + issuetype üzerinde aranır; "sadece client" değerlendirmesinde AI'a
# ipucu olarak verilir (kesin karar AI'da, ama bu ön-tarama şeffaflık sağlar).
_BE_SINYAL_DESENI = re.compile(
    r"\b(be|backend|back-?end|bff|api|endpoint|servis|service|micro-?service|"
    r"veritaban[ıi]|database|db|migration|migrasyon|repository|entity|"
    r"consumer|producer|kafka|queue|job|scheduler|cron)\b",
    re.IGNORECASE,
)
_FE_SINYAL_DESENI = re.compile(
    r"\b(fe|frontend|front-?end|ui|ux|client|react|component|bile[şs]en|"
    r"ekran|screen|sayfa|page|css|style|stil|i18n|çeviri|translation)\b",
    re.IGNORECASE,
)


def _katman_tahmin(metin: str) -> str:
    """summary/type metninden kaba katman tahmini: 'be' | 'fe' | 'belirsiz'.
    Yalnızca ipucu — nihai kararı AI içerik incelemesiyle verir."""
    be = bool(_BE_SINYAL_DESENI.search(metin))
    fe = bool(_FE_SINYAL_DESENI.search(metin))
    if be and not fe:
        return "be"
    if fe and not be:
        return "fe"
    return "belirsiz"


# Hata/bug + basit-iş sinyalleri → çıktı KISA-NET tutulur (gereksiz servis/DB/öneri dökümü YOK).
_HATA_TIP_DESEN = re.compile(r"(bug|hata|sorun|defect|problem|ar[ıi]za)", re.IGNORECASE)
# Yalnız BUG İFADESİ sayılır ('çalışmıyor', 'hata alıyor', 'fix:'); çıplak 'hata'/'eksik'/'çalışm' DEĞİL —
# 'Hata mesajlarının gösterilmesi', 'Çalışma saatleri', 'Eksik alanların eklenmesi' özellik işidir (kısa moda düşmemeli).
_HATA_KELIME_DESEN = re.compile(
    r"(^\s*(?:hata|bug|fix|hotfix)\s*[:\-]|"                      # 'Hata: kayıt silinemiyor' / 'fix: …' başlık öneki
    r"çal[ıi][şs]m[ıi]yor|calismiyor|hata\s+(?:al[ıi]yor|al[ıi]n[ıi]yor|veriyor|d[öo]n[üu]yor|f[ıi]rlat[ıi]yor)|"
    r"\w{3,}[ae]m[ıi]yor\b|"                                        # silinemiyor / kaydedilemiyor / yapılamıyor
    r"a[çc][ıi]lm[ıi]yor|g[öo]r[üu]nm[üu]yor|patl[ıi]yor|k[ıi]r[ıi]k|bozuk|crash|broken|not\s+working|"
    r"\bbug\b|\bhotfix\b|takl[ıi]yor|donuyor|\bçöküyor|cokuyor|yanl[ıi]ş\s+(?:hesapl|g[öo]ster|çal[ıi][şs]))",
    re.IGNORECASE)


def _hata_gorev_mi(gorev: dict) -> bool:
    """Görev bir HATA/BUG ya da küçük düzeltme mi? issuetype veya başlık sinyaliyle.
    True → analiz çıktısı KISA-NET tutulur (bug modu). Yalnızca ipucu; içeriği AI değerlendirir."""
    tip = str(gorev.get("type") or gorev.get("issuetype") or "")
    baslik = (gorev.get("summary") or "")
    if _HATA_TIP_DESEN.search(tip):
        return True
    return bool(_HATA_KELIME_DESEN.search(baslik))


def _issuelink_ayikla(issuelinks: list) -> list[dict]:
    """Jira `issuelinks` alanını sade bağlı-task listesine çevirir.
    Her link'in in/out tarafındaki issue'yu, ilişki metnini ve kaba katman
    tahminini (be/fe/belirsiz) döndürür. Bozuk/eksik link sessizce atlanır."""
    sonuc = []
    for link in issuelinks or []:
        if not isinstance(link, dict):
            continue
        tip = link.get("type") or {}
        # Bir link ya inwardIssue ya outwardIssue taşır (biri dolu olur).
        if link.get("outwardIssue"):
            issue = link["outwardIssue"]
            iliski = tip.get("outward", "ilişkili")
        elif link.get("inwardIssue"):
            issue = link["inwardIssue"]
            iliski = tip.get("inward", "ilişkili")
        else:
            continue
        lf = issue.get("fields", {}) or {}
        summary = lf.get("summary", "")
        issuetype = (lf.get("issuetype") or {}).get("name", "")
        sonuc.append({
            "key": issue.get("key", ""),
            "summary": summary,
            "type": issuetype,
            "iliski": iliski,
            "durum": (lf.get("status") or {}).get("name", ""),
            "katman": _katman_tahmin(f"{summary} {issuetype}"),
        })
    return sonuc


_ISSUE_ALANLARI = ["summary", "description", "status", "issuetype", "priority",
                   "assignee", "parent", "comment", "issuelinks"]
# bulkfetch tek istekte en fazla 100 issue kabul eder (150 denendi → 400).
_BULKFETCH_LIMIT = 100


def _issue_ayrıstir(issue: dict) -> dict:
    """Ham Jira issue nesnesini uygulamanın görev sözlüğüne çevirir.
    Hem arama (search) hem doğrudan okuma (bulkfetch) sonuçları için ORTAK."""
    f = issue.get("fields", {}) or {}
    desc = f.get("description")
    desc_metin = _adf_to_text(desc) if isinstance(desc, dict) else (desc or "")
    # Comment'ler: ADF→metin + yazar/tarih (analist task detayında görsün)
    comments = []
    cdata = f.get("comment") or {}
    for c in (cdata.get("comments") if isinstance(cdata, dict) else cdata) or []:
        body_metin = _adf_to_text(c.get("body")) if isinstance(c.get("body"), dict) else (c.get("body") or "")
        yazar = (c.get("author") or {}).get("displayName", "")
        tarih = (c.get("created") or "")[:10]  # YYYY-MM-DD
        comments.append({"yazar": yazar, "tarih": tarih, "metin": body_metin.strip()})
    parent = f.get("parent") or {}
    return {
        "key": issue["key"],
        "summary": f.get("summary", ""),
        "status": (f.get("status") or {}).get("name", ""),
        "type": (f.get("issuetype") or {}).get("name", ""),
        "priority": (f.get("priority") or {}).get("name", ""),
        "assignee": (f.get("assignee") or {}).get("displayName", ""),
        # Üst kayıt (Story/Epic altındaki iş kalemleri için köprü/transitif eşleşmede kullanılır)
        "parent_key": parent.get("key", ""),
        "parent_type": ((parent.get("fields") or {}).get("issuetype") or {}).get("name", ""),
        "description": desc_metin.strip(),
        "comments": comments,
        # Bağlı task'lar (FE/BE ayrımı için kritik): her issue-link'in
        # in/out tarafındaki issue + tipi + ilişki. "Sadece client"
        # değerlendirmesi bir task'ın BAĞLI BE task'ını dikkate almalı.
        "baglantililar": _issuelink_ayikla(f.get("issuelinks") or []),
    }


# KAPSAYICI tipler: girilen anahtar bunlardan biriyse listede KENDİSİ gösterilmez
# (analist altındaki/bağlı görevleri ister). Görev/Bug gibi yaprak iş kalemlerinde
# ise analistin asıl incelemek istediği şey o task'ın KENDİSİdir → listeye eklenir.
# NOT: Jira'da Story ve Task AYNI hierarchyLevel'a (0) sahiptir — gerçek Jira'da
# doğrulandı (Hikaye=0, Görev=0). Bu yüzden ayrım tip ADIna göre yapılır;
# hierarchyLevel >= 1 (Epic ve üstü) her hâlükârda kapsayıcı sayılır.
_KAPSAYICI_TIP_ADLARI = {
    "epic", "epik", "story", "hikaye", "initiative", "girişim", "girisim",
}


def _iptal_statusu_mu(status: str) -> bool:
    """Durum 'iptal edilmiş' anlamına mı geliyor? Türkçe (İptal Edildi / İPTAL
    EDİLDİ / İptal) ve İngilizce (Cancelled / Canceled) varyantları yakalar.
    upper() kullanılır — casefold Türkçe 'İ'de birleşik noktalı harf üretip
    substring aramasını bozabiliyor."""
    u = (status or "").upper()
    return "İPTAL" in u or "IPTAL" in u or "CANCEL" in u


def iptal_ayikla(gorevler: list[dict]) -> tuple[list[dict], int]:
    """İptal edilmiş görevleri listeden çıkarır. (kalan_liste, çıkarılan_sayı) döndürür.
    Bağlı task'lar (baglantililar) DOKUNULMAZ — yalnızca üst-düzey görev kartları elenir."""
    kalan = [g for g in gorevler if not _iptal_statusu_mu(g.get("status", ""))]
    return kalan, len(gorevler) - len(kalan)


def _kapsayici_mi(issuetype: dict | None) -> bool:
    """Issue tipi 'kapsayıcı' mı (Epic/Story) yoksa yaprak iş kalemi mi (Görev/Bug)?"""
    it = issuetype or {}
    try:
        if int(it.get("hierarchyLevel", 0)) >= 1:
            return True
    except (TypeError, ValueError):
        pass
    return str(it.get("name", "")).strip().lower() in _KAPSAYICI_TIP_ADLARI


def gorev_getir(key: str) -> dict | None:
    """Tek bir Jira görevini TAM (açıklama + bağlantılar dahil) görev sözlüğü olarak getirir.
    İlişkili FE/BE analizinde, listede yüklü olmayan bağlı task'ları çekmek için."""
    ham = _tek_issue_ham(key, _cloud_id())
    return _issue_ayrıstir(ham) if ham else None


def _http_durum(e: BaseException) -> int | None:
    """Hatadan HTTP durum kodunu çıkarır (requests.HTTPError.response ya da mesajdaki 'API 401'/'400 Client Error')."""
    r = getattr(e, "response", None)
    kod = getattr(r, "status_code", None)
    if isinstance(kod, int):
        return kod
    m = re.search(r"\b([45]\d\d)\b", str(e))
    return int(m.group(1)) if m else None


def _tek_issue_ham(key: str, cloud_id: str) -> dict | None:
    """Tek issue'yu HAM olarak doğrudan okur (tip kontrolü + ayrıştırma için).
    Bulunamazsa (404 / 400 geçersiz anahtar) None. Yetki (401/403) ve ağ hataları YÜKSELTİLİR —
    eskiden yutulup 'bulunamadı' sanılıyordu (analist yetki sorununu göremiyordu)."""
    try:
        data = atlassian_post(
            "/rest/api/3/issue/bulkfetch",
            body={"issueIdsOrKeys": [key], "fields": _ISSUE_ALANLARI},
            cloud_id=cloud_id,
        )
    except Exception as e:
        if _http_durum(e) in (400, 404):
            print(f"  ⚠ '{key}' bulunamadı: {e}")
            return None
        raise RuntimeError(f"'{key}' okunamadı (yetki/ağ): {str(e)[:200]}") from e
    for issue in data.get("issues", []) or []:
        if issue.get("key") == key:
            return issue
    return None


def _taze_issue_oku(keys: list[str], cloud_id: str) -> dict[str, dict]:
    """Verilen anahtarların GÜNCEL içeriğini doğrudan okur → {key: görev}.

    NEDEN GEREKLİ: `/rest/api/3/search/jql` sonuçları arama İNDEKSİNDEN gelir ve
    indeks eventually-consistent'tır — Atlassian dokümanı: "Recent updates might
    not be immediately visible in the returned search results." Jira'da bir task'ın
    başlığı/açıklaması güncellendikten sonra arama ESKİ değeri döndürebiliyordu;
    analist görevleri yeniden çekince güncellemeyi göremiyordu. `issue/bulkfetch`
    indeksten değil doğrudan issue'dan okur → her zaman güncel.

    Hata durumunda (yetki/endpoint yok) boş dict döner; çağıran arama sonucuna
    düşer (bayat olabilir ama akış kırılmaz)."""
    taze: dict[str, dict] = {}
    for i in range(0, len(keys), _BULKFETCH_LIMIT):
        parca = keys[i:i + _BULKFETCH_LIMIT]
        try:
            data = atlassian_post(
                "/rest/api/3/issue/bulkfetch",
                body={"issueIdsOrKeys": parca, "fields": _ISSUE_ALANLARI},
                cloud_id=cloud_id,
            )
            for issue in data.get("issues", []) or []:
                if issue.get("key"):
                    taze[issue["key"]] = _issue_ayrıstir(issue)
        except Exception as e:
            print(f"  ⚠ Taze issue okuma başarısız ({len(parca)} görev), arama sonucu kullanılacak: {e}")
    return taze


def _agent_analiz_ayikla(metin: str) -> str | None:
    """Jira task açıklamasından AGENT ANALİZİNİ ayıklar (Yol 2 backfill filtresi).
    Marker '🤖' (Jira Köprüsü '## 🤖 Teknik Analiz') varsa o başlıktan SONRASI; yoksa
    analiz-şablonu sinyalleri + yeterli uzunluk varsa tüm gövde; değilse None (örnek değil)."""
    t = (metin or "").strip()
    if len(t) < 400:
        return None
    idx = t.find("🤖")
    if idx != -1:
        sonrasi = t[idx:]
        nl = sonrasi.find("\n")
        analiz = (sonrasi[nl + 1:] if nl != -1 else "").strip()
        return analiz if len(analiz) >= 400 else None
    dusuk = t.lower()
    sinyaller = ("## amaç", "kabul kriter", "iş mantığı", "endpoint", "## sorun", "## çözüm",
                 "etkilenen", "ekran/bileşen", "veri modeli", "## kapsam", "bağımlılık", "hata yönetimi")
    vurus = sum(1 for s in sinyaller if s in dusuk)
    return t if (vurus >= 2 and len(t) >= 600) else None


def jira_gecmis_import(projeler: list[str], gun: int = 180, limit: int = 300) -> dict:
    """Yol 2 — Geçmiş Jira analizlerini örnek havuzuna aktarır (ortak few-shot backfill).
    Belirtilen projelerde son `gun` gün içinde GÜNCELLENMİŞ, açıklaması OLAN task'ları tarar;
    `_agent_analiz_ayikla` ile agent analizini ayıklayıp `ornek_kaydet` ile yerel+sink havuzuna
    yazar (idempotent — id-dedup). Dönen: {taranan, eklenen, atlanan, hata}."""
    from .ornek_havuzu import ornek_kaydet
    projeler = [str(p).strip().upper() for p in (projeler or []) if str(p).strip()]
    if not projeler:
        return {"taranan": 0, "eklenen": 0, "atlanan": 0, "hata": "Proje seçilmedi."}
    try:
        gun = max(1, min(int(gun or 180), 1095))
    except (TypeError, ValueError):
        gun = 180
    cloud_id = _cloud_id()
    jql = (f"project in ({','.join(projeler)}) AND updated >= -{gun}d "
           f"AND description is not EMPTY ORDER BY updated DESC")
    taranan = eklenen = atlanan = 0
    next_token = None
    try:
        while taranan < limit:
            body = {"jql": jql, "fields": _ISSUE_ALANLARI, "maxResults": 100}
            if next_token:
                body["nextPageToken"] = next_token
            data = atlassian_post("/rest/api/3/search/jql", body=body, cloud_id=cloud_id)
            issues = data.get("issues", []) or []
            if not issues:
                break
            for issue in issues:
                taranan += 1
                g = _issue_ayrıstir(issue)
                analiz = _agent_analiz_ayikla(g.get("description", ""))
                if analiz and ornek_kaydet("teknik", analiz, girdi_ozeti=g.get("summary", ""),
                                           proje=g["key"].split("-")[0], jira_key=g["key"]):
                    eklenen += 1
                else:
                    atlanan += 1
                if taranan >= limit:
                    break
            next_token = data.get("nextPageToken")
            if not next_token:
                break
        return {"taranan": taranan, "eklenen": eklenen, "atlanan": atlanan, "hata": ""}
    except Exception as e:
        return {"taranan": taranan, "eklenen": eklenen, "atlanan": atlanan, "hata": str(e)[:200]}


def alt_gorevleri_cek(parent_key: str) -> list[dict]:
    """Verilen Epic/Story KEY'inin BİR SEVİYE altındaki görevleri çeker. Üç bağ
    modelini BİRLEŞTİRİR (tekrarsız): `parent = KEY` (sub-task/team-managed çocuk),
    `"Epic Link" = KEY` (company-managed epic çocuğu) ve `issue in linkedIssues(KEY)`
    (Relates vb. issue-link — bazı ekipler hiyerarşi yerine bunu kullanır). Projede
    olmayan alan/JQL sessizce atlanır.

    İKİ AŞAMA: (1) arama = KEŞİF (hangi issue'lar bağlı), (2) bulkfetch = TAZE İÇERİK.
    Arama indeksi gecikmeli olduğundan içerik doğrudan issue'dan okunur; böylece
    Jira'da yapılan güncellemeler yeniden çekmede ANINDA görünür."""
    parent_key = (parent_key or "").strip().upper()
    if not _ID_DESENI.match(parent_key):
        raise ValueError(f"Geçersiz Jira anahtarı: '{parent_key}' (örn. PROJ-123 olmalı)")

    cloud_id = _cloud_id()

    def _ara(jql: str) -> list[dict]:
        gorevler, next_token = [], None
        while True:
            body = {"jql": jql, "fields": _ISSUE_ALANLARI, "maxResults": 100}
            if next_token:
                body["nextPageToken"] = next_token
            data = atlassian_post("/rest/api/3/search/jql", body=body, cloud_id=cloud_id)
            for issue in data.get("issues", []):
                gorevler.append(_issue_ayrıstir(issue))
            next_token = data.get("nextPageToken")
            if not next_token:
                break
        return gorevler

    # "Alt görev" tanımı projeden projeye değişir. Üç modeli de kapsa, birleştir:
    #   1. parent = KEY           → gerçek sub-task / team-managed çocuk
    #   2. "Epic Link" = KEY      → company-managed epic çocuğu
    #   3. linkedIssues(KEY)      → issue-link (Relates vb.) ile bağlı görevler
    #                               (bazı ekipler hiyerarşi yerine bunu kullanır)
    jql_adaylari = [
        f"parent = {parent_key}",
        f'"Epic Link" = {parent_key}',
        f'issue in linkedIssues("{parent_key}")',
    ]
    # AŞAMA 1 — KEŞİF: hangi issue'lar bu üst göreve bağlı? (arama indeksi)
    birlesik: dict[str, dict] = {}   # key → arama sonucu (bulkfetch başarısız olursa yedek)
    sirali_keys: list[str] = []      # keşif sırasını koru (ORDER BY created ASC)
    basarili, son_hata = 0, None
    for jql in jql_adaylari:
        try:
            for g in _ara(f"{jql} ORDER BY created ASC"):
                if g["key"] != parent_key and g["key"] not in birlesik:
                    birlesik[g["key"]] = g   # ilk gelen kazanır, tekrarı önle
                    sirali_keys.append(g["key"])
            basarili += 1
        except Exception as e:
            # YALNIZ 400 (alan/JQL projede yok) sessizce geçilir. 401/403/ağ hatası '0 alt görev' DEĞİLDİR:
            # tüm sorgular düşerse net hata yükselir (eskiden analist boş liste görüp yetki sorununu anlamıyordu).
            if _http_durum(e) == 400:
                continue
            son_hata = e
            print(f"  ⚠ Alt görev sorgusu başarısız ({jql}): {str(e)[:160]}")
    if basarili == 0 and son_hata is not None:
        raise RuntimeError(f"Alt görevler okunamadı (yetki/ağ): {str(son_hata)[:200]}") from son_hata

    # AŞAMA 2 — TAZE İÇERİK: başlık/açıklama/yorum/bağlantıları doğrudan issue'dan
    # oku. Arama indeksi gecikmeli olduğu için Jira'daki güncellemeler aksi hâlde
    # yeniden çekmede görünmüyordu.
    taze = _taze_issue_oku(sirali_keys, cloud_id) if sirali_keys else {}
    sonuc = [taze.get(k) or birlesik[k] for k in sirali_keys]

    # AŞAMA 3 — GİRİLEN ANAHTARIN KENDİSİ: Epic/Story ise kapsayıcıdır, listede
    # yer almaz (altındaki görevler istenir). Görev/Bug gibi yaprak iş kaleminde
    # ise analistin asıl incelemek istediği şey odur → EN ÜSTE eklenir.
    kendi_ham = _tek_issue_ham(parent_key, cloud_id)
    if kendi_ham is not None:
        tip = (kendi_ham.get("fields") or {}).get("issuetype")
        if not _kapsayici_mi(tip):
            sonuc.insert(0, _issue_ayrıstir(kendi_ham))
    return sonuc


# ─── Sınıflandırma: Yapısal + AI ─────────────────────────────────────────────

# Her alternatif BAŞLIK olarak çapalı (satır başı + opsiyonel #/bold) — eskiden `|değişiklik`, `|amaç\s*:`,
# `|acceptance` çapasızdı → gövdede geçen tek kelime 'bölüm var' sayılıyordu (yapısal skor şişiyordu).
_BOLUM_DESENLERI = {
    "amac": re.compile(r"(?im)^\s*(?:#{0,4}|\*\*)\s*ama[cç]\b"),
    "degisiklik": re.compile(r"(?im)^\s*(?:#{0,4}|\*\*)\s*de[gğ]i[sş]iklik"),
    "referans": re.compile(r"(?im)^\s*(?:#{0,4}|\*\*)\s*(?:referans|yakla[sş][iı]m)\b"),
    "kabul": re.compile(r"(?im)^\s*(?:#{0,4}|\*\*)\s*(?:kabul\s*kriter|acceptance\s*criteria)"),
}
_DOSYA_DESENI = re.compile(r"\b[\w./-]+\.(?:tsx|ts|jsx|js|py|java|cs|vue|json|ya?ml|sql|md)\b")


def _yapisal_skor(gorev: dict) -> dict:
    """Görev içeriğinin standart bölümleri taşıyıp taşımadığını deterministik ölçer."""
    metin = f"{gorev.get('summary','')}\n{gorev.get('description','')}"
    bolumler = {ad: bool(d.search(metin)) for ad, d in _BOLUM_DESENLERI.items()}
    dosya_ref = bool(_DOSYA_DESENI.search(metin))
    uzun = len(gorev.get("description", "")) >= 120
    bolum_sayisi = sum(bolumler.values())
    # Yapısal "hazır" sinyali: kabul kriteri + (amaç/değişiklik) + (dosya ya da uzunluk)
    hazir_yapisal = bolumler["kabul"] and (bolumler["amac"] or bolumler["degisiklik"]) and (dosya_ref or uzun)
    return {
        "bolumler": bolumler,
        "bolum_sayisi": bolum_sayisi,
        "dosya_ref": dosya_ref,
        "uzun": uzun,
        "hazir_yapisal": hazir_yapisal,
    }


def _siniflandirma_prompt() -> str:
    return (
        "Kıdemli teknik analistsin. Sana bir Jira üst görevinin altındaki alt görevler "
        "verilecek. Her görevin BAŞLIK ve AÇIKLAMASINI OKU; içeriğine göre sınıflandır.\n\n"
        "'hazir' = amaç net, yapılacak değişiklik somut, etkilenen dosya/ekran belli ve "
        "test edilebilir kabul kriteri var — geliştirici ek soru sormadan başlayabilir.\n"
        "'detay' = muğlak/üst seviye, kapsam veya kabul kriteri eksik, teknik yaklaşım belirsiz "
        "ya da birden çok yoruma açık — önce teknik analiz gerekir.\n\n"
        "ÖNEMLİ: 'gerekce' o görevin İÇERİĞİNE özgü, somut bir tek cümle olmalı "
        "(örn. \"Etkilenen dosyalar ve i18n anahtarları net, kabul kriteri test edilebilir\" / "
        "\"Endpoint sözleşmesi ve hata durumları tanımsız\"). Genel/kalıp cümle YAZMA.\n"
        "Sana deterministik bir 'yapisal_hazir' ipucu verilir; dikkate al ama kararı İÇERİKTEN ver.\n\n"
        "SADECE şu JSON formatında yanıt ver, başka metin yazma:\n"
        '{"sonuclar":[{"key":"PROJ-1","durum":"hazir|detay","gerekce":"içeriğe özgü tek cümle",'
        '"eksikler":["detay ise eksik olan somut şeyler"]}]}'
    )


def _json_ayikla(metin: str) -> dict:
    """AI yanıtından ilk JSON nesnesini güvenli ayıklar."""
    m = re.search(r"\{.*\}", metin, re.DOTALL)
    if not m:
        raise ValueError("AI yanıtında JSON bulunamadı")
    return json.loads(m.group(0))


_BOLUM_ETIKET = {"amac": "Amaç", "degisiklik": "Değişiklik", "referans": "Referans", "kabul": "Kabul kriteri"}

# ─── Benzer Task Tespiti (deterministik, 0 token) ────────────────────────────

_STOPWORDS = {
    "ve", "ile", "için", "de", "da", "bir", "bu", "şu", "the", "of", "for", "to", "in", "on",
    "fe", "be", "ui", "api",  # katman/genel etiketleri — sinyal değil
}
_TOKEN_DESENI = re.compile(r"[a-zA-Z0-9ğüşıöçĞÜŞİÖÇ]{3,}")


def _benzerlik_jetonlari(gorev: dict) -> set[str]:
    """Görevin başlığı + açıklamasının ilk 300 karakterinden token seti üretir.
    Stopword'ler ve 3'ten kısa kelimeler atılır."""
    metin = (gorev.get("summary", "") + " " + (gorev.get("description", "") or "")[:300]).lower()
    return {t for t in _TOKEN_DESENI.findall(metin) if t not in _STOPWORDS}


def benzer_gorevleri_isaretle(gorevler: list[dict], esik: float = 0.35) -> None:
    """Görev listesinde her görev için BENZER (Jaccard ≥ esik) olanları bulup
    g['benzerler'] = [{'key', 'summary', 'skor'}] olarak işaretler. Token harcamaz.
    O(n²) ama 100 görevde milisaniye düzeyinde."""
    setler = [(g, _benzerlik_jetonlari(g)) for g in gorevler]
    for g, s in setler:
        g["benzerler"] = []
        if len(s) < 4:  # çok az token varsa sinyal güvenilmez
            continue
        skorlar = []
        for h, sh in setler:
            if h is g or len(sh) < 4:
                continue
            kesisim = len(s & sh)
            birlesim = len(s | sh)
            if not birlesim:
                continue
            j = kesisim / birlesim
            if j >= esik:
                skorlar.append((j, h))
        skorlar.sort(reverse=True, key=lambda x: x[0])
        g["benzerler"] = [
            {"key": h["key"], "summary": h.get("summary", ""), "skor": round(j, 2)}
            for j, h in skorlar[:3]  # ilk 3 benzer yeter
        ]


def _yapisal_gerekce(ys: dict) -> str:
    """Yapısal taramada NEYE göre karar verildiğini şeffaf gösterir (içerik
    incelemesi DEĞİL — format/bölüm tespiti)."""
    var = [_BOLUM_ETIKET[a] for a, v in ys["bolumler"].items() if v]
    if ys["dosya_ref"]:
        var.append("dosya ref")
    bulgu = ", ".join(var) if var else "yapılandırılmış içerik yok"
    return f"Yapısal ön-tarama (format): {bulgu}"


def _ai_siniflandir(gorevler: list[dict], parca_boyu: int = 12) -> dict:
    """Görevleri AI ile İÇERİKTEN sınıflandırır. Büyük listeyi parçalara böler
    (CLI'de tek dev çağrı yavaş + çıktı limiti riski). key→{durum,gerekce,eksikler}."""
    ai_map: dict[str, dict] = {}
    sistem = _siniflandirma_prompt()
    for i in range(0, len(gorevler), parca_boyu):
        parca = gorevler[i:i + parca_boyu]
        ozet = [{
            "key": g["key"],
            "summary": g["summary"],
            "description": g["description"][:900],
            "yapisal_hazir": g["yapisal"]["hazir_yapisal"],
        } for g in parca]
        mesajlar = [{"role": "user", "content": [
            {"type": "text", "text": "Alt görevler:\n\n" + json.dumps(ozet, ensure_ascii=False, indent=2)},
            {"type": "text", "text": "Her görevi İÇERİĞİNE göre sınıflandır ve belirtilen JSON formatında dön."},
        ]}]
        try:
            yanit = _api_cagri(sistem, mesajlar, max_tokens=MAX_TOKENS_KISA, thinking=False)
            sonuclar = _json_ayikla(_metin_sikistir(yanit)).get("sonuclar", [])
            if not sonuclar:
                # Bozuk/boş yanıt 7 gün önbellekte kalmasın → BİR KEZ önbelleksiz tekrar
                yanit = _api_cagri(sistem, mesajlar, max_tokens=MAX_TOKENS_KISA, thinking=False, onbellek=False)
                sonuclar = _json_ayikla(_metin_sikistir(yanit)).get("sonuclar", [])
            for s in sonuclar:
                ai_map[s.get("key", "")] = s
        except Exception as e:
            print(f"  ⚠ AI sınıflandırma parçası başarısız ({i}-{i+len(parca)}), yapısala düşülüyor: {e}")
    return ai_map


def _triyaja_uygun_mu(gorev: dict) -> bool:
    """Görev, Hızlı İşleme / Detaylı Analiz triyajına girmeli mi?

    Amaç: analistin ANALİZ EDİP DETAYLANDIRACAĞI, henüz işleme alınmamış işler.
    Kural: durumu Backlog VE atanmamış. UAT / TAMAM / READY FOR TEST / Devam Ediyor
    gibi ilerlemiş (işe alınmış) durumlar triyaja alınmaz — bunlar yalnızca
    "Tüm Görevler" listesinde görünür."""
    status = (gorev.get("status") or "").strip().lower()
    atanmamis = not (gorev.get("assignee") or "").strip()
    return "backlog" in status and atanmamis


def gorevleri_siniflandir(gorevler: list[dict], ai_kullan: bool = True) -> dict:
    """İki fazlı sınıflandırma. Her görevde 'kaynak' alanı kararın NEYE dayandığını
    belirtir ('yapisal' = format ön-tarama / 'ai' = içerik incelemesi):
      - ai_kullan=False (FAZ 1): yalnızca yapısal ön-tarama — anında, 0 token.
        Bölüm/dosya işaretlerine bakar; İÇERİĞİ İNCELEMEZ. Şeffaf gerekçe verir.
      - ai_kullan=True (FAZ 2): AI HER görevin içeriğini okuyup sınıflandırır
        (parçalara bölünmüş); kararı gerçek bir gerekçeyle döner. Yapısal sonuç
        AI başarısız olan görevler için fallback kalır.

    Hızlı İşleme / Detaylı Analiz gruplarına YALNIZCA triyaja uygun (Backlog +
    atanmamış) görevler girer (bkz. `_triyaja_uygun_mu`). Tüm görevler ayrıca
    'tum' altında döner — "Tüm Görevler" başlığı + statü/atanan filtreleri için."""
    if not gorevler:
        return {"hazir": [], "detay": [], "tum": []}

    for g in gorevler:
        g["yapisal"] = _yapisal_skor(g)

    # Benzer içerik tespiti — deterministik, 0 token; her görev `benzerler` listesi alır
    benzer_gorevleri_isaretle(gorevler)

    # Triyaj YALNIZCA Backlog + atanmamış görevlerde çalışır (analistin işleme
    # alacağı fresh işler). İlerlemiş görevler yalnızca "Tüm Görevler"de kalır.
    uygunlar = [g for g in gorevler if _triyaja_uygun_mu(g)]
    ai_map = _ai_siniflandir(uygunlar) if ai_kullan else {}

    hazir, detay = [], []
    for g in uygunlar:
        ys = g["yapisal"]
        ai = ai_map.get(g["key"])
        if ai and ai.get("durum") in ("hazir", "detay"):
            g["durum"] = ai["durum"]
            g["gerekce"] = ai.get("gerekce", "") or "AI içerik incelemesi"
            g["eksikler"] = ai.get("eksikler", []) or []
            g["kaynak"] = "ai"
        else:
            g["durum"] = "hazir" if ys["hazir_yapisal"] else "detay"
            g["gerekce"] = _yapisal_gerekce(ys)
            g["eksikler"] = [] if ys["hazir_yapisal"] else \
                [_BOLUM_ETIKET[a] for a, v in ys["bolumler"].items() if not v]
            g["kaynak"] = "yapisal"
        (hazir if g["durum"] == "hazir" else detay).append(g)

    # 'yapisal' iç alanı UI'a gönderilmesin (sade JSON). Triyaj dışı görevler
    # durum/gerekce/kaynak ALMAZ — "Tüm Görevler"de nötr kart olarak görünür.
    for g in gorevler:
        g.pop("yapisal", None)

    return {"hazir": hazir, "detay": detay, "tum": gorevler}


# ─── Sadece Client (Frontend-only) Ayıklama ──────────────────────────────────
# Board'dan çekilen task'ların hangileri HİÇBİR BFF/BE değişikliği gerektirmeden,
# YALNIZCA client (frontend) tarafında tamamlanabilir olduğunu ayırır. Bağlı BE
# task'ları dikkate alınır: bir task'ın bağlı bir BE task'ı varsa, isterin sunucu
# tarafı da geliştirilmeli demektir → "sadece client" DEĞİLDİR.

def _sadece_client_prompt() -> str:
    return (
        "Kıdemli teknik analistsin. Bir bahis/trade panelinin (Trade Panel) Jira "
        "görevlerini inceliyorsun. Mimari: React tabanlı CLIENT (frontend) + BFF katmanı "
        "+ backend (BE) mikroservisleri. Sana görevler ve her görevin BAĞLI task'ları "
        "verilecek. Görevi tamamlamak için GEREKEN işin YALNIZCA client (frontend) tarafında "
        "olup olmadığına karar ver.\n\n"
        "'sadece_client' = true KOŞULLARI (HEPSİ sağlanmalı):\n"
        "- Yeni/değişen BFF veya BE endpoint'i GEREKMEZ.\n"
        "- Servis request/response sözleşmesinde (yeni alan, yeni parametre) değişiklik GEREKMEZ.\n"
        "- Yeni DB kolonu/tablosu, migration, sunucu-tarafı iş kuralı/hesaplama GEREKMEZ.\n"
        "- İhtiyaç duyulan TÜM veri client'a ZATEN geliyor (mevcut API'lerle karşılanıyor).\n"
        "- İş tamamen client: UI yerleşimi, stil, client-side validasyon, formatlama, i18n, "
        "zaten çekilmiş veriyi client'ta filtreleme/sıralama, bileşen refactor, client state, "
        "navigasyon, görsel/etkileşim değişiklikleri.\n\n"
        "'sadece_client' = false YAPAN sinyaller (BİRİ bile varsa false):\n"
        "- Görev metni yeni endpoint, response'a yeni alan, servis/BFF değişikliği, DB, migration "
        "veya backend hesaplama ima ediyor.\n"
        "- Görevin BAĞLI bir BE task'ı var (aynı isterin sunucu tarafı ayrı task'ta geliştiriliyor). "
        "Bu, isterin backend geliştirme İÇERDİĞİNİN güçlü kanıtıdır → sadece_client = false.\n"
        "- İhtiyaç duyulan veri client'ta mevcut değil, yeni bir servisten gelmeli.\n\n"
        "KRİTİK KURAL: Emin değilsen 'sadece_client' = FALSE ver. Yanlışlıkla bir görevi "
        "'sadece client' işaretlemek teslimatı bozar (backend eksik kalır); tersi güvenlidir. "
        "Backend ihtiyacı gördüğünde 'backend_ihtiyaci' alanında NE gerektiğini tek cümleyle yaz.\n\n"
        "SADECE şu JSON formatında yanıt ver, başka metin yazma:\n"
        '{"sonuclar":[{"key":"PROJ-1","sadece_client":true,'
        '"gerekce":"içeriğe özgü tek cümle — neden yalnızca client / neden değil",'
        '"backend_ihtiyaci":"false ise gereken sunucu işi; true ise boş string"}]}'
    )


def _sadece_client_ai(gorevler: list[dict], parca_boyu: int = 20) -> dict:
    """Görevleri AI ile 'sadece client mi' diye sınıflandırır (parçalı).
    Her görevin açıklaması + bağlı task özetleri AI'a verilir.
    key → {sadece_client, gerekce, backend_ihtiyaci}."""
    ai_map: dict[str, dict] = {}
    sistem = _sadece_client_prompt()
    for i in range(0, len(gorevler), parca_boyu):
        parca = gorevler[i:i + parca_boyu]
        ozet = []
        for g in parca:
            bagli = [
                {"key": b["key"], "summary": b["summary"], "type": b["type"],
                 "iliski": b["iliski"], "tahmini_katman": b["katman"]}
                for b in (g.get("baglantililar") or [])
            ]
            ozet.append({
                "key": g["key"],
                "summary": g["summary"],
                "description": (g.get("description") or "")[:1100],
                "bagli_tasklar": bagli,
            })
        mesajlar = [{"role": "user", "content": [
            {"type": "text", "text": "Görevler ve bağlı task'ları:\n\n" + json.dumps(ozet, ensure_ascii=False, indent=2)},
            {"type": "text", "text": "Her görev için YALNIZCA client tarafında mı yapılacağına karar ver ve belirtilen JSON formatında dön."},
        ]}]
        try:
            yanit = _api_cagri(sistem, mesajlar, max_tokens=MAX_TOKENS_KISA, thinking=False)
            for s in _json_ayikla(_metin_sikistir(yanit)).get("sonuclar", []):
                ai_map[s.get("key", "")] = s
        except Exception as e:
            print(f"  ⚠ Sadece-client sınıflandırma parçası başarısız ({i}-{i+len(parca)}): {e}")
    return ai_map


def sadece_client_ayikla(gorevler: list[dict]) -> dict:
    """Board task'larından YALNIZCA client (frontend) tarafında yapılacak olanları
    ayırır. Bağlı BE task'ları dikkate alır. Döner:
      {"sadece_client": [...], "diger": [...], "toplam": n}
    Her görevde 'sc_gerekce' ve 'sc_backend_ihtiyaci' alanları set edilir.

    AI hiç sonuç veremezse (429/hata) deterministik fallback: bağlı BE task'ı olan
    VEYA açıklamasında güçlü BE sinyali olan görevler 'diger'e, kalanlar — güvenli
    olması için — yine 'diger'e düşer (AI'sız 'sadece client' KESİNLEŞTİRİLMEZ)."""
    if not gorevler:
        return {"sadece_client": [], "diger": [], "toplam": 0}

    ai_map = _sadece_client_ai(gorevler)
    sadece_client, diger = [], []
    for g in gorevler:
        ai = ai_map.get(g["key"])
        bagli_be = [b for b in (g.get("baglantililar") or []) if b.get("katman") == "be"]
        if ai is not None:
            karar = bool(ai.get("sadece_client"))
            g["sc_gerekce"] = ai.get("gerekce", "") or ""
            g["sc_backend_ihtiyaci"] = ai.get("backend_ihtiyaci", "") or ""
            g["sc_kaynak"] = "ai"
        else:
            # AI yok → güvenli taraf: kesin 'sadece client' deme.
            karar = False
            g["sc_gerekce"] = (
                "AI sınıflandırması yapılamadı — güvenlik gereği 'sadece client' kesinleştirilmedi"
                + (f"; ayrıca bağlı BE task(lar): {', '.join(b['key'] for b in bagli_be)}" if bagli_be else "")
            )
            g["sc_backend_ihtiyaci"] = ""
            g["sc_kaynak"] = "fallback"
        (sadece_client if karar else diger).append(g)

    return {"sadece_client": sadece_client, "diger": diger, "toplam": len(gorevler)}


# ─── Özellik 1: Standart Formata Çevir ───────────────────────────────────────

def gorev_standart_formatla(gorev: dict) -> str:
    """Mevcut görev içeriğini agent'ın standart 4-başlık görev formatına çevirir.
    Hafif iş → haiku (Sonnet'in ~%10 maliyeti). YENİ kapsam UYDURMAZ; sadece var
    olan içeriği yeniden yapılandırır + boş bölüme '(belirtilmemiş)' notu yazar."""
    sistem = (
        "Kıdemli teknik analistsin. Sana bir Jira görevinin mevcut başlık ve açıklaması "
        "verilecek. Bu içeriği AŞAĞIDAKİ standart 4-başlık formata yeniden yapılandır.\n\n"
        "KURALLAR:\n"
        "1. YENİ kapsam/dosya/kural/kabul kriteri UYDURMA — yalnızca verilen bilgiyi "
        "doğru bölümlere yerleştir.\n"
        "2. Bir bölüm için bilgi yoksa başlığı KOY ve altına '(belirtilmemiş)' yaz "
        "(başlık varlığı + dolu/boş kuralı). Asla başlığı atlama, asla 'detay başka çıktıda' "
        "veya 'açık sorular ayrı dokümanda' türü notlar EKLEME — bu çıktı kendi kendine yeter.\n"
        "3. Yalnızca aşağıdaki 4 başlık bulunsun, ek bölüm ekleme.\n\n"
        "Çıktıyı TEK bir XML bloğu içinde, Türkçe Markdown olarak ver:\n\n"
        f"<gorev>\n{STANDART_GOREV_SABLONU}\n</gorev>"
    )
    icerik = [
        {"type": "text", "text": f"### Görev: {gorev.get('key','')} — {gorev.get('summary','')}"},
        {"type": "text", "text": f"### Mevcut Açıklama\n\n{gorev.get('description','') or '(açıklama yok)'}"},
        {"type": "text", "text": "Yukarıdaki görevi standart 4-başlık formata çevir."},
    ]
    # Çıktı bütçesi GİRDİDEN ölçeklenir: tam açıklama yeniden yazılır → sabit 3000 token uzun açıklamayı kesiyordu.
    butce = min(MAX_TOKENS_UZUN, max(MAX_TOKENS_KISA, len(gorev.get("description", "") or "") // 3 + 800))
    yanit = _api_cagri(sistem, [{"role": "user", "content": icerik}],
                       model=MODEL_HAFIF, max_tokens=butce, thinking=False)
    return _meta_notlari_temizle(_xml_ayir(_metin_sikistir(yanit), "gorev"))


# ─── Özellik 2: Teknik Analiz ile Detaylandır ────────────────────────────────

_KATMAN_ETIKET = {"fe": "Frontend (FE)", "be": "Backend (BE)", "belirsiz": ""}


def gorev_analiz_et(gorev: dict, cevaplar: str = "", iliskili: list | None = None,
                    katman: str = "", onceki_sorular: str = "", ekran_baglami: bool = True,
                    rag_ctx: dict | None = None, canli_baglam_override: str | None = None,
                    bff_rapor: str | None = None, gozlem_rapor: dict | None = None,
                    canli_kapsam: str | None = None, soru_asamasi: bool = True) -> dict:
    """Görevi YALIN teknik analize çevirir (gorev_teknik_analiz promptu — tek
    görev için, yalnızca ilgili bölümler, tüm şablonu doldurmaz → token/süre
    tasarrufu, kaliteden ödün yok). İki aşama: (1) Sonnet ile analiz (RAG dahil),
    (2) Haiku ile kısa açık-sorular pass'i. Çıktı:
        {"markdown": "<teknik analiz markdown>", "acik_sorular": "<varsa>"}.
    Açık sorular Jira'ya YAZILMAZ — UI'da ayrı sekmede gösterilir.
    `canli_kapsam`: gözlem profili/URL seti ('gorev' | 'surec'); None → eski davranış (override varsa 'surec', yoksa
    'gorev'). Köprü, kullandığı URL kaynağına göre geçirir. `soru_asamasi=False` → açık soru + öz-çözümleme + otomatik
    işleme ATLANIR (FE+BE ayrımında bu aşama iki katman için TEK kez `gorev_fe_be_analiz` içinde koşar).

    NOT: Ağır 11-bölümlük şablon (teknik_analiz_bolumler) yerine görev-bazlı yalın
    prompt kullanılır. Basit görevler artık koca bir 'kapsam dışı' başlık dizisiyle
    dolmaz; sadece gerçekten dokunulan konular kısa yazılır."""
    sistem = prompt_yukle("gorev_teknik_analiz")

    # RAG: bağlam filtresi (Süreç Analizi ekranındaki filtre) ile filtrelenmiş
    # referansları topla. referans_dosyalari_hazirla() zaten load_context_filter()
    # + filtrele_referanslar() çağırıyor — atlamıyor. Burada ayrıca filtre durumunu
    # log ve çıktı meta yorumu için yakalıyoruz (analist şeffaflığı).
    # Jira Köprüsü (ekran_baglami=False): analiz KENDİ KENDİNE YETERLİ olmalı —
    # ekranda kayıtlı bağlam filtresine + analist notuna BAĞLI KALMAZ (Jira'dan komut
    # veren kişi onları göremez/değiştiremez → yanlış task'a ait filtre analizi saptırır).
    # Bağlam yalnız task'ın kendi içeriği + komut argümanı (cevaplar). RAG filtresiz (task-güdümlü).
    ctx = (load_context_filter() or {}) if ekran_baglami else {}
    # RAG filtresi: ekranda → kayıtlı filtre; köprüde → task'tan türetilen keyword'ler
    # (rag_ctx). rag_ctx None ise köprüde filtresiz (task-güdümlü tüm referanslar).
    if ekran_baglami:
        rag_override = None
        filtre_kaynak = ctx
    else:
        rag_override = rag_ctx or {}
        filtre_kaynak = rag_ctx or {}
    aktif_filtreler = []
    if filtre_kaynak.get("keywords"):
        aktif_filtreler.append(f"kelime:{','.join(filtre_kaynak['keywords'])}")
    if filtre_kaynak.get("jira_keys"):
        aktif_filtreler.append(f"jira:{','.join(filtre_kaynak['jira_keys'])}")
    if filtre_kaynak.get("confluence_pages"):
        aktif_filtreler.append(f"conf:{','.join(filtre_kaynak['confluence_pages'])}")

    stable_bloklar: list[dict] = []
    referans_sayisi = 0
    try:
        ref_dosyalar = referans_dosyalari_hazirla(ctx_override=rag_override)
        referans_sayisi = len(ref_dosyalar)
        if aktif_filtreler:
            print(f"  🔍 Bağlam filtresi aktif — {' | '.join(aktif_filtreler)}")
        print(f"  {referans_sayisi} referans dosya dahil ediliyor...")
        if ref_dosyalar:
            # Sorgu = görevin kendi metni (özet + açıklama) → task'a alakalı referanslar seçilir.
            gorev_sorgu = f"{gorev.get('summary','')} {gorev.get('description','') or ''}".strip()
            ref_bloklari, _ = _ref_bloklari_olustur(ref_dosyalar, sorgu_metni=gorev_sorgu)
            stable_bloklar.extend(ref_bloklari)
    except Exception as e:
        print(f"  ⚠ Referanslar dahil edilemedi: {e}")

    # Canlı Uygulama (Chrome MCP) — Jira Görevleri ekranının KENDİ hedefi (live_app_gorev).
    # Süreç/Teknik Analiz ekranının URL'inden bağımsızdır; iki akış birbirini ezmez.
    # Köprü, base-URL + task-güdümlü hedef ile kendi canlı-gözlem bağlamını verir
    # (canli_baglam_override); ekran akışı kendi live_app_gorev hedefini kullanır.
    # BFF sözleşme raporu (skills/bff_kesif — agent'ın kendi CRUD gözlemi) → gerçek endpoint/alan/mesajlar
    if bff_rapor:
        print("  🔌 BFF sözleşme raporu (canlı CRUD gözlemi) dahil ediliyor...")
        stable_bloklar.append({"type": "text", "text": bff_rapor})
    canli_baglam = canli_baglam_override if canli_baglam_override is not None \
        else canli_uygulama_baglami_hazirla(gorev=True)
    # Faz 1 (kota): canlı gözlem ANALİZDEN AYRI küçük promptlu bir fazda yapılır (skills/gozlem.py) → analiz çağrısı
    # gözlem RAPORUNU alır, tarayıcı aracı kullanmaz. Cevap turu / düzelt (cevaplar|onceki_sorular) taze raporu yeniden
    # kullanır (6 sa); yeni analiz taze gözler. FE+BE ayrımında rapor dışarıdan (gozlem_rapor) paylaşılır.
    kapsam = canli_kapsam or ("surec" if canli_baglam_override is not None else "gorev")
    if canli_baglam and gozlem_rapor is None:
        from . import gozlem as _gz
        gozlem_rapor = _gz.rapor_al(canli_baglam, kapsam,
                                   gorev_ozet=f"{gorev.get('summary', '')}\n\n{gorev.get('description', '') or ''}",
                                   yeniden=not bool((cevaplar or "").strip() or (onceki_sorular or "").strip()))
    if canli_baglam:
        from . import gozlem as _gz
        # Yalnız MAKİNE-DOĞRULANMIŞ (ok) rapor gerçek veri olarak girer; ok=False rapor (araç çalışmamış, kanıt yok)
        # 'gözlem yapıldı' diye enjekte edilirse analiz uydurma ekranı gerçek sanır.
        if gozlem_rapor and gozlem_rapor.get("ok") and gozlem_rapor.get("md"):
            print("  🌐 Canlı gözlem raporu (ayrı faz) analize dahil ediliyor...")
            stable_bloklar.append({"type": "text", "text": _gz.rapor_blogu(gozlem_rapor)})
        else:
            print("  ⚠ Canlı gözlem yapılamadı — analiz gözlemsiz üretiliyor (rapor rozetinde görünür).")
            stable_bloklar.append({"type": "text", "text": _gz.gozlem_yok_blogu((gozlem_rapor or {}).get("neden", ""))})

    if stable_bloklar:
        stable_bloklar[-1]["cache_control"] = {"type": "ephemeral"}

    icerik = stable_bloklar + [
        {"type": "text", "text": f"### Analiz Edilecek Jira Görevi: {gorev.get('key','')}\n\n"
                                 f"**Başlık:** {gorev.get('summary','')}\n\n"
                                 f"**Açıklama:**\n{gorev.get('description','') or '(açıklama yok)'}"},
    ]

    # Analist Notu (opsiyonel) — Jira Görevleri ekranından girilir (context_filter.json).
    # Doluysa mevcut sistem promptuyla BİRLİKTE dikkate alınır; boşsa hiç eklenmez (token yok).
    analist_notu = str(ctx.get("gorev_analist_notu", "") or "").strip()
    if analist_notu:
        print("  📝 Analist notu dikkate alınıyor (teknik analize dahil).")
        icerik.append({"type": "text", "text": (
            "### ANALİST NOTU (bu göreve özel — DİKKATE AL)\n"
            "Analist bu görev için özel bir yorum/odak/akış belirtti. Teknik analizi üretirken bu notu "
            "MUTLAKA dikkate al; belirtilen kısma veya akışa özellikle eğil. Bu not mevcut sistem "
            "promptunun YERİNE geçmez — onunla BİRLİKTE çalışır ve doğruluk, gözlemlenebilirlik ve "
            "spekülasyon-yasağı kurallarını GEVŞETMEZ (nota dayanarak gözleyemediğin şeyi uydurma).\n\n"
            f"Not:\n{analist_notu}"
        )})

    # Prompt-cache genişletme (P0 madde 3): görev içeriği (key/başlık/açıklama + analist notu) tur'lar
    # arasında DEĞİŞMEZ; yalnız cevaplar/önceki-sorular değişir. Buraya ikinci cache breakpoint koyarak
    # (refs breakpoint'ine ek) cevap/düzeltme turlarında görev içeriği de cache'ten okunur — her turda
    # yeniden token ödemek yerine. Sistem(1)+refs(1)+görev(1) = 3 breakpoint (Anthropic tavanı 4).
    icerik[-1]["cache_control"] = {"type": "ephemeral"}

    # Analist cevapları (opsiyonel) — modaldeki "Açık Sorular"a verilen cevaplar. Doluysa, analizi
    # bu cevaplara göre YENİDEN yaz: cevaplanan belirsizlikleri ÇÖZ, ilgili bölümü netleştir.
    cevaplar = (cevaplar or "").strip()
    if cevaplar:
        print("  💬 Analist cevapları dikkate alınıyor (belirsizlikler çözülecek).")
        icerik.append({"type": "text", "text": (
            "### ANALİST CEVAPLARI (önceki açık sorulara) — DİKKATE AL\n"
            "Analist aşağıda önceki turdaki açık soruların bir kısmını cevapladı. Teknik analizi bu cevaplara "
            "göre GÜNCELLE: cevaplanan belirsizlikleri ÇÖZ (artık o konuları `[K: ❓ Belirsiz]` / `⚠ VARSAYIM` "
            "bırakma, cevaba göre kesinleştir), ilgili bölümü buna göre yaz. Cevaplanmayan konular açık soru "
            "olarak kalabilir. Cevapları uydurma bilgiyle genişletme — yalnız verileni uygula.\n\n"
            f"Analist cevapları:\n{cevaplar}"
        )})
    # İLİŞKİLİ FE/BE ANALİZİ (opsiyonel) — bağlı KARŞI-katman task'lar bağlam olarak eklenir; analiz
    # BU görevin katmanına odaklanır, karşı katmanın İÇ implementasyonunu yazmaz, yalnız ARAYÜZ/SÖZLEŞMEyi verir.
    katman = (katman or "").strip().lower()
    kat_et = _KATMAN_ETIKET.get(katman, "")
    if iliskili:
        satirlar = []
        for r in iliskili:
            rkat = _KATMAN_ETIKET.get((r.get("katman") or "").lower(), "") or "katman?"
            aciklama = (r.get("description") or "(açıklama yok)").strip()
            satirlar.append(f"### Bağlı task {r.get('key','')} [{rkat}] — {r.get('summary','')}\n{aciklama[:4000]}")
        icerik.append({"type": "text", "text": (
            "### İLİŞKİLİ (KARŞI KATMAN) TASK'LAR — BAĞLAM\n"
            "Aşağıdaki task'lar bu görevle ilişkili ve genellikle KARŞI katmandır. Bunların İÇ "
            "implementasyonunu ANALİZ ETME (onlar ayrı analiz edilir). Yalnızca bu görevle ARAYÜZ/BAĞIMLILIK "
            "ilişkisini kur.\n\n" + "\n\n".join(satirlar)
        )})
    if kat_et:
        icerik.append({"type": "text", "text": (
            f"### KATMAN ODAĞI: {kat_et}\n"
            f"Bu görev bir {kat_et} işidir. Analizi {kat_et} katmanının İÇ işine odakla "
            f"({'ekran/bileşen/state/validasyon/istemci akışı' if katman=='fe' else 'veri modeli/endpoint/iş kuralı/servis'} vb.). "
            + ("İlişkili karşı-katman task(lar)ıyla etkileşimi AYRI bir `## Bağımlılık ve Arayüz (FE↔BE)` "
               "başlığında SÖZLEŞME olarak ver: "
               + ("FE'nin BE'den beklediği endpoint/alan/istek-yanıt sözleşmesi (hangi çağrı, hangi alanlar, "
                  "beklenen yanıt şekli/durum). Karşı katmanın nasıl yapacağını YAZMA."
                  if katman == "fe" else
                  "BE'nin FE'ye SUNACAĞI endpoint/alan/yanıt sözleşmesi (method/path, istek/yanıt alanları, "
                  "durum kodları) ve hangi FE task'ının tükettiği. FE'nin nasıl render edeceğini YAZMA.")
               if iliskili else "Karşı katman işini bu analize KATMA.")
            + "\n\nANALİZİN EN BAŞINA TEK SATIR yaz: `**Bu katmanda iş:** VAR — <tek cümle: ne>` ya da, bu görev için "
              f"{kat_et} tarafında HİÇ değişiklik gerekmiyorsa `**Bu katmanda iş:** YOK — <tek cümle gerekçe>` (o zaman kalan "
              "analizi 2-3 cümleyle sınırla; dolgu bölüm açma). Analist bu satıra bakarak yalnız gereken katmanın task'ını açar."
        )})
    # HATA/BASİT İŞ MODU — çıktıyı işin boyutuna göre ÖLÇEKLE. Küçük iş, task'ta büyük iş gibi durmasın.
    if _hata_gorev_mi(gorev):
        print("  🐞 Hata/basit iş algılandı — analiz KISA-NET tutulacak (bug modu).")
        icerik.append({"type": "text", "text": (
            "### ÇIKTI MODU: HATA / BASİT İŞ — KISA ve NET (KRİTİK)\n"
            "Bu bir HATA/bug ya da küçük düzeltme. Geliştiriciye SORUNU ve NE YAPILACAĞINI net-yalın ilet; "
            "task'ı gereksiz büyük GÖSTERME. KURALLAR:\n"
            "- **YALNIZCA şu kısa başlıklar** (dokunulmayanı hiç açma): `## Sorun` (net: ne yanlış, nerede/hangi "
            "ekran-akış, gerekiyorsa 1 tekrar-adımı) · `## Çözüm` (somut ne yapılmalı — 2-6 madde) · "
            "(gerçekten gerekiyorsa) `## Kabul Kriterleri` (1-3 madde).\n"
            "- Şablonun 11 bölümünü AÇMA; İş Gereksinimleri/DB/API/Frontend/Rol/Teknik Borç başlıklarını "
            "YALNIZ hatanın çözümü DOĞRUDAN oradaysa ve KISA yaz — yoksa hiç ekleme.\n"
            "- Gereksiz servis/endpoint/network DÖKÜMÜ, arka plan anlatımı, 'şöyle de yapılabilir' ÖNERİLERİ, "
            "alternatif akışlar YAZMA. Yalnız çözüm için ZORUNLU olan tek endpoint/alan varsa onu ver.\n"
            "- Hedef: geliştirici 20 saniyede okuyup ne yapacağını anlasın. Doğruluk/kaynak-etiketi kuralları "
            "yine geçerli ama KISA."
        )})
    # Değişiklik Etkisi (0 token): görev zorunluluk kaldırma/silme/güncelleme… içeriyorsa veri yaşam
    # döngüsü talimatı + referanslardaki OLASI TÜKETİCİLER. Hata modunda tek 'Etki:' maddesi (kısa kalır).
    try:
        from .degisiklik_etkisi import degisiklik_blogu
        _de_blok = degisiklik_blogu(f"{gorev.get('summary', '')}\n{gorev.get('description', '') or ''}",
                                    hedef="gorev_hata" if _hata_gorev_mi(gorev) else "gorev")
        if _de_blok:
            print("  🔁 Değişiklik etkisi sinyali — veri yaşam döngüsü + olası tüketiciler dahil ediliyor...")
            icerik.append({"type": "text", "text": _de_blok})
    except Exception as _e:
        print(f"  ⚠ Değişiklik etkisi taraması atlandı: {_e}")
    # Few-shot: onaylı EKİP örneklerinden stil/derinlik referansı (Task analizi de havuzdan öğrenir).
    try:
        from .ornek_havuzu import ornek_bloklari
        _os = (str(gorev.get("summary", "")) + "\n" + str(gorev.get("description", "") or ""))[:4000]
        # Kendi taslağı (aynı task'ın önceki analizi — key ya da key::FE) örnek olarak GİRMEZ (öz-kirlenme).
        _kendi = [b for b in ornek_bloklari(_os, tip="teknik", n=4) if not _ornek_kendisi_mi(b, gorev.get("key", ""))]
        for _blok in _kendi[:2]:
            icerik.append(_blok)
    except Exception:
        pass
    icerik.append(
        {"type": "text", "text": "Bu görev için teknik analiz raporunu üret (açık sorular HARİÇ — onlar ayrı adımda üretilecek)."}
    )
    asama_ayarla("gorev:analiz")
    # Gözlem ayrı fazda yapıldı → bu çağrı tarayıcı aracı kullanmaz; önbellek anahtarı rapor metnini içerir
    # (taze rapor = taze analiz; aynı rapor + aynı girdi = önbellek hit, token yok).
    yanit = _api_cagri(sistem, [{"role": "user", "content": icerik}],
                       max_tokens=MAX_TOKENS_COMBINED, thinking=extended_thinking_acik())
    teknik = _meta_notlari_temizle(_xml_ayir(_metin_sikistir(yanit), "teknik_analiz"))

    # Şeffaflık: editör ön-izlemesinde + history'de RAG durumu görünür.
    # HTML yorumu olarak ekle — markdown render'da görünmez ama analist editörde okur.
    filtre_str = " | ".join(aktif_filtreler) if aktif_filtreler else "yok"
    teknik = (
        f"<!-- RAG: {referans_sayisi} referans dosya kullanıldı | bağlam filtresi: {filtre_str} -->\n\n"
        + teknik
    )

    # Aşama 2/2b/2c — açık sorular + öz-çözümleme + otomatik işleme (tek helper; FE+BE ayrımında dışarıda TEK kez koşar)
    acik = ""
    if soru_asamasi:
        [teknik], acik = _soru_asamasi([teknik], gorev, cevaplar=cevaplar, onceki_sorular=onceki_sorular,
                                       canli=bool(canli_baglam), gozlem_rapor=gozlem_rapor,
                                       rag_ctx=(rag_ctx if not ekran_baglami else None),
                                       canli_kapsam=(kapsam if canli_baglam else None))

    # Yönetici Özeti (TL;DR) — modalda görünür, Jira'ya YAZILMAZ (gorev_jiraya_yaz keser).
    ozet = yonetici_ozeti_olustur(teknik, acik_sorular=acik)
    teknik = yonetici_ozetini_cikar(teknik)   # modelin kendi özeti gövdeden çıkar (tek blok)
    return {"markdown": ozet + teknik, "acik_sorular": acik}


def _ornek_kendisi_mi(blok: dict, key: str) -> bool:
    """Few-shot bloğu bu task'ın kendi (key ya da key::FE) örneği mi? Etiket satırı '· <jira_key>' ile biter."""
    key = (key or "").strip().upper()
    if not key:
        return False
    ilk = str((blok or {}).get("text", "")).split("\n", 1)[0].upper()
    return re.search(r"·\s*" + re.escape(key) + r"(?:::FE)?\s*$", ilk) is not None


def _soru_asamasi(teknikler: list[str], gorev: dict, *, cevaplar: str = "", onceki_sorular: str = "",
                  canli: bool = False, gozlem_rapor: dict | None = None, rag_ctx: dict | None = None,
                  canli_kapsam: str | None = None) -> tuple[list[str], str]:
    """Açık sorular (haiku) → öz-çözümleme (kanıt + tek canlı tur) → kanıtla cevaplananları analize işle.
    `teknikler` birden çoksa (FE+BE) sorular TÜM katmanlar üzerinden TEK kez üretilir/çözülür; otomatik işleme her
    katmana ayrı ucuz hedefli düzeltme olarak uygulanır (canlı çözüm turu tek). Dönen: (güncel teknikler, acik)."""
    acik = ""
    soru_metni = teknikler[0] if len(teknikler) == 1 else "\n\n---\n\n".join(
        f"### Katman analizi {i + 1}\n\n{t}" for i, t in enumerate(teknikler))
    try:
        acik = _gorev_acik_sorular_uret(soru_metni, gorev, cevaplar=cevaplar, onceki_sorular=onceki_sorular,
                                        gozlem_rapor=gozlem_rapor)
    except Exception as e:
        print(f"  ⚠ Görev açık soruları üretilemedi: {e}")
    if not (acik and acik.strip()):
        return teknikler, acik
    # Aşama 2b — ÖZ-ÇÖZÜMLEME: analist görmeden önce agent her soruyu referans/kod/tüketici taramasıyla ve gerekirse
    # tek canlı gözlem turuyla araştırır; cevaplananlar UI'da önceden dolu gelir (analiz yeniden yazılmaz).
    try:
        from . import soru_cozumleme as _sc
        if not _sc.acik_mi():
            return teknikler, acik
        acik = _sc.cozumle(acik, gorev, canli=canli, rag_ctx=rag_ctx, canli_kapsam=canli_kapsam)
        # Aşama 2c — kanıtla CEVAPLANAN sorular analize OTOMATİK işlenir (tek ucuz hedefli düzeltme; referans/gözlem yok)
        # ve listeden düşer; yalnız 'kısmen' + 'karar gerekli' analiste kalır.
        if _sc.uygula_acik_mi():
            kalan, cozulen = _sc.cozulenleri_ayir(acik)
            if cozulen:
                guncel = list(teknikler)
                basarili = 0
                for i, teknik in enumerate(teknikler):
                    try:
                        print(f"  ✍️  {len(cozulen)} çözülen soru analize işleniyor (hedefli düzeltme)...")
                        _rag, _govde = _rag_yorum_ayir(teknik)
                        _yeni = gorev_analiz_duzelt(gorev, _govde, _sc.uygulama_talimati(cozulen))
                        if _yeni and len(_yeni) > 0.5 * len(_govde):
                            guncel[i] = _rag + _yeni
                            basarili += 1
                        else:
                            print("  ⚠ Düzeltme çıktısı güvenilmez (çok kısa) — sorular ön-dolu bırakıldı.")
                    except Exception as e:
                        print(f"  ⚠ Çözülen sorular analize işlenemedi (ön-dolu bırakıldı): {str(e)[:160]}")
                if basarili == len(teknikler):
                    teknikler = guncel
                    acik = (kalan + ("\n\n" if kalan else "") + _sc.cozulen_bolumu(cozulen)).strip()
    except Exception as e:
        print(f"  ⚠ Açık soru öz-çözümleme atlandı: {e}")
    return teknikler, acik


_SOZLESME_BASLIK = re.compile(r"(?im)^#{1,4}\s+[^\n]*(ba[ğg][ıi]ml[ıi]l[ıi]k|aray[üu]z|\bapi\b|endpoint|s[öo]zle[şs]me)[^\n]*$")
_FE_GIRDI_TAVAN = 6_000


def _fe_icin_be_sozlesme(be_markdown: str) -> str:
    """FE analizine 'karşı katman' bağlamı olarak giren BE metni. `gorev_analiz_et` ilişkili açıklamayı BAŞTAN 4000
    karaktere kırpar → sonda duran `## Bağımlılık ve Arayüz (FE↔BE)` sözleşmesi kaybolurdu. Burada: özet + RAG yorumu
    atılır, sözleşme/arayüz/API bölümleri ÖNE alınır, kalan yer gövdeden doldurulur (toplam ≤ ~6k)."""
    govde = _rag_yorum_ayir(yonetici_ozetini_cikar(be_markdown or ""))[1].strip()
    if not govde:
        return ""
    from .revizyon_ai import bolumlere_ayir
    try:
        bolumler = [b for b in bolumlere_ayir(govde) if b["seviye"] > 0]
    except Exception:
        bolumler = []
    sozlesme = [b["icerik"].strip() for b in bolumler if _SOZLESME_BASLIK.search(b["icerik"].split("\n", 1)[0])]
    if not sozlesme:
        return govde if len(govde) <= _FE_GIRDI_TAVAN else "…(baş kırpıldı)\n" + govde[-_FE_GIRDI_TAVAN:]
    on = ("### BE SÖZLEŞMESİ (FE'nin tükettiği arayüz — önce bunu kullan)\n\n" + "\n\n".join(sozlesme))[:_FE_GIRDI_TAVAN]
    kalan = _FE_GIRDI_TAVAN - len(on)
    if kalan > 400:
        on += "\n\n### BE analizi (özet)\n\n" + govde[:kalan]
    return on


def gorev_fe_be_analiz(gorev: dict, cevaplar: str = "", onceki_sorular: str = "",
                       ekran_baglami: bool = True, rag_ctx: dict | None = None,
                       canli_baglam_override: str | None = None, bff_rapor: str | None = None,
                       canli_kapsam: str | None = None) -> dict:
    """Tek bir görevi HEM BE HEM FE olarak İKİ AYRI katman-özel analize böler (görev hem
    sunucu hem istemci işi içeriyorsa). Önce **BE** analizi (veri modeli/endpoint/iş kuralı +
    'Bağımlılık ve Arayüz' başlığında BE'nin SUNDUĞU sözleşme), sonra **FE** analizi — BE
    sözleşmesini KARŞI-KATMAN bağlamı olarak alır, BE'nin iç implementasyonunu TEKRARLAMAZ,
    yalnız tükettiği arayüzü yazar. İki içerik ayrışır → 'aynı analiz iki taskta' sorunu çözülür.
    Dönen: {"be": {markdown, acik_sorular}, "fe": {markdown, acik_sorular}}."""
    # Faz 1 (kota): TEK gözlem raporu, iki analiz (eskiden BE ve FE ayrı ayrı gözlüyordu → iki döngü).
    gozlem_rapor = None
    kapsam = canli_kapsam or ("surec" if canli_baglam_override is not None else "gorev")
    _canli = canli_baglam_override if canli_baglam_override is not None else canli_uygulama_baglami_hazirla(gorev=True)
    if _canli:
        from . import gozlem as _gz
        gozlem_rapor = _gz.rapor_al(_canli, kapsam,
                                   gorev_ozet=f"{gorev.get('summary', '')}\n\n{gorev.get('description', '') or ''}",
                                   yeniden=not bool((cevaplar or "").strip() or (onceki_sorular or "").strip()))
        if not ((gozlem_rapor or {}).get("md") and (gozlem_rapor or {}).get("ok")):
            gozlem_rapor = {"ok": False, "md": "", "neden": (gozlem_rapor or {}).get("neden", "")}
    ortak = dict(cevaplar=cevaplar, onceki_sorular=onceki_sorular, ekran_baglami=ekran_baglami, rag_ctx=rag_ctx,
                 canli_baglam_override=canli_baglam_override, bff_rapor=bff_rapor, gozlem_rapor=gozlem_rapor,
                 canli_kapsam=kapsam, soru_asamasi=False)   # soru aşaması aşağıda İKİ katman için TEK kez
    be = gorev_analiz_et(gorev, katman="be", **ortak)
    # FE, BE'nin ürettiği FE↔BE sözleşmesini bağlam alsın (aynı görevin karşı katmanı) — sözleşme bölümü ÖNE alınır,
    # yoksa 4000 karakterlik baş-kırpmada (Yönetici Özeti önce) sondaki sözleşme kaybolurdu.
    be_baglam = {"key": gorev.get("key", ""),
                 "summary": (gorev.get("summary", "") + " — BE tarafı (sözleşme)"),
                 "description": _fe_icin_be_sozlesme(be.get("markdown", "")), "katman": "be"}
    fe = gorev_analiz_et(gorev, katman="fe", iliskili=[be_baglam], **ortak)
    # Açık sorular + öz-çözümleme + otomatik işleme: iki katman üzerinden TEK kez (canlı çözüm turu bir kez koşar).
    be_md, fe_md = yonetici_ozetini_cikar(be.get("markdown", "")), yonetici_ozetini_cikar(fe.get("markdown", ""))
    (be_md, fe_md), acik = _soru_asamasi([be_md, fe_md], gorev, cevaplar=cevaplar, onceki_sorular=onceki_sorular,
                                         canli=bool(_canli), gozlem_rapor=gozlem_rapor,
                                         rag_ctx=(rag_ctx if not ekran_baglami else None),
                                         canli_kapsam=(kapsam if _canli else None))
    be_md = yonetici_ozeti_olustur(be_md, acik_sorular=acik) + be_md
    fe_md = yonetici_ozeti_olustur(fe_md, acik_sorular=acik) + fe_md
    # is_var ÖNCE parse edilir (satır dururken); sonra '**Bu katmanda iş:**' göstergesi analist çıktısından ÇIKARILIR
    # (owner 2026-10-21: bu alan analiz çıktısında olmamalı — UI katman ön-işareti için is_var alanı yeter).
    be_is, fe_is = katman_is_var_mi(be_md), katman_is_var_mi(fe_md)
    return {"be": {"markdown": katman_satiri_cikar(be_md), "acik_sorular": acik, "is_var": be_is},
            "fe": {"markdown": katman_satiri_cikar(fe_md), "acik_sorular": acik, "is_var": fe_is}}


_KATMAN_IS = re.compile(r"\*\*\s*Bu katmanda iş\s*:?\s*\*\*\s*:?\s*(VAR|YOK)\b", re.I)
# Göstergeyi SATIR olarak çıkarır (önündeki yalnız '---' ayıracı ortada kalırsa onu da yut).
_KATMAN_SATIR = re.compile(r"(?mi)^[ \t]*(?:---[ \t]*\n)?[ \t]*[-*•]?[ \t]*\*{0,2}Bu katmanda iş\s*:?\*{0,2}.*(?:\n|$)")


def katman_is_var_mi(markdown: str):
    """FE+BE ayrı analizin başındaki `**Bu katmanda iş:** VAR|YOK` satırı → True/False; satır yoksa None.
    UI bu değere göre katman kutusunu ön-işaretler (YOK → işaretsiz + 'agent: bu katmanda iş yok' notu)."""
    m = _KATMAN_IS.search(markdown or "")
    if not m:
        return None
    return m.group(1).upper() == "VAR"


def katman_satiri_cikar(markdown: str) -> str:
    """`**Bu katmanda iş:** VAR|YOK …` göstergesini analiz GÖVDESİNDEN çıkarır (owner 2026-10-21: analiz çıktısında
    olmamalı). is_var ayrı alanda taşınır; UI katman ön-işareti ondan beslenir. Fazla boş satır toparlanır."""
    if not markdown:
        return markdown
    m = _KATMAN_SATIR.sub("", markdown)
    return re.sub(r"\n{3,}", "\n\n", m)


def gorev_fe_be_task_olustur(key: str, be_markdown: str, fe_markdown: str,
                             summary: str = "", katmanlar=("be", "fe")) -> dict:
    """FE+BE bölünmüş analizi Jira'ya yazar — KATMAN SEÇİMLİ (owner isteri: bazen yalnız FE ya da yalnız BE):
    - 'be' seçiliyse **BE** analizi ORİJİNAL task'a yazılır, başlık 'BE - <özet>' önekli.
    - 'fe' seçiliyse **FE** analizi YENİ bir Task olarak açılır, başlık 'FE - <özet>'.
    - İKİSİ seçiliyse **BE → FE Blocks** bağı kurulur; YALNIZ FE'de yeni task kaynak task'a **Relates** ile bağlanır
      (izlenebilirlik; BE task'ı olmadığından Blocks yok). Yalnız BE'de yeni task açılmaz.
    Her task YALNIZ kendi katman analizini içerir. Dönen: {be_key|None, fe_key|None, link, link_uyari, katmanlar}."""
    from .jira_tasks import _issue_olustur, _proje_bilgi, _katman_prefix
    from .jira_fe_be import _blocks_bagla, _blocks_link_tipi
    key = (key or "").strip().upper()
    if not _ID_DESENI.match(key):
        raise ValueError(f"Geçersiz Jira anahtarı: '{key}'")
    kat = [k for k in ("be", "fe") if k in {str(x).strip().lower() for x in (katmanlar or ())}]
    if not kat:
        raise ValueError("En az bir katman seçilmeli (BE ve/veya FE).")
    if "be" in kat and not (be_markdown or "").strip():
        raise ValueError("BE analizi boş — 'BE'yi yaz' seçildi.")
    if "fe" in kat and not (fe_markdown or "").strip():
        raise ValueError("FE analizi boş — 'FE task'ı aç' seçildi.")
    orig = gorev_getir(key) or {}
    ozet = (summary or orig.get("summary", "")).strip() or key
    cloud_id = _cloud_id()
    be_key = fe_key = None
    link_ok, link_uyari = False, ""

    # 1) BE → orijinal task (başlık 'BE - ' önekli, idempotent). Owner kararı 2026-10-21: task'a YALNIZ temiz
    #    teknik analiz yazılır — '## 📌 Orijinal Talep' + '## 🤖 Teknik Analiz (Analyst Agent)' wrapper EKLENMEZ
    #    (orijinal_koru=False). Agent iskelesi (Bu katmanda iş / Kaynak Görev) zaten jira_icin_temizle'de silinir.
    if "be" in kat:
        gorev_jiraya_yaz(key, be_markdown, summary=_katman_prefix("be", ozet), orijinal_koru=False)
        be_key = key

    # 2) FE → yeni Task (aynı temizlik: TL;DR + canlı gözlem + [K:] etiketleri çıkarılır)
    if "fe" in kat:
        fe_temiz = jira_icin_temizle(fe_markdown or "")
        adf = markdown_to_adf(fe_temiz)
        if not adf:
            raise ValueError("FE içeriği boş; yeni task açılamadı.")
        proje = key.split("-")[0]
        pbilgi = _proje_bilgi(proje, cloud_id)
        task_id = pbilgi.get("task_id")
        if not task_id:
            raise ValueError(f"'{proje}' projesinde Task tipi bulunamadı.")
        fe_key = _issue_olustur(_katman_prefix("fe", ozet),
                                {"type": "doc", "version": 1, "content": adf},
                                task_id, proje, cloud_id)
        if "be" in kat:
            # 3) BE (orijinal) → FE Blocks bağı (link tipi runtime doğrulanır; yoksa uyarıyla atlanır)
            tip = _blocks_link_tipi(cloud_id)
            if tip:
                try:
                    _blocks_bagla(key, fe_key, tip, cloud_id)
                    link_ok = True
                except Exception as e:
                    link_uyari = f"Blocks bağı kurulamadı: {str(e)[:120]}"
            else:
                link_uyari = "Projede 'Blocks' link tipi yok — bağ atlandı."
        else:
            # Yalnız FE: kaynak task'a Relates (BE task'ı yok → Blocks anlamsız)
            try:
                from .jira_kopru import jira_issue_link
                jira_issue_link(fe_key, key, tip="Relates")
                link_ok = True
            except Exception as e:
                link_uyari = f"Kaynak task bağı kurulamadı: {str(e)[:120]}"
    return {"be_key": be_key, "fe_key": fe_key, "link": link_ok, "link_uyari": link_uyari, "katmanlar": kat}


def _analiz_adf(markdown: str) -> dict:
    """Analiz markdown'ını Jira gövdesine uygun ADF'ye çevirir (aynı temizlik:
    TL;DR + canlı gözlem kapsamı + [K:] kanıt etiketleri çıkarılır)."""
    temiz = jira_icin_temizle(markdown or "")
    adf = markdown_to_adf(temiz)
    if not adf:
        raise ValueError("İçerik boş; task açılamadı.")
    return {"type": "doc", "version": 1, "content": adf}


def issue_ozet(key: str) -> dict:
    """Bir Jira issue'nun özet bilgisini döndürür (üst öğe doğrulaması için):
    {key, summary, tip, proje}. Bulunamazsa RuntimeError/ValueError."""
    from .atlassian import atlassian_get
    key = (key or "").strip().upper()
    if not _ID_DESENI.match(key):
        raise ValueError(f"Geçersiz Jira anahtarı: '{key}'")
    cloud_id = _cloud_id()
    data = atlassian_get(f"/rest/api/3/issue/{key}?fields=summary,issuetype,project", cloud_id)
    f = data.get("fields", {}) or {}
    return {
        "key": data.get("key", key),
        "summary": f.get("summary", ""),
        "tip": ((f.get("issuetype") or {}).get("name", "")),
        "proje": ((f.get("project") or {}).get("key", "")),
    }


def gorev_yeni_task_olustur(proje: str, mode: str = "tek", markdown: str = "",
                            be_markdown: str = "", fe_markdown: str = "",
                            baslik: str = "", ust_key: str = "",
                            kaynak_key: str = "") -> dict:
    """Analiz OK sonrası YENİ Task(lar) açar (hep **Task** tipinde; analist sonra
    tipini değiştirebilir) ve girilen Epic/Story/Task'a **ilişkili** (Relates) bağlar.

    - mode='tek'   → tek Task; gövde=markdown.
    - mode='fe-be' → İKİ yeni Task (BE + FE, başlıkları 'BE - '/'FE - ' önekli);
                     ikisi birbirine (Blocks varsa Blocks, yoksa Relates) bağlanır.
    - mode='be'|'fe' → FE+BE setinden YALNIZ o katman için tek yeni Task (önekli); gövde=markdown.
    Her açılan task, verilmişse üst öğeye (ust_key) ve kaynak analiz task'ına
    (kaynak_key) Relates ile bağlanır. Üst öğe hiyerarşi 'parent'ı DEĞİL — Task,
    Story'nin child'ı olamaz; 'ilişkili' istendiği için issue-link kullanılır.

    Dönen: {tasklar:[{key,katman,summary}], ust_key, febe_link, uyarilar:[...]}.
    """
    from .jira_tasks import _issue_olustur, _proje_bilgi, _katman_prefix
    from .jira_fe_be import _blocks_bagla, _blocks_link_tipi
    from .jira_kopru import jira_issue_link

    proje = (proje or "").strip().upper()
    if not proje:
        raise ValueError("Proje seçilmedi.")
    cloud_id = _cloud_id()
    pbilgi = _proje_bilgi(proje, cloud_id)
    task_id = pbilgi.get("task_id")
    if not task_id:
        raise ValueError(f"'{proje}' projesinde 'Task' tipi bulunamadı.")

    ust_key = (ust_key or "").strip().upper()
    kaynak_key = (kaynak_key or "").strip().upper()
    if kaynak_key and (kaynak_key.startswith("EKRAN-") or not _ID_DESENI.match(kaynak_key)):
        kaynak_key = ""   # sentetik kaynak (İnteraktif Analiz ekran kaydı EKRAN-n) → Jira'da yok, bağ kurulmaz
    if ust_key and not _ID_DESENI.match(ust_key):
        raise ValueError(f"Geçersiz üst öğe anahtarı: '{ust_key}'")
    ozet = (baslik or "").strip() or "Yeni görev"
    uyarilar: list[str] = []
    tasklar: list[dict] = []

    def _baglan(yeni_key: str) -> None:
        # Üst öğe (epic/story/task) ilişkisi — Relates (yeni task ilgili öğeye bağlı)
        if ust_key and ust_key != yeni_key:
            try:
                jira_issue_link(yeni_key, ust_key, tip="Relates")
            except Exception as e:
                uyarilar.append(f"{yeni_key} → {ust_key} bağı kurulamadı: {str(e)[:100]}")
        # Kaynak analiz task'ı ilişkisi (izlenebilirlik) — best-effort
        if kaynak_key and kaynak_key not in (yeni_key, ust_key):
            try:
                jira_issue_link(yeni_key, kaynak_key, tip="Relates")
            except Exception:
                pass

    if mode == "fe-be":
        if not (be_markdown or "").strip() or not (fe_markdown or "").strip():
            raise ValueError("BE ve FE analizleri dolu olmalı.")
        # BE ÖNCE (blocker), sonra FE — deterministik sıra
        be_key = _issue_olustur(_katman_prefix("be", ozet), _analiz_adf(be_markdown),
                                task_id, proje, cloud_id)
        tasklar.append({"key": be_key, "katman": "BE", "summary": _katman_prefix("be", ozet)})
        fe_key = _issue_olustur(_katman_prefix("fe", ozet), _analiz_adf(fe_markdown),
                                task_id, proje, cloud_id)
        tasklar.append({"key": fe_key, "katman": "FE", "summary": _katman_prefix("fe", ozet)})
        # BE ↔ FE bağı — 'Blocks' varsa BE bloklar FE, yoksa Relates (ASLA atlanmaz)
        febe_link = False
        tip = _blocks_link_tipi(cloud_id)
        try:
            if tip:
                _blocks_bagla(be_key, fe_key, tip, cloud_id)
            else:
                jira_issue_link(be_key, fe_key, tip="Relates")
            febe_link = True
        except Exception as e:
            uyarilar.append(f"BE↔FE bağı kurulamadı: {str(e)[:100]}")
        _baglan(be_key)
        _baglan(fe_key)
        return {"tasklar": tasklar, "ust_key": ust_key, "febe_link": febe_link, "uyarilar": uyarilar}

    if mode in ("be", "fe"):
        # TEK KATMAN (FE+BE setinden yalnız biri): katman önekli tek yeni task; üst öğe + kaynak task'a Relates
        if not (markdown or "").strip():
            raise ValueError(f"{mode.upper()} analizi boş.")
        yeni_key = _issue_olustur(_katman_prefix(mode, ozet), _analiz_adf(markdown), task_id, proje, cloud_id)
        tasklar.append({"key": yeni_key, "katman": mode.upper(), "summary": _katman_prefix(mode, ozet)})
        _baglan(yeni_key)
        return {"tasklar": tasklar, "ust_key": ust_key, "febe_link": None, "uyarilar": uyarilar}

    # mode == "tek"
    if not (markdown or "").strip():
        raise ValueError("Analiz içeriği boş.")
    yeni_key = _issue_olustur(ozet, _analiz_adf(markdown), task_id, proje, cloud_id)
    tasklar.append({"key": yeni_key, "katman": "", "summary": ozet})
    _baglan(yeni_key)
    return {"tasklar": tasklar, "ust_key": ust_key, "febe_link": None, "uyarilar": uyarilar}


_GOREV_DUZELT_SISTEM = (
    "Kıdemli teknik analistsin. Sana MEVCUT bir Jira görev teknik analizi + tek bir DÜZELTME TALİMATI "
    "verilecek. Talimatın istediği kısmı düzelt; DOKUNULMAYAN bölümleri AYNEN koru — yeniden yazma, "
    "kısaltma, başlık değiştirme. Aynı Markdown biçimini, bölüm başlıklarını ve ID şemasını koru. "
    "Doğruluk, gözlemlenebilirlik ve spekülasyon-yasağı kurallarını GEVŞETME (gözleyemediğini uydurma). "
    "Tüm (güncellenmiş) analizi eksiksiz olarak <teknik_analiz>…</teknik_analiz> içinde dön."
)


_RAG_YORUM = re.compile(r"<!--\s*RAG:[^>]*-->[ \t]*\n?")


def _rag_yorum_ayir(teknik: str) -> tuple[str, str]:
    """`<!-- RAG: … -->` yorumunu gövdeden ayırır (düzeltme çağrısına gitmesin, sonra geri konsun). Yorum metnin
    başında olmayabilir (önünde Yönetici Özeti varsa) → İLK 3 SATIR içinde aranır; dönen gövde yorumdan arındırılmıştır."""
    t = teknik or ""
    parcalar = t.split("\n", 3)
    on = "\n".join(parcalar[:3])
    m = _RAG_YORUM.search(on)
    if not m:
        return "", t
    yorum = m.group(0).rstrip("\n") + "\n\n"
    return yorum, (t[:m.start()] + t[m.end():]).lstrip("\n")


def _govde_ayir(markdown: str) -> tuple[str, bool, str]:
    """(rag_yorum, ozet_vardi, saf_govde) — Yönetici Özeti + RAG yorumu düzeltme çağrısına GİTMEZ (özet eskiden
    analizle birlikte modele gidip 'eski özet' olarak geri geliyor, sayaçlar yenilenmiyordu)."""
    md = markdown or ""
    ozetsiz = yonetici_ozetini_cikar(md)
    ozet_vardi = ozetsiz.strip() != md.strip()
    rag, govde = _rag_yorum_ayir(ozetsiz)
    return rag, ozet_vardi, govde


def gorev_analiz_duzelt(gorev: dict, mevcut_markdown: str, talimat: str, asama: str = "gorev:duzelt",
                        acik_sorular: str = "") -> str:
    """İteratif düzeltme: mevcut teknik analiz + talimat → yalnız ilgili kısmı düzeltilmiş tam analiz.
    HTML prototip 'sohbetle düzelt' deseninin görev-analizi karşılığı. Jira'ya YAZMAZ (önizleme).
    Girdideki Yönetici Özeti + `<!-- RAG -->` yorumu modele GİTMEZ; özet vardıysa çıktıda deterministik olarak
    YENİDEN üretilir, RAG yorumu geri konur. `asama`: telemetri etiketi (cevap turu 'gorev:cevap' geçer)."""
    talimat = (talimat or "").strip()
    if not talimat:
        raise ValueError("Düzeltme talimatı boş.")
    rag, ozet_vardi, mevcut = _govde_ayir(mevcut_markdown)
    mevcut = mevcut.strip()
    if not mevcut:
        raise ValueError("Düzeltilecek analiz yok.")
    # NOT: girdi etiketleri markdown BAŞLIĞI (`### …`) OLMAMALI — model başlığı bir bölüm sanıp ÇIKTIYA kopyalıyordu
    # (`### Kaynak Görev: …` her düzelt turunda birikiyordu, FE 2x/BE 4x). Düz etiket + 'çıktıya ekleme' notu.
    icerik = [
        {"type": "text", "text": f"[MEVCUT TEKNİK ANALİZ — düzeltilecek metin]\n\n{mevcut}"},
        {"type": "text", "text": f"[Kaynak görev bağlamı — SADECE BİLGİ, ÇIKTIYA YAZMA]: {gorev.get('key','')} — {gorev.get('summary','')}"},
        {"type": "text", "text": f"[DÜZELTME TALİMATI — yalnız bunu uygula]\n{talimat}"},
    ]
    asama_ayarla(asama or "gorev:duzelt")
    yanit = _api_cagri(_GOREV_DUZELT_SISTEM, [{"role": "user", "content": icerik}],
                       max_tokens=MAX_TOKENS_COMBINED, thinking=extended_thinking_acik(), katman="yardimci")
    yeni = _meta_notlari_temizle(_xml_ayir(_metin_sikistir(yanit), "teknik_analiz"))
    if not yeni.strip():
        return yeni
    yeni = yonetici_ozetini_cikar(yeni)
    if ozet_vardi:
        yeni = yonetici_ozeti_olustur(yeni, acik_sorular=acik_sorular or "") + yeni
    return rag + yeni


def cevap_hedefli_acik() -> bool:
    """Kota Faz 2: 'Cevapları İşle' analizi BAŞTAN üretmek yerine hedefli düzeltme ile işler. `CEVAP_HEDEFLI=false` kapatır."""
    return os.getenv("CEVAP_HEDEFLI", "true").strip().lower() not in ("0", "false", "no", "hayir", "hayır")


_CEVAP_TALIMAT = (
    "Analistin aşağıdaki CEVAPLARINI analize İŞLE (cevaplanan her soru için):\n"
    "- Sorunun ilgilendirdiği bölümü bul; oradaki `[K: ❓ Belirsiz]` / `⚠ VARSAYIM` / 'netleştirilmeli' ifadelerini kaldır ve "
    "analistin cevabını KESİN bilgi olarak, `[K: Analist cevabı]` etiketiyle yaz (endpoint/alan/kural/akış etkisi dahil).\n"
    "- Cevabın gerektirdiği küçük tutarlılık düzeltmelerini (kabul kriteri, akış adımı, hata durumu) AYNI bölümlerde yap.\n"
    "- Açık Sorular bölümü varsa cevaplanan soruları oradan ÇIKAR; kalanları aynen bırak.\n"
    "- Cevapla ilgisiz hiçbir bölüme, başlığa, numaralandırmaya DOKUNMA; analizi kısaltma/genişletme; yeniden yazma.\n\n"
    "### ANALİSTİN CEVAPLARI\n")


def gorev_cevap_uygula(gorev: dict, mevcut_markdown: str, cevaplar: str, onceki_sorular: str = "") -> dict:
    """Kota Faz 2 — 'Cevapları İşle' HEDEFLİ: analizi baştan üretmek (tam bağlam + gözlem + öz-çözümleme = ~3-4 büyük
    çağrı) yerine (1) mevcut analize cevapları `gorev_analiz_duzelt` ile işler (yardımcı katman, küçük prompt),
    (2) kalan açık soruları `_gorev_acik_sorular_uret` ile YAKINSAR (hafif katman). Canlı gözlem/RAG YENİDEN YAPILMAZ —
    cevaplar yeni gözlem gerektirmeyen analist bilgisidir. Mevcut analiz yoksa ValueError → çağıran tam üretime düşer.
    Dönen: {markdown, acik_sorular, hedefli: True}."""
    cevaplar = (cevaplar or "").strip()
    if not cevaplar:
        raise ValueError("Cevap metni boş.")
    if not (mevcut_markdown or "").strip():
        raise ValueError("Cevap uygulanacak mevcut analiz yok.")
    rag, ozet_vardi, govde = _govde_ayir(mevcut_markdown)
    yeni = gorev_analiz_duzelt(gorev, govde, _CEVAP_TALIMAT + cevaplar, asama="gorev:cevap")
    if not yeni.strip():
        raise ValueError("Cevap uygulama boş sonuç döndü.")
    yeni = yonetici_ozetini_cikar(yeni)
    acik = ""
    try:
        acik = _gorev_acik_sorular_uret(yeni, gorev, cevaplar=cevaplar, onceki_sorular=onceki_sorular or "")
    except Exception as e:
        print(f"  ⚠ Kalan açık sorular üretilemedi (cevaplar yine de işlendi): {str(e)[:120]}")
    # Özet (açık soru sayacı dahil) GÜNCEL gövde + KALAN sorulardan yeniden kurulur; RAG yorumu geri konur.
    ozet = yonetici_ozeti_olustur(yeni, acik_sorular=acik) if ozet_vardi else ""
    return {"markdown": rag + ozet + yeni, "acik_sorular": acik, "hedefli": True}


def _gorev_acik_sorular_uret(teknik_metni: str, gorev: dict,
                             cevaplar: str = "", onceki_sorular: str = "",
                             gozlem_rapor: dict | None = None) -> str:
    """Aşama-2 açık sorular: üretilen teknik analiz + görev + (varsa) ÖNCEKİ tur soruları/cevapları.
    Amaç: geliştirmeyi GERÇEKTEN bloklayan soruları toplamak ve TURLAR İÇİNDE YAKINSAMAK — her turda
    AZALMALI, birkaç turda bitmeli (drift/tekrar yok). Haiku — ucuz. Boşsa UI'da panel gizlenir."""
    takip = bool(cevaplar.strip() or onceki_sorular.strip())
    asama_ayarla("gorev:sorular")
    sistem = (
        "Kıdemli teknik analistsin. Sana üretilmiş bir teknik analiz + Jira görevi (ve varsa ÖNCEKİ TUR "
        "açık soruları + analistin CEVAPLARI) verilir. Amaç: geliştiricinin başlamasını GERÇEKTEN "
        "ENGELLEYEN açık soruları toplamak ve TURLAR İÇİNDE YAKINSAMAK — her turda soru sayısı AZALMALI, "
        "birkaç turda BİTMELİ.\n\n"
        "YAKINSAMA KURALLARI (EN ÖNEMLİSİ — önceki tur verildiyse):\n"
        "- Analistin CEVAPLADIĞI ya da artık analizde cevabı BULUNAN her soruyu ÇIKAR — bir daha SORMA, "
        "yeniden İFADE ETME, bölerek/çoğaltarak geri getirme.\n"
        "- Hâlâ gerçekten açık kalan önceki soruları AYNI ID ve AYNI metinle KORU (yeniden yazma).\n"
        "- YALNIZ verilen cevapların ORTAYA ÇIKARDIĞI, bloklayan YENİ bir belirsizlik varsa ekle (yeni ID).\n"
        "- Reworded/benzer soru ÜRETME. Kalanlar bloklamıyorsa 'Açık soru tespit edilmedi.' dön.\n\n"
        "GENEL KURALLAR:\n"
        "- Yalnız `[K: ❓ Belirsiz]`/`⚠ VARSAYIM` işaretli VE geliştirmeyi BLOKLAYAN konular soru olur; "
        "tercihe bağlı/kozmetik/küçük konu için SORU ÜRETME.\n"
        "- Önem: Kritik/Yüksek öncelikli; Orta/Düşük ancak gerçekten gerekiyorsa. **EN FAZLA 6 soru.**\n"
        "- Cevapsız kalırsa veri kaybı/bozulması, başka ekran/rapor/entegrasyonun kırılması ya da testin beklenen "
        "sonucunun bilinmemesi doğacaksa (özellikle veri değişikliği etkisi ve akışın tanımsız dalları) soruya `- Zorunlu: Evet` "
        "satırı ekle; diğerlerine yazma. Zorunlu sorular yakınsamada da cevaplanana kadar KORUNUR.\n"
        "- Soru bağımsız cevaplanabilir, tek konuya odaklı olmalı.\n"
        "- Hiç bloklayan belirsizlik yoksa SADECE şu satırı dön: 'Açık soru tespit edilmedi.'\n\n"
        "Çıktı Türkçe Markdown, XML bloğu içinde:\n\n"
        "<acik_sorular>\n"
        "### Q-T-001: [Başlık]\n"
        "- Önem: Kritik / Yüksek / Orta / Düşük\n"
        "- Zorunlu: Evet (yalnız zorunluysa)\n"
        "- Bağlı bölüm: [§5 API / §4 DB / vb.]\n"
        "- Soru: [tek cümle]\n"
        "- Beklenen yanıt: [alan tipi / değer kümesi / karar]\n"
        "</acik_sorular>"
    )
    icerik = [
        {"type": "text", "text": f"### Üretilen Teknik Analiz\n\n{teknik_metni}"},
        {"type": "text", "text": f"### Kaynak Jira Görevi: {gorev.get('key','')}\n\n"
                                 f"**Başlık:** {gorev.get('summary','')}\n\n"
                                 f"**Açıklama:**\n{gorev.get('description','') or '(açıklama yok)'}"},
    ]
    if gozlem_rapor and gozlem_rapor.get("ok") and gozlem_rapor.get("md"):
        # Gözlem↔referans çelişkileri (analizde `[K: ❓ Belirsiz]`) bloklayıcıysa soruya dönüşsün — analiz çağrısı
        # Açık Sorular üretmediğinden çelişki yalnız burada soruya çevrilebilir.
        from .gozlem import rapor_soru_blogu
        icerik.append({"type": "text", "text": rapor_soru_blogu(gozlem_rapor)})
    if onceki_sorular.strip():
        icerik.append({"type": "text", "text": (
            "### ÖNCEKİ TUR AÇIK SORULAR (yakınsama için — cevaplanan/çözülenleri ÇIKAR; kalan gerçekten "
            "açık olanları AYNI ID+metinle koru; benzerini yeniden üretme)\n\n" + onceki_sorular.strip())})
    if cevaplar.strip():
        icerik.append({"type": "text", "text": (
            "### ANALİSTİN CEVAPLARI (bu konular ARTIK KAPALI — tekrar SORMA)\n\n" + cevaplar.strip())})
    icerik.append({"type": "text", "text": (
        "Yakınsama kurallarına göre KALAN gerçekten bloklayan açık soruları üret (mümkün olduğunca AZ)."
        if takip else "Geliştirmeyi gerçekten bloklayan açık konuları (en fazla 6) soru olarak topla.")})
    # canli_uygulama_kapsami verilmiyor: bu aşama zaten üretilmiş teknik analiz
    # metnini özetler, hiçbir browsing talimatı içermez — canlı uygulama hiç açılmaz.
    yanit = _api_cagri(sistem, [{"role": "user", "content": icerik}],
                       model=MODEL_HAFIF, max_tokens=MAX_TOKENS_KISA, thinking=False)
    acik = _xml_ayir(_metin_sikistir(yanit), "acik_sorular")
    # DETERMİNİSTİK YAKINSAMA (owner 2026-10-21: 'cevap girdim ama aynı soruyu tekrar çıkarıyor'):
    # Analistin CEVAPLADIĞI soru ID'lerini model ne derse desin ELE — reworded olsa da aynı ID geri gelmesin.
    return _cevaplanan_sorulari_dus(acik, cevaplar)


_SORU_BASLIK = re.compile(r"(?mi)^#{1,4}\s*(Q-?T?-?\d+)\b")
_CEVAP_ID = re.compile(r"(?mi)^\s*[-*•]?\s*\*{0,2}(Q-?T?-?\d+)\*{0,2}\s*[:\-–]")


def _cevaplanan_sorulari_dus(acik: str, cevaplar: str) -> str:
    """Analistin cevapladığı (cevaplar metninde `Q-T-00n:` ile başlayan, boş olmayan) soru ID'lerinin
    `### <ID>:` bloklarını açık sorulardan çıkarır — model yakınsamada bırakmış olsa da. ID normalize edilir
    (Q-T-1 == Q-T-001 == QT1) → reworded ama AYNI ID geri gelmez. Yeni ID'li gerçek yeni soru korunur."""
    if not (acik or "").strip() or not (cevaplar or "").strip():
        return acik

    def _norm(i: str) -> str:
        m = re.search(r"T?-?(\d+)", i.upper().replace(" ", ""))
        t = "T" if "T" in i.upper() else ""
        return f"Q{t}{int(m.group(1))}" if m else i.upper()

    cevaplanan = {_norm(m.group(1)) for m in _CEVAP_ID.finditer(cevaplar)}
    if not cevaplanan:
        return acik
    # Blokları `### <ID>:` başlıklarından böl; cevaplanan ID'li blokları at (başlıksız giriş metni korunur).
    parcalar = re.split(r"(?mi)(^#{1,4}\s*Q-?T?-?\d+\b.*$)", acik)
    if len(parcalar) < 3:
        return acik
    sonuc = [parcalar[0]]
    i = 1
    while i < len(parcalar):
        baslik = parcalar[i]
        govde = parcalar[i + 1] if i + 1 < len(parcalar) else ""
        m = _SORU_BASLIK.match(baslik)
        if not (m and _norm(m.group(1)) in cevaplanan):
            sonuc.append(baslik + govde)
        i += 2
    birlesik = "".join(sonuc).strip()
    # Hiç soru kalmadıysa parser'ın 'boş' sayması için net sinyal
    return birlesik if re.search(r"(?mi)^#{1,4}\s*Q-?T?-?\d+\b", birlesik) else "Açık soru tespit edilmedi."


# ─── Jira'ya Yaz (onaydan sonra) ─────────────────────────────────────────────

# Analiz bölümü işareti — Jira'dan geri okurken `##` düşebilir → '#'li ve '#'siz eşleşir (köprüyle aynı sözleşme).
_ANALIZ_ISARET = re.compile(r"(?:#{1,6}\s*)?🤖\s*Teknik Analiz")
_ORIJINAL_ISARET = re.compile(r"^(?:\s*(?:#{1,6}\s*)?📌\s*Orijinal Talep\s*\n+)+")


def orijinal_talep_ayikla(desc: str) -> str:
    """Task açıklamasından ORİJİNAL talebi çıkarır — daha önce agent analizi yazıldıysa (`🤖 Teknik Analiz` bölümü)
    onun ÜSTÜNDEKİ metni döndürür; yoksa açıklamanın tamamı orijinaldir. Baştaki '📌 Orijinal Talep' başlıkları
    (bir ya da daha çok) temizlenir → tekrar yazımda kaz-boynu birikmez (idempotent)."""
    d = (desc or "").strip()
    if not d:
        return ""
    ust = re.split(r"\n*" + _ANALIZ_ISARET.pattern, d, maxsplit=1)[0]
    ust = _ORIJINAL_ISARET.sub("", ust)
    ust = re.sub(r"\n*-{3,}\s*$", "", ust).strip()
    return ust


def govde_birlestir(analiz_md: str, mevcut_desc: str) -> str:
    """Jira açıklaması = '## 📌 Orijinal Talep' + orijinal + '---' + '## 🤖 Teknik Analiz (Analyst Agent)' + analiz.
    Köprü (`jira_kopru._govdeye_yaz`) ve 'BE'yi yaz' / 'Onayla ve Jira'da Güncelle' aynı biçimi kullanır →
    analiz hiçbir yolda isteri SİLMEZ. Analiz Jira kopyası olarak temizlenir (`jira_icin_temizle`)."""
    temiz = jira_icin_temizle(analiz_md or "").strip()
    orijinal = orijinal_talep_ayikla(mevcut_desc)
    return (f"## 📌 Orijinal Talep\n\n{orijinal or '(açıklama yok)'}\n\n"
            f"---\n\n## 🤖 Teknik Analiz (Analyst Agent)\n\n{temiz}")


def gorev_jiraya_yaz(task_key: str, markdown: str, summary: str | None = None, orijinal_koru: bool = True) -> bool:
    """Görevin description'ını markdown→ADF olarak günceller. İsteğe bağlı summary de güncellenir.
    `orijinal_koru=True` (varsayılan): yazılacak metin zaten `🤖 Teknik Analiz` işaretini TAŞIMIYORSA mevcut açıklama
    okunur ve `govde_birlestir` ile '📌 Orijinal Talep + analiz' olarak yazılır → isteri ezilmez; işaret varsa (köprü /
    BE'yi yaz zaten birleştirdi) olduğu gibi yazılır (idempotent, ikinci okuma yok). Mevcut açıklama okunamazsa
    (yetki/ağ) yazma YAPILMAZ — orijinal korunamayacağı için (sessiz veri kaybı yerine net hata)."""
    task_key = (task_key or "").strip().upper()
    if not _ID_DESENI.match(task_key):
        raise ValueError(f"Geçersiz Jira anahtarı: '{task_key}'")
    if orijinal_koru and not _ANALIZ_ISARET.search(markdown or ""):
        mevcut = gorev_getir(task_key)
        if mevcut is None:
            raise RuntimeError(f"'{task_key}' okunamadı — orijinal talep korunamayacağı için analiz yazılmadı.")
        markdown = govde_birlestir(markdown, mevcut.get("description", ""))
    # Jira'ya giden kopya TEK kapıdan temizlenir (`base.jira_icin_temizle`): Yönetici Özeti +
    # Canlı Gözlem Kapsamı + `<!-- RAG -->` yorumu + kaynak alıntı cümleleri + meta-gerekçe +
    # `[K:]` etiketleri + ardışık bölüm numaraları. Analiz çıktısındaki hâl korunur.
    markdown = jira_icin_temizle(markdown)
    adf_content = markdown_to_adf(markdown)
    if not adf_content:
        # İçerik yalnızca HTML yorumu/boşluktan ibaretse ADF boş kalır — Jira 400 verir.
        raise ValueError("Dönüştürülen içerik boş; Jira'ya yazılamaz. Editörde geçerli markdown bırakın.")
    fields = {"description": {"type": "doc", "version": 1, "content": adf_content}}
    if summary:
        fields["summary"] = summary
    # Not: eski geniş ValueError yakalaması kaldırıldı — canonical atlassian_put 204'ü kendisi ele alır; geniş yakalama
    # gerçek yazma hatalarını (ör. doğrulama mesajı ValueError olarak yükselirse) maskeliyordu.
    atlassian_put(f"/rest/api/3/issue/{task_key}", body={"fields": fields}, cloud_id=_cloud_id())
    return True
