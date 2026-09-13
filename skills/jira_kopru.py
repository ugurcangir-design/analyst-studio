"""Jira Köprüsü — Jira'yı web-chat gibi kullanma (polling + taslak/onay).

Analist, MBSTRADE/MBSOPS gibi bir task'ın YORUMUNA komut yazar:

    /analyst_agent analiz
    /analyst_agent analiz sadece BE tarafını değerlendir
    /analyst_agent yardım

Uygulama (lokal masaüstü, localhost:5003) periyodik bir JQL taramasıyla bu
komutlu yorumları bulur, işler ve sonucu **Jira yorumu** olarak geri yazar.
Inbound bağlantı/webhook/tünel GEREKMEZ — mevcut OAuth + lokal mimariyle uyumlu.

GÜVENLİK İLKELERİ (bkz. CLAUDE.md):
  • Yorum bir KOMUTtur, talimat kaynağı değil (prompt-injection sınırı). Analiz
    girdisi task'ın KENDİ içeriğidir; yorumdaki serbest metin yalnız komut argümanı.
  • YAZMA KAPILARI: `analiz`/`cevap`/`düzelt`/`güncelle` task AÇIKLAMASINI (gövde) yazar —
    orijinal talep korunur (`_orijinal_talep_ayikla`/`_orijinal_gorev`). Yeni Jira TASK açma
    (`ilişkili-aç`) → TASLAK + `onayla`. GÜVENLİK: yorum komutları yalnız `JIRA_KOPRU_YAZAR_ALLOWLIST`
    accountId'lerinden işlenir; allowlist BOŞSA fail-closed (hiç işlenmez). Owner UI kanalı (admin_gerekli) ayrı.
  • Varsayılan KAPALI: `JIRA_KOPRU=false`. Owner `.env`'de açar.
  • Kendi yanıtlarımız `ROBOT_IMZA` ile başlar ve komut prefiksiyle BAŞLAMAZ →
    kendi yorumlarımızı asla komut sanmayız (döngü koruması). İşlenen yorum
    id'leri ayrıca durum dosyasında tutulur (tekrar işleme yok).

Bu modül mevcut analiz motoruna (gorev_getir + gorev_analiz_et) sıfır dokunuşla
oturur; Jira'ya yorum yazma canonical atlassian_post üzerindendir.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .atlassian import atlassian_get, atlassian_post
from .base import (
    canli_gozlem_kapsamini_cikar,
    canli_uygulama_baglami_hazirla,
    load_context_filter,
    yonetici_ozetini_cikar,
)
from .jira_gorevleri import (
    _adf_to_text, _cloud_id, _ID_DESENI,
    gorev_getir, gorev_analiz_et, gorev_analiz_duzelt, gorev_jiraya_yaz,
)
from .jira_tasks import _issue_olustur, _proje_bilgi   # canonical OAuth issue create
from jira_agent import markdown_to_adf  # ADF: teknik analiz task'ı formatı

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DURUM_DOSYA = BASE_DIR / "output" / "jira-kopru" / "durum.json"

ROBOT_IMZA = "🤖 **Analyst Agent**"      # yanıtlarımızın başı — döngü koruması + tanınırlık
_MAX_ISLENEN = 500                        # durum dosyasında tutulan işlenmiş yorum tavanı
_MAX_SON_ANALIZ = 40                      # önbellekte tutulan task analizi (markdown) tavanı — disk şişmesin
_TUR_LOCK = threading.Lock()             # aynı anda TEK tur — arka plan döngüsü + elle /tara çakışmasın (çift işleme önlemi)
_ANALIZ_TAZE_DK = 60                      # `analiz` çıktısı bu kadar dakika içindeyse güncelle/ilişkili-aç yeniden ANALİZ ETMEZ
_MAX_ILISKILI = 5                         # `ilişkili-aç` en fazla bu kadar task önerir

# `ilişkili-aç` için: mevcut task'ı TAMAMLAYAN ilişkili YENİ task önerileri (analizden).
_ILISKILI_SISTEM = """Kıdemli yazılım analistisin. Verilen teknik analizden, ANALİZİ YAPILAN mevcut
Jira görevini TAMAMLAYAN ilişkili YENİ task önerileri çıkar (örn. karşı katman FE↔BE işi, entegrasyon,
migrasyon, test/QA görevi, gözden kaçan bağımlılık). KURALLAR:
- Yalnızca analizden AÇIKÇA doğan, ayrı bir iş kalemi olacak kadar somut görevler öner. Uydurma yok.
- Mevcut görevin KENDİSİNİ tekrar önerme.
- Her öneri kısa, uygulanabilir bir başlık + 1-3 cümle açıklama içersin.
- En fazla {maks} öneri. Gerçekten ayrı iş yoksa boş liste döndür.
- Türkçe yaz; teknik terimler İngilizce kalabilir.
Yanıtı SADECE şu formatta ver:
<iliskili_tasklar>
[{"summary": "...", "description": "...", "katman": "FE|BE|Genel"}]
</iliskili_tasklar>"""


# ─── Ayarlar (.env) ──────────────────────────────────────────────────────────

def _bool(v: str) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "evet", "on")


def _kopru_config() -> dict:
    """Çalışma-zamanı köprü config'i: `reference/jira_kopru.json` (git'te İZLENMEZ; `.example`'dan
    boot'ta seed edilir — analistler .env'e YAZMADAN güncelleme ile ekip varsayılanını alır).
    Yoksa {} → `.env` yedeğine düşülür."""
    try:
        p = BASE_DIR / "reference" / "jira_kopru.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8")) or {}
    except Exception:
        pass
    return {}


def _liste_coz(ham) -> list[str]:
    if isinstance(ham, list):
        return [str(x).strip() for x in ham if str(x).strip()]
    return [x.strip() for x in str(ham or "").split(",") if x.strip()]


def ayarlar() -> dict:
    """Köprü yapılandırması. Öncelik: `reference/jira_kopru.json` (güncelleme ile gelen ekip
    varsayılanı — analist .env yazmaz) > `.env` (yedek/eski) > kod varsayılanı. Self-scope
    sayesinde `yazar_allowlist` boş olabilir (agent kendi hesabına kilitlenir)."""
    cfg = _kopru_config()

    def s(cfg_key: str, env_key: str, default):
        v = cfg.get(cfg_key)
        if v not in (None, "", [], {}):   # boş liste/dize = "set edilmemiş" → .env'e düş (False korunur)
            return v
        e = os.getenv(env_key)
        return e if (e is not None and e != "") else default

    projeler = [p.upper() for p in _liste_coz(s("projeler", "JIRA_KOPRU_PROJELER", ""))]
    izinli = _liste_coz(s("yazar_allowlist", "JIRA_KOPRU_YAZAR_ALLOWLIST", ""))
    return {
        "aktif": _bool(s("aktif", "JIRA_KOPRU", "false")),
        "aralik_sn": max(20, int(s("aralik_sn", "JIRA_KOPRU_ARALIK", 60) or 60)),
        "pencere_dk": max(5, int(s("pencere_dk", "JIRA_KOPRU_PENCERE_DK", 120) or 120)),
        "projeler": projeler,
        "komut": str(s("komut", "JIRA_KOPRU_KOMUT", "/analyst_agent")).strip() or "/analyst_agent",
        "yazar_allowlist": izinli,   # yalnız accountId; BOŞ → self-scope (kendi kimliği)
    }


# ─── Durum (işlenen yorumlar — tekrar işleme yok) ────────────────────────────

def _durum_yukle() -> dict:
    try:
        return json.loads(DURUM_DOSYA.read_text(encoding="utf-8"))
    except Exception:
        return {"islenen": {}, "son_tur": None, "son_ozet": None}


def _durum_yaz(d: dict) -> None:
    DURUM_DOSYA.parent.mkdir(parents=True, exist_ok=True)
    # Sınırsız büyümeyi önle — en yeni N kaydı tut (işlenen yorum id'leri + analiz önbelleği).
    islenen = d.get("islenen", {})
    if len(islenen) > _MAX_ISLENEN:
        sirali = sorted(islenen.items(), key=lambda kv: kv[1].get("zaman", ""))
        d["islenen"] = dict(sirali[-_MAX_ISLENEN:])
    # son_analiz her task'ın tam analiz markdown'ını tutar → en yeni _MAX_SON_ANALIZ task ile sınırla.
    son_analiz = d.get("son_analiz", {})
    if len(son_analiz) > _MAX_SON_ANALIZ:
        sirali = sorted(son_analiz.items(), key=lambda kv: (kv[1] or {}).get("zaman", ""))
        d["son_analiz"] = dict(sirali[-_MAX_SON_ANALIZ:])
    DURUM_DOSYA.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


# ─── Jira yorum G/Ç ──────────────────────────────────────────────────────────

def jira_yorum_ekle(key: str, markdown: str) -> bool:
    """Task'a markdown→ADF yorum ekler (canonical atlassian_post). Yalnız YORUM —
    task alanlarına dokunmaz."""
    key = (key or "").strip().upper()
    if not _ID_DESENI.match(key):
        raise ValueError(f"Geçersiz Jira anahtarı: '{key}'")
    icerik = markdown_to_adf(markdown)
    if not icerik:
        raise ValueError("Yorum içeriği boş (ADF üretilemedi).")
    body = {"body": {"type": "doc", "version": 1, "content": icerik}}
    atlassian_post(f"/rest/api/3/issue/{key}/comment", body=body, cloud_id=_cloud_id())
    return True


def jira_issue_link(inward_key: str, outward_key: str, tip: str = "Relates") -> bool:
    """İki issue arasında link kurar (varsayılan 'Relates'). inward <tip> outward
    (örn. yeni-task Relates kaynak-task). Canonical atlassian_post."""
    body = {"type": {"name": tip},
            "inwardIssue": {"key": inward_key.strip().upper()},
            "outwardIssue": {"key": outward_key.strip().upper()}}
    atlassian_post("/rest/api/3/issueLink", body=body, cloud_id=_cloud_id())
    return True


def _issue_yorumlari(key: str, cloud_id: str) -> list[dict]:
    """Task'ın yorumlarını id + yazar (displayName/accountId) + created + düz metinle
    döndürür (created ARTAN). Komut ayrıştırma ve dedup için id ŞART — bu yüzden
    parse edilmiş görevdeki (id'siz) yorumlar yerine doğrudan comment endpoint'i."""
    yorumlar: list[dict] = []
    baslangic = 0
    while True:
        data = atlassian_get(
            f"/rest/api/3/issue/{key}/comment?orderBy=created&maxResults=100&startAt={baslangic}",
            cloud_id=cloud_id,
        )
        for c in data.get("comments", []) or []:
            yazar = c.get("author") or {}
            govde = c.get("body")
            metin = _adf_to_text(govde) if isinstance(govde, dict) else (govde or "")
            yorumlar.append({
                "id": str(c.get("id", "")),
                "yazar": yazar.get("displayName", ""),
                "hesap": yazar.get("accountId", ""),
                "created": c.get("created", ""),
                "metin": (metin or "").strip(),
            })
        toplam = data.get("total", len(yorumlar))
        baslangic += data.get("maxResults", 100)
        if baslangic >= toplam or not data.get("comments"):
            break
    return yorumlar


# ─── Komut ayrıştırma ────────────────────────────────────────────────────────

def _komut_coz(metin: str, prefix: str) -> tuple[str, str] | None:
    """Yorum metni komut prefiksiyle başlıyorsa (komut, argüman) döndürür; değilse None.
    Örn. '/analyst_agent analiz sadece BE' → ('analiz', 'sadece BE')."""
    s = (metin or "").strip()
    if not s.lower().startswith(prefix.lower()):
        return None
    kalan = s[len(prefix):].strip()
    if not kalan:
        return ("yardim", "")
    parca = kalan.split(None, 1)
    komut = parca[0].strip().lower().lstrip("/")
    arg = parca[1].strip() if len(parca) > 1 else ""
    # Türkçe/aksan eşanlamlıları tek anahtara indir
    esanlam = {
        "yardım": "yardim", "help": "yardim", "?": "yardim",
        "analyze": "analiz", "analiz-et": "analiz",
        "ilişkili-aç": "iliskili-ac", "iliskili-ac": "iliskili-ac", "ilişkiliaç": "iliskili-ac",
        "güncelle": "guncelle",
        "cevapla": "cevap", "cevaplar": "cevap", "answer": "cevap", "yanit": "cevap", "yanıt": "cevap",
        "düzelt": "duzelt", "duzeltme": "duzelt", "fix": "duzelt", "revize": "duzelt",
        "onayla": "onayla", "approve": "onayla",
    }
    return (esanlam.get(komut, komut), arg)


def _yazar_izinli(yorum: dict, izinliler: list[str]) -> bool:
    """Yorum komutunu çalıştırma yetkisi. GÜVENLİK: yalnız `accountId` (kararlı, tekil)
    eşleşir — `displayName` kullanıcı-düzenlenebilir/taklit edilebilir, yetkiye SOKULMAZ.
    Boş allowlist FAIL-CLOSED (çağıran _tek_tur_ic zaten boşken hiç işlemez)."""
    if not izinliler:
        return False
    return yorum.get("hesap", "") in izinliler


# ── Self-scope (madde 2): per-user kurulumda agent, elle allowlist verilmemişse KENDİ Jira
#    kimliğine (myself.accountId) otomatik kilitlenir → analist yalnız KENDİ komutlarını işler,
#    başka analistlerinkine dokunmaz (çakışma yok). Alınamazsa fail-closed korunur.
_owner_id_cache: dict = {"id": None}


def _owner_account_id(cloud_id: str) -> str | None:
    """Agent'ın bağlı olduğu Jira hesabının accountId'i. Bir kez çözülüp önbelleğe alınır."""
    if _owner_id_cache["id"]:
        return _owner_id_cache["id"]
    try:
        me = atlassian_get("/rest/api/3/myself", cloud_id=cloud_id) or {}
        aid = me.get("accountId")
        if aid:
            _owner_id_cache["id"] = aid
            return aid
    except Exception as e:
        logger.warning("Jira 'myself' alınamadı (self-scope): %s", e)
    return None


def _etkin_allowlist(ayar: dict, cloud_id: str) -> list[str]:
    """Yetki eşleşmesinde kullanılacak etkin liste: elle `JIRA_KOPRU_YAZAR_ALLOWLIST` varsa onu
    (merkezi/çok-kullanıcılı kurulum), yoksa self-scope (owner accountId). Hiçbiri yoksa [] → fail-closed."""
    if ayar["yazar_allowlist"]:
        return ayar["yazar_allowlist"]
    aid = _owner_account_id(cloud_id)
    return [aid] if aid else []


def _yardim_metni(prefix: str) -> str:
    return (
        f"{ROBOT_IMZA} — komutlar\n\n"
        f"- `{prefix} analiz` — bu task'ı teknik analiz eder ve sonucu **task açıklamasına** yazar "
        f"(orijinal talep korunur; açık sorular yorumda). Bağlam task'ın kendisinden (kimsenin ekranına bağlı değil).\n"
        f"- `{prefix} analiz <talimat>` — talimatlı analiz (örn. *sadece BE tarafını değerlendir*).\n"
        f"- `{prefix} cevap <cevaplarınız>` — açık sorulara cevap → analiz cevaplara göre güncellenir, sorular yakınsar.\n"
        f"- `{prefix} düzelt <talimat>` — yalnız ilgili kısmı düzeltir (diğer bölümler korunur).\n"
        f"- `{prefix} güncelle` — son analizi task açıklamasına yeniden yazar (taze analiz varsa 0-token).\n"
        f"- `{prefix} ilişkili-aç` — analizden ilişkili yeni task'lar **önerir** (taslak) → `{prefix} onayla` açar + Relates bağlar.\n"
        f"- `{prefix} onayla` / `{prefix} iptal` — bekleyen ilişkili-task taslağını uygular / vazgeçer.\n"
        f"- `{prefix} yardım` — bu liste.\n\n"
        f"_Güvenlik: yorum bir komuttur; YENİ task açma yalnız açık onaydan sonra yapılır._"
    )


# ─── Komut işleme ────────────────────────────────────────────────────────────

def _proje_key(key: str) -> str:
    """MBSTRADE-123 → MBSTRADE."""
    return (key or "").split("-", 1)[0].upper()


# Türkçe+İngilizce durak kelimeler — task'tan RAG anahtar kelimesi çıkarırken elenir.
_STOPWORDS = {
    "için", "ile", "ama", "veya", "gibi", "kadar", "daha", "çok", "bir", "bu", "şu", "olan",
    "olarak", "üzerinde", "üzerine", "göre", "sonra", "önce", "hem", "her", "tüm", "bütün",
    "değil", "yani", "ancak", "fakat", "ve", "de", "da", "ki", "mi", "mı", "the", "and", "for",
    "with", "that", "this", "from", "into", "will", "shall", "should", "must", "when", "then",
    "task", "görev", "ekran", "ekranı", "buton", "butonu", "alan", "alanı", "sayfa", "kullanıcı",
    "işlem", "yeni", "eklenmesi", "eklenecek", "yapılması", "yapılacak", "olması", "gerekiyor",
    "istenen", "isteniyor", "talebi", "talep", "açıklama", "başlık",
}


def _task_keywords(gorev: dict, azami: int = 8) -> list[str]:
    """Task başlığı+açıklamasından RAG için anahtar kelimeler çıkarır (deterministik,
    0 token). Durak kelimeler elenir; **≥5 harfli** en sık/ilk geçen **en çok 8** terim.
    filtrele_referanslar bunları alt-dize olarak arar → CLI'de token doğrudan RAG boyutuna
    bağlı olduğundan az/isabetli kelime = daha küçük getirim (kısa/genel terim aşırı-isabet önlenir)."""
    metin = f"{gorev.get('summary', '')} {gorev.get('summary', '')} {gorev.get('description', '')}".lower()
    tokenler = re.findall(r"[a-zçğıiöşü0-9][a-zçğıiöşü0-9\-]{4,}", metin)
    sayac: dict[str, int] = {}
    sira: list[str] = []
    for t in tokenler:
        t = t.strip("-")
        if len(t) < 5 or t in _STOPWORDS or t.isdigit():
            continue
        if t not in sayac:
            sira.append(t)
        sayac[t] = sayac.get(t, 0) + 1
    # sıklığa göre (eşitlikte ilk görülme sırası) sırala, azami kadar al
    sirali = sorted(sira, key=lambda w: (-sayac[w], sira.index(w)))
    return sirali[:azami]


def _canli_gorev_baglam(gorev: dict) -> str | None:
    """#2 — Bridge canlı gözlem bağlamı: kayıtlı live-app URL'inden ANA giriş (base)
    türetilir; hedef ekran task içeriğinden bulunur (login zaten live_app_auth ile).
    Sabit `live_app_gorev` ekranına bağlı DEĞİL. Yapılandırma yoksa None."""
    ctx = load_context_filter() or {}
    url = ""
    for k in ("live_app_gorev", "live_app"):
        v = ctx.get(k) or {}
        if isinstance(v, dict) and str(v.get("target_url", "")).strip():
            url = str(v["target_url"]).strip()
            break
    if not url:
        return None
    p = urlparse(url)
    if not (p.scheme and p.netloc):
        return None
    base = f"{p.scheme}://{p.netloc}"
    hedef = f"{gorev.get('summary', '')}\n\n{gorev.get('description', '')}".strip()
    return canli_uygulama_baglami_hazirla(base_url_override=base, hedef_tarif=hedef)


def _orijinal_gorev(gorev: dict) -> dict:
    """Analiz GİRDİSİ için görevi normalize eder: açıklamaya daha önce bridge analizi
    yazıldıysa (gövde = orijinal + 🤖 analiz), analiz GİRDİSİ yalnız ORİJİNAL talep
    olmalı — yoksa analiz kendi çıktısını girdi sanar (özyineleme). `description`'ı
    `_orijinal_talep_ayikla` ile orijinale indirir (kopya döndürür, mutasyon yok)."""
    orj = _orijinal_talep_ayikla(gorev.get("description", ""))
    if orj and orj != (gorev.get("description") or "").strip():
        g = dict(gorev)
        g["description"] = orj
        return g
    return gorev


def _analiz_bolumu_ayikla(desc: str) -> str:
    """Gövdedeki `## 🤖 Teknik Analiz` bölümünü (analiz metni) döndürür — `düzelt`
    önbellek boşsa gövdeden mevcut analizi alır. Yoksa ''. """
    parcalar = re.split(r"\n*(?:#{1,6}\s*)?🤖\s*Teknik Analiz[^\n]*\n", desc or "", maxsplit=1)
    return parcalar[1].strip() if len(parcalar) > 1 else ""


def _bridge_uret(gorev: dict, arg: str, onceki_sorular: str = "") -> dict:
    """Bridge analizini KENDİ KENDİNE YETERLİ üretir: ORİJİNAL talep girdi (#1 özyineleme
    önlemi), task keyword'leriyle RAG (#3), base-URL + task-güdümlü canlı gözlem (#2),
    ekran notu/filtresi YOK. `onceki_sorular` verilirse açık sorular yakınsar (cevap turu)."""
    gorev = _orijinal_gorev(gorev)
    kws = _task_keywords(gorev)
    canli = _canli_gorev_baglam(gorev)
    sonuc = gorev_analiz_et(gorev, cevaplar=arg or "", onceki_sorular=onceki_sorular,
                            ekran_baglami=False,
                            rag_ctx={"keywords": kws} if kws else {},
                            canli_baglam_override=canli)
    sonuc["_keywords"] = kws
    return sonuc


def _analiz_md_getir(key: str, arg: str, durum: dict) -> str:
    """güncelle için analiz markdown'ı — TAZE `analiz` çıktısı (son _ANALIZ_TAZE_DK dk)
    varsa yeniden ANALİZ ETMEZ (token tasarrufu), yoksa üretir + önbelleğe alır."""
    onbellek = durum.setdefault("son_analiz", {})
    kayit = onbellek.get(key)
    if kayit and not arg:
        try:
            yas_dk = (datetime.now(timezone.utc)
                      - datetime.strptime(kayit["zaman"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                      ).total_seconds() / 60
            if yas_dk <= _ANALIZ_TAZE_DK and kayit.get("md"):
                return kayit["md"]
        except Exception:
            pass
    gorev = gorev_getir(key)
    if not gorev:
        raise RuntimeError(f"`{key}` okunamadı (yetki/erişim?).")
    md = (_bridge_uret(gorev, arg).get("markdown") or "").strip()
    onbellek[key] = {"md": md, "zaman": _simdi()}
    return md


def _orijinal_talep_ayikla(desc: str) -> str:
    """Task açıklamasından ORİJİNAL talebi çıkarır — önceki bir bridge analizi
    yazıldıysa (`🤖 Teknik Analiz` bölümü) onun ÜSTÜNDEKİ orijinal metni döndürür;
    yoksa açıklamanın tamamı orijinaldir. Tekrar analizde orijinal korunur (#1).
    ÖNEMLİ: Jira, yazdığımız markdown başlıklarını (`## 📌`/`## 🤖`) ADF'ye çevirir;
    geri OKURKEN `##` işaretleri DÜŞER → marker'ları `#`'li VE `#`'siz eşleştir.
    Ayrıca kaz-boynu ekleme (çift '📌 Orijinal Talep') olmasın diye baştaki
    BİR VEYA DAHA ÇOK orijinal başlığı temizlenir."""
    d = (desc or "").strip()
    if not d:
        return ""
    ust = re.split(r"\n*(?:#{1,6}\s*)?🤖\s*Teknik Analiz", d, maxsplit=1)[0]
    ust = re.sub(r"^(?:\s*(?:#{1,6}\s*)?📌\s*Orijinal Talep\s*\n+)+", "", ust)
    ust = re.sub(r"\n*-{3,}\s*$", "", ust).strip()
    return ust


def _govdeye_yaz(key: str, analiz_md: str, mevcut_desc: str) -> None:
    """#1 — Analizi task GÖVDESİNE (açıklama) yazar; ORİJİNAL talep korunur.
    Açıklama = '## 📌 Orijinal Talep' + orijinal + '## 🤖 Teknik Analiz' + analiz.
    Yönetici Özeti / Canlı Gözlem Kapsamı gövdeye YAZILMAZ (analist bilgisi)."""
    temiz = canli_gozlem_kapsamini_cikar(yonetici_ozetini_cikar(analiz_md)).strip()
    orijinal = _orijinal_talep_ayikla(mevcut_desc)
    combined = (
        f"## 📌 Orijinal Talep\n\n{orijinal or '(açıklama yok)'}\n\n"
        f"---\n\n## 🤖 Teknik Analiz (Analyst Agent)\n\n{temiz}"
    )
    gorev_jiraya_yaz(key, combined)


def _analiz_islet(key: str, arg: str, durum: dict) -> str:
    """`analiz` — task'ı KENDİ KENDİNE YETERLİ analiz eder ve sonucu task GÖVDESİNE
    yazar (orijinal talep korunur, #1). Yorum = kısa bilgilendirme + açık sorular."""
    gorev = gorev_getir(key)
    if not gorev:
        return f"{ROBOT_IMZA}\n\n⚠ `{key}` okunamadı (yetki/erişim?). Analiz yapılamadı."
    sonuc = _bridge_uret(gorev, arg)
    md = (sonuc.get("markdown") or "").strip()
    acik = (sonuc.get("acik_sorular") or "").strip()
    kws = sonuc.get("_keywords") or []
    durum.setdefault("son_analiz", {})[key] = {"md": md, "acik": acik, "zaman": _simdi()}
    try:
        _govdeye_yaz(key, md, gorev.get("description", ""))
        bas = f"{ROBOT_IMZA} — Teknik analiz **task açıklamasına yazıldı** · `{key}` (orijinal talep korundu)."
    except Exception as e:
        bas = (f"{ROBOT_IMZA} — ⚠ Analiz üretildi ama açıklamaya yazılamadı: {e}\n\n"
               f"Analiz metni aşağıdadır:\n\n{canli_gozlem_kapsamini_cikar(yonetici_ozetini_cikar(md)).strip()}")
    prefix = ayarlar()["komut"]
    parcalar = [bas, "", f"RAG anahtar kelimeleri: {', '.join(kws) if kws else '—'}"]
    if acik and acik.lower() not in ("açık soru tespit edilmedi.", "acik soru tespit edilmedi."):
        parcalar += ["", "---", "**Açık Sorular** (gövdeye yazılmadı):", "", acik, "",
                     f"↪︎ Cevaplamak için: `{prefix} cevap <cevaplarınız>` — analiz cevaplara göre güncellenir, sorular yakınsar.",
                     f"↪︎ İlgili kısmı düzeltmek için: `{prefix} düzelt <talimat>`."]
    parcalar += ["", f"İlişkili task önerileri için: `{prefix} ilişkili-aç` (onay gerekir)."]
    return "\n".join(parcalar)


def _acik_yorum_parcasi(acik: str, prefix: str) -> list[str]:
    """Cevap turu sonrası kalan açık soruları + sonraki adım ipuçlarını yorum satırlarına çevirir."""
    if not acik or acik.lower() in ("açık soru tespit edilmedi.", "acik soru tespit edilmedi."):
        return ["", "✅ Açık soru kalmadı."]
    return ["", "**Kalan Açık Sorular:**", "", acik, "",
            f"↪︎ Devam için: `{prefix} cevap <cevaplarınız>` · `{prefix} düzelt <talimat>`."]


def _cevap_islet(key: str, arg: str, durum: dict, prefix: str) -> str:
    """`cevap` — açık sorulara verilen cevaplarla analizi YENİDEN üretir (cevaplananları
    ÇÖZER), soruları YAKINSAR (önceki sorular verilir → cevaplanan çıkar, kalan korunur,
    yeni bloklayan eklenir), gövdeyi günceller (orijinal korunur)."""
    if not (arg or "").strip():
        return (f"{ROBOT_IMZA}\n\n⚠ Cevap metni gerekli. Örn: "
                f"`{prefix} cevap Q-T-001: Event Name korunur, freeText destekleyici`")
    gorev = gorev_getir(key)
    if not gorev:
        return f"{ROBOT_IMZA}\n\n⚠ `{key}` okunamadı (yetki/erişim?)."
    onceki = (durum.get("son_analiz", {}).get(key, {}) or {}).get("acik", "")
    sonuc = _bridge_uret(gorev, arg, onceki_sorular=onceki)
    md = (sonuc.get("markdown") or "").strip()
    acik = (sonuc.get("acik_sorular") or "").strip()
    durum.setdefault("son_analiz", {})[key] = {"md": md, "acik": acik, "zaman": _simdi()}
    try:
        _govdeye_yaz(key, md, gorev.get("description", ""))
    except Exception as e:
        return f"{ROBOT_IMZA}\n\n⚠ Analiz cevaplarla güncellendi ama gövdeye yazılamadı: {e}"
    bas = f"{ROBOT_IMZA} — Analiz **cevaplara göre güncellendi** · `{key}` (gövdeye yazıldı, orijinal korundu)."
    return "\n".join([bas] + _acik_yorum_parcasi(acik, prefix))


def _duzelt_islet(key: str, arg: str, durum: dict, prefix: str) -> str:
    """`düzelt` — yalnız ilgili kısmı düzeltir (`gorev_analiz_duzelt`), dokunulmayan
    bölümleri korur; gövdeye yazar. Mevcut analiz önbellekte yoksa gövdeden alınır."""
    if not (arg or "").strip():
        return f"{ROBOT_IMZA}\n\n⚠ Düzeltme talimatı gerekli. Örn: `{prefix} düzelt §7'ye debounce süresini ekle`"
    gorev = gorev_getir(key)
    if not gorev:
        return f"{ROBOT_IMZA}\n\n⚠ `{key}` okunamadı (yetki/erişim?)."
    mevcut = (durum.get("son_analiz", {}).get(key, {}) or {}).get("md", "")
    if not mevcut:
        mevcut = _analiz_bolumu_ayikla(gorev.get("description", ""))
    if not mevcut:
        return f"{ROBOT_IMZA}\n\n⚠ `{key}` için düzeltilecek analiz yok — önce `{prefix} analiz` çalıştırın."
    try:
        yeni = gorev_analiz_duzelt(_orijinal_gorev(gorev), mevcut, arg)
    except Exception as e:
        return f"{ROBOT_IMZA}\n\n⚠ Düzeltme yapılamadı: {e}"
    onceki_acik = (durum.get("son_analiz", {}).get(key, {}) or {}).get("acik", "")
    durum.setdefault("son_analiz", {})[key] = {"md": yeni, "acik": onceki_acik, "zaman": _simdi()}
    try:
        _govdeye_yaz(key, yeni, gorev.get("description", ""))
    except Exception as e:
        return f"{ROBOT_IMZA}\n\n⚠ Düzeltme üretildi ama gövdeye yazılamadı: {e}"
    return f"{ROBOT_IMZA} ✅ `{key}` analizinin ilgili kısmı düzeltildi ve açıklamaya yazıldı (orijinal korundu)."


def _guncelle_islet(key: str, arg: str, durum: dict, prefix: str) -> str:
    """`güncelle` — SON analizi (önbellek) task GÖVDESİNE (yeniden) yazar; orijinal
    talep korunur. `analiz` zaten gövdeye yazar → bu, taze analiz varsa 0-token
    yeniden uygulamadır (yoksa üretir). Onay gerekmez (task'ın kendi gövdesi)."""
    gorev = gorev_getir(key)
    if not gorev:
        return f"{ROBOT_IMZA}\n\n⚠ `{key}` okunamadı (yetki/erişim?)."
    try:
        md = _analiz_md_getir(key, arg, durum)
    except Exception as e:
        return f"{ROBOT_IMZA}\n\n⚠ `{key}` analizi üretilemedi: {e}"
    if not md:
        return f"{ROBOT_IMZA}\n\n⚠ `{key}` için analiz üretilemedi; gövde yazılamadı."
    _govdeye_yaz(key, md, gorev.get("description", ""))
    return f"{ROBOT_IMZA} ✅ `{key}` açıklaması son analizle güncellendi (orijinal talep korundu)."


def _iliskili_task_onerileri(analiz_md: str, gorev: dict) -> list[dict]:
    """Analizden mevcut görevi tamamlayan ilişkili YENİ task önerileri (AI, JSON)."""
    from .base import _api_cagri, _xml_ayir, MAX_TOKENS_KISA
    sistem = _ILISKILI_SISTEM.replace("{maks}", str(_MAX_ILISKILI))
    kullanici = (f"### Mevcut Görev: {gorev.get('key', '')}\n**Başlık:** {gorev.get('summary', '')}\n\n"
                 f"### Teknik Analiz\n{analiz_md}\n\nİlişkili yeni task önerilerini üret.")
    yanit = _api_cagri(sistem, [{"role": "user", "content": [{"type": "text", "text": kullanici}]}],
                       max_tokens=MAX_TOKENS_KISA)
    ham = _xml_ayir(yanit, "iliskili_tasklar") or "[]"
    try:
        oneriler = json.loads(ham)
    except json.JSONDecodeError:
        temiz = re.sub(r"^```[a-z]*\n?", "", ham.strip()).rstrip("`").strip()
        oneriler = json.loads(temiz) if temiz else []
    temizlenmis = []
    for o in oneriler[:_MAX_ILISKILI]:
        s = str(o.get("summary", "")).strip()
        if s:
            temizlenmis.append({"summary": s[:255],
                                "description": str(o.get("description", "")).strip(),
                                "katman": str(o.get("katman", "Genel")).strip() or "Genel"})
    return temizlenmis


def _iliskili_taslak(key: str, arg: str, durum: dict, prefix: str) -> str:
    """`ilişkili-aç` — analizden ilişkili YENİ task'lar ÖNERİR (taslak). Açmaz; `onayla` bekler."""
    gorev = gorev_getir(key)
    if not gorev:
        return f"{ROBOT_IMZA}\n\n⚠ `{key}` okunamadı; ilişkili task önerisi üretilemedi."
    md = _analiz_md_getir(key, arg, durum)
    oneriler = _iliskili_task_onerileri(md, gorev)
    if not oneriler:
        return (f"{ROBOT_IMZA} — İlişkili task · `{key}`\n\n"
                f"Analizden ayrı bir iş kalemi olacak ilişkili yeni task tespit edilmedi.")
    proje = _proje_key(key)
    durum.setdefault("taslaklar", {})[key] = {
        "tip": "iliskili-ac", "proje": proje, "oneriler": oneriler, "zaman": _simdi(),
    }
    satirlar = [f"{ROBOT_IMZA} — İlişkili task taslağı · `{key}`", "",
                f"Onaylarsanız `{proje}` projesinde şu task'lar **açılacak** ve `{key}` ile "
                f"**Relates** olarak bağlanacak:", ""]
    for i, o in enumerate(oneriler, 1):
        satirlar.append(f"{i}. **[{o['katman']}] {o['summary']}**")
        if o["description"]:
            satirlar.append(f"   - {o['description']}")
    satirlar += ["", f"Uygulamak için: `{prefix} onayla` · vazgeçmek için: `{prefix} iptal`"]
    return "\n".join(satirlar)


def _onayla_uygula(key: str, durum: dict, prefix: str) -> str:
    """`onayla` — bekleyen taslağı UYGULAR (tek geri-döndürülemez yazma noktası)."""
    taslak = durum.get("taslaklar", {}).get(key)
    if not taslak:
        return (f"{ROBOT_IMZA}\n\n`{key}` için bekleyen taslak yok. Önce `{prefix} ilişkili-aç` çalıştırın.")
    tip = taslak.get("tip")
    # Uygulanmış say: sonuç ne olursa olsun taslağı düş (çift-uygulama önlemi).
    durum.get("taslaklar", {}).pop(key, None)
    if tip == "iliskili-ac":
        proje = taslak.get("proje") or _proje_key(key)
        cloud_id = _cloud_id()
        pbilgi = _proje_bilgi(proje, cloud_id)
        task_type_id = pbilgi.get("task_id") or pbilgi.get("story_id")
        if not task_type_id:
            return f"{ROBOT_IMZA}\n\n⚠ `{proje}` projesinde 'Task' tipi bulunamadı; task açılamadı."
        acilan, hata = [], []
        for o in taslak.get("oneriler", []):
            try:
                desc_md = o.get("description") or o["summary"]
                adf = {"type": "doc", "version": 1, "content": markdown_to_adf(desc_md) or markdown_to_adf(o["summary"])}
                yeni = _issue_olustur(o["summary"], adf, task_type_id, proje, cloud_id)
                try:
                    jira_issue_link(yeni, key, "Relates")
                except Exception as le:
                    hata.append(f"{yeni} link kurulamadı: {le}")
                acilan.append(yeni)
            except Exception as e:
                hata.append(f"'{o['summary'][:40]}' açılamadı: {e}")
        satir = [f"{ROBOT_IMZA} ✅ `{key}` için {len(acilan)} ilişkili task açıldı:"]
        satir += [f"- {k} ({key} ile Relates)" for k in acilan]
        if hata:
            satir += ["", "⚠ Bazı adımlar başarısız:"] + [f"- {h}" for h in hata]
        return "\n".join(satir)
    return f"{ROBOT_IMZA}\n\n⚠ Bilinmeyen taslak tipi: {tip}"


def _komut_uygula(komut: str, arg: str, key: str, prefix: str, durum: dict) -> str:
    """Komutu işleyip Jira'ya yazılacak YANIT markdown'ını döndürür. `durum`
    taslak deposu + analiz önbelleği için paylaşılır (tek_tur sonda diske yazar)."""
    if komut == "yardim":
        return _yardim_metni(prefix)
    if komut == "analiz":
        return _analiz_islet(key, arg, durum)
    if komut == "guncelle":
        return _guncelle_islet(key, arg, durum, prefix)
    if komut == "cevap":
        return _cevap_islet(key, arg, durum, prefix)
    if komut == "duzelt":
        return _duzelt_islet(key, arg, durum, prefix)
    if komut == "iliskili-ac":
        return _iliskili_taslak(key, arg, durum, prefix)
    if komut == "onayla":
        return _onayla_uygula(key, durum, prefix)
    if komut == "iptal":
        vardi = durum.get("taslaklar", {}).pop(key, None) is not None
        return (f"{ROBOT_IMZA}\n\n{'Taslak iptal edildi.' if vardi else 'İptal edilecek bekleyen taslak yok.'}")
    return (
        f"{ROBOT_IMZA}\n\n❓ Bilinmeyen komut: `{komut}`. `{prefix} yardım` ile komut listesine bakın."
    )


# ─── Tek tur (elle /tara ve arka plan döngüsü ortak yolu) ────────────────────

def tek_tur(pencere_dk: int | None = None) -> dict:
    """Komutlu yeni yorumları bir kez tarar ve işler. Döner:
        {"ok", "taranan_task", "islenen":[{key,komut,yazar}], "atlanan", "hata":[...]}.
    Elle `/api/jira-kopru/tara` ve arka plan döngüsü aynı yolu kullanır. AYNI ANDA
    TEK tur çalışır — kilit tutuluysa ikinci çağrı İŞLEMEDEN döner (arka plan döngüsü
    ile elle taramanın aynı yorumu iki kez işlemesini önler)."""
    if not _TUR_LOCK.acquire(blocking=False):
        return {"ok": False, "error": "Köprü taraması zaten çalışıyor; bu çağrı atlandı.", "kilitli": True}
    try:
        return _tek_tur_ic(pencere_dk)
    finally:
        _TUR_LOCK.release()


def _tek_tur_ic(pencere_dk: int | None = None) -> dict:
    ayar = ayarlar()
    if not ayar["projeler"]:
        return {"ok": False, "error": "JIRA_KOPRU_PROJELER tanımlı değil (.env)."}
    cloud_id = _cloud_id()   # Jira bağlı değilse net RuntimeError
    # GÜVENLİK — FAIL-CLOSED + SELF-SCOPE: etkin allowlist = elle `JIRA_KOPRU_YAZAR_ALLOWLIST`,
    # yoksa agent'ın KENDİ Jira kimliği (myself.accountId → yalnız kendi komutlarını işler; per-user
    # kurulumda çakışmasız). Hiçbiri belirlenemezse yorum kanalı komutları İŞLENMEZ (fail-closed).
    # Owner UI kanalı (admin_gerekli) etkilenmez.
    etkin_allowlist = _etkin_allowlist(ayar, cloud_id)
    if not etkin_allowlist:
        return {"ok": False, "fail_closed": True,
                "error": "Yetki belirlenemedi: JIRA_KOPRU_YAZAR_ALLOWLIST boş ve Jira kimliği (myself) "
                         "alınamadı — güvenlik gereği yorum komutları işlenmez (fail-closed)."}
    pencere = pencere_dk or ayar["pencere_dk"]
    prefix = ayar["komut"]
    durum = _durum_yukle()
    islenen_kayit = durum.setdefault("islenen", {})

    # WATERMARK: son taramadan bu yana GEÇEN süre kadar geriye bak (+2 dk örtüşme), `pencere` ile
    # sınırlı. Steady-state'te (ör. 60s aralık) yalnız son ~1-2 dk güncellenen task'lar taranır →
    # her turda tüm task'ların TÜM yorumlarını çekmek yerine çok daha az Jira REST çağrısı.
    # İlk tarama / eski son_tur → tam `pencere` (kaçırma yok).
    etkin_pencere = pencere
    if durum.get("son_tur"):
        try:
            gecen_dk = (datetime.now(timezone.utc) - datetime.strptime(
                durum["son_tur"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).total_seconds() / 60
            etkin_pencere = min(pencere, max(2, int(gecen_dk) + 2))
        except Exception:
            pass

    projeler = ",".join(ayar["projeler"])
    jql = f"project in ({projeler}) AND updated >= \"-{etkin_pencere}m\" ORDER BY updated DESC"
    body = {"jql": jql, "fields": ["summary"], "maxResults": 100}
    data = atlassian_post("/rest/api/3/search/jql", body=body, cloud_id=cloud_id)
    task_keys = [i.get("key") for i in data.get("issues", []) if i.get("key")]

    islenen: list[dict] = []
    hatalar: list[dict] = []
    atlanan = 0
    for key in task_keys:
        try:
            yorumlar = _issue_yorumlari(key, cloud_id)
        except Exception as e:
            hatalar.append({"key": key, "hata": f"yorum okunamadı: {e}"})
            continue
        for y in yorumlar:
            cid = y["id"]
            if not cid or cid in islenen_kayit:
                continue
            coz = _komut_coz(y["metin"], prefix)
            if not coz:
                continue  # komut değil (kendi 🤖 yanıtlarımız da buraya düşer)
            komut, arg = coz
            if not _yazar_izinli(y, etkin_allowlist):
                # İSTEK 1 — TAM SESSİZLİK: entegrasyonu olmayan / yetkisiz yazara Jira'ya YANIT
                # YAZILMAZ ve işlenen-id'ye EKLENMEZ (başka analistin kendi agent'ı, kendi durum
                # dosyasında, kendi komutunu işleyebilsin). Yorum düz bir Jira girdisi olarak kalır;
                # agent'ın varlığı yetkisiz kullanıcıya sızmaz. `atlanan` yalnız owner tanısı için.
                atlanan += 1
                continue
            try:
                yanit = _komut_uygula(komut, arg, key, prefix, durum)
                jira_yorum_ekle(key, yanit)
                islenen_kayit[cid] = {"key": key, "komut": komut, "yazar": y["yazar"], "zaman": _simdi()}
                islenen.append({"key": key, "komut": komut, "yazar": y["yazar"]})
            except Exception as e:
                hatalar.append({"key": key, "komut": komut, "hata": str(e)})
                # Hatada da işlendi işaretle (aynı hatayı token yakarak tekrarlama);
                # kullanıcıya kısa hata yorumu bırak.
                islenen_kayit[cid] = {"key": key, "komut": komut, "zaman": _simdi(), "hata": str(e)}
                try:
                    jira_yorum_ekle(key, f"{ROBOT_IMZA}\n\n⚠ Komut işlenemedi: {e}")
                except Exception:
                    pass

    ozet = {"ok": True, "taranan_task": len(task_keys), "islenen": islenen,
            "atlanan": atlanan, "hata": hatalar, "zaman": _simdi()}
    durum["son_tur"] = ozet["zaman"]
    durum["son_ozet"] = {"taranan_task": len(task_keys), "islenen": len(islenen),
                         "atlanan": atlanan, "hata": len(hatalar)}
    _durum_yaz(durum)
    return ozet


# Runtime sağlık — arka plan döngüsü (app.py) her turda günceller; süreç-içi (disk değil).
# Kullanıcı agent'ının canlı + Jira'ya bağlı olduğunu görebilsin (durum göstergesi, madde 6).
_saglik: dict = {"bagli": None, "son_hata": None, "kontrol": None}


def saglik_guncelle(bagli: bool, hata: str | None = None) -> None:
    """Köprü döngüsü çağırır: başarılı tur → bagli=True; hata → bagli=False + son_hata."""
    _saglik["bagli"] = bool(bagli)
    _saglik["son_hata"] = (hata or None) if not bagli else None
    _saglik["kontrol"] = _simdi()


def saglik() -> dict:
    return dict(_saglik)


def son_durum() -> dict:
    """UI/endpoint için köprü durumu (0 token)."""
    d = _durum_yukle()
    return {"ayarlar": {k: v for k, v in ayarlar().items()},
            "son_tur": d.get("son_tur"), "son_ozet": d.get("son_ozet"),
            "islenen_toplam": len(d.get("islenen", {})),
            "saglik": saglik()}


# ─── Agent UI kanalı — açık soruları arayüzden de cevapla (tek beyin, iki kanal) ──

_UI_KOMUTLAR = {"analiz", "cevap", "duzelt", "guncelle", "iliskili-ac", "onayla", "iptal"}


def _acik_var(acik: str) -> bool:
    a = (acik or "").strip().lower()
    return bool(a) and a not in ("açık soru tespit edilmedi.", "acik soru tespit edilmedi.")


def liste() -> dict:
    """Agent UI için köprü analizlerini listeler (0 token) — key · son analiz zamanı ·
    açık sorular · bekleyen ilişkili taslak. En yeni önce."""
    d = _durum_yukle()
    son = d.get("son_analiz", {}) or {}
    taslaklar = d.get("taslaklar", {}) or {}
    kayitlar = []
    for key, v in son.items():
        acik = (v or {}).get("acik", "")
        kayitlar.append({
            "key": key,
            "zaman": (v or {}).get("zaman", ""),
            "acik": acik,
            "acik_var": _acik_var(acik),
            "taslak_var": key in taslaklar,
            "taslak_tip": (taslaklar.get(key) or {}).get("tip", ""),
        })
    kayitlar.sort(key=lambda r: r.get("zaman", ""), reverse=True)
    return {"ok": True, "kayitlar": kayitlar, "aktif": ayarlar()["aktif"], "komut": ayarlar()["komut"],
            "saglik": saglik(), "son_tur": d.get("son_tur")}


def ui_komut(komut: str, key: str, arg: str = "") -> dict:
    """Agent UI'dan köprü komutu çalıştırır — Jira yorumuyla AYNI mantık (`_komut_uygula`),
    ayrıca Jira'ya aynı bilgilendirme yorumunu bırakır (iki kanal tutarlı). Uzun sürebilir
    (AI); app tarafında arka plan işinde çağrılmalı. `_TUR_LOCK` ile döngüyle serileşir."""
    komut = (komut or "").strip().lower()
    key = (key or "").strip().upper()
    if komut not in _UI_KOMUTLAR:
        return {"ok": False, "error": f"Geçersiz komut: {komut}"}
    if not _ID_DESENI.match(key):
        return {"ok": False, "error": f"Geçersiz Jira anahtarı: {key}"}
    prefix = ayarlar()["komut"]
    _TUR_LOCK.acquire()
    try:
        durum = _durum_yukle()
        try:
            yanit = _komut_uygula(komut, arg, key, prefix, durum)
        except Exception as e:
            _durum_yaz(durum)
            return {"ok": False, "error": str(e), "key": key, "komut": komut}
        # UI kanalı da Jira'ya aynı yorumu bıraksın (analist Jira'da da görsün)
        try:
            jira_yorum_ekle(key, yanit)
        except Exception:
            pass
        _durum_yaz(durum)
        acik = (durum.get("son_analiz", {}).get(key, {}) or {}).get("acik", "")
        return {"ok": True, "key": key, "komut": komut, "yanit": yanit,
                "acik": acik, "acik_var": _acik_var(acik),
                "taslak_var": key in (durum.get("taslaklar", {}) or {})}
    finally:
        _TUR_LOCK.release()


def _simdi() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
