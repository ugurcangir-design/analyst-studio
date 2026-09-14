"""
Jira FE/BE Görev Bölme Skill — Adım 7 (alternatif akış).

teknik-analiz.md → DÜZ (hiyerarşisiz) FE ve BE **görev (Task)** listesi →
ilişkili FE↔BE task'lar arasında **Blocks** bağı (BE, FE'yi bloklar).

Hiyerarşi (Epic/Story/Subtask) akışından (jira_tasks.py) FARKI:
- Tüm issue'lar tek tip: **Task** (görev). Epic/Story/Subtask AÇILMAZ.
- Yapı DÜZ: her iş öğesi bağımsız bir Task. Üst başlık yok.
- FE ve BE ayrı task'lardır; bir FE, ihtiyaç duyduğu BE task'ı tarafından
  BLOKLANIR (Blocks bağı: BE 'blocks' FE / FE 'is blocked by' BE).

Akış: `jira_fe_be_uret` (önizleme, Jira'ya YAZMAZ) → analist seçer/düzenler →
`jira_fe_be_olustur` (seçilenleri Task olarak açar + Blocks bağlarını kurar).
"""

import json
import re

from .base import (
    _api_cagri, _xml_ayir, _metin_sikistir,
    dosya_oku, OUTPUT_DIR, MAX_CHARS_GENEL,
    yonetici_ozetini_cikar, canli_gozlem_kapsamini_cikar,
)
from .atlassian import env_oku, atlassian_get, atlassian_post
from .jira_tasks import _proje_bilgi, _issue_olustur, _hikaye_adf


MAX_TOKENS_FE_BE = 4_000

# BE→FE bağımlılığı için Jira link tipi. Projede tam ad farklı olabilir
# (nadiren); _blocks_link_tipi runtime'da doğrular, yoksa buna düşer.
_VARSAYILAN_BLOCKS = "Blocks"


# ─── AI Prompt ────────────────────────────────────────────────────────────────

_FE_BE_SISTEM = """Kıdemli yazılım mimarısın. Teknik analiz dokümanından, geliştirme
ekibinin doğrudan çalışabileceği DÜZ (hiyerarşisiz) bir Jira **görev (Task)** listesi
üret. Epic/Story/Subtask ÜRETME — her iş öğesi bağımsız bir Task'tır.

# KATMAN AYRIMI (ZORUNLU)
Her görev tek bir katmana aittir: FE (frontend) veya BE (backend).
- FE işi (ekran, bileşen, form, validasyon, UX) → ayrı FE görevi
- BE işi (endpoint, servis, iş kuralı, DB/migration) → ayrı BE görevi
- Bir iş hem FE hem BE gerektiriyorsa AYRI bir FE görevi ve AYRI bir BE görevi
  olarak böl; FE görevini, ihtiyaç duyduğu BE görevine bağımlı işaretle.
- Teknik analizdeki İş Kırılımı ID'lerini (T-FE-XX / T-BE-XX) ve §7 (Frontend)
  bölümünü kaynak al. Her görevi bağımsız test edilebilir büyüklükte tut.

# BAĞIMLILIK (BE → FE bloklar)
Bir FE görevi, çalışması için bir BE görevinin (endpoint/servis) BİTMESİNİ
gerektiriyorsa, FE görevinin `bagimli_be` alanına o BE görev(ler)inin id'sini yaz.
Yani "BE görevi FE görevini bloklar". Yalnız GERÇEK bağımlılıkları yaz — her FE'yi
her BE'ye bağlama. BE görevlerinin `bagimli_be`'si genelde boştur.

# KURALLAR
- Görev sayısı işin gerektirdiği kadar (tipik 2-8). Yapay bölme YOK.
- Başlıklar kısa ve eylem odaklı (örn. "Sipariş listesi endpoint'i", "Sipariş ekranı formu").
- description: ne yapılacağı + teknik analizdeki ilgili bölüme/ID'ye atıf.
- Her görev için 2-6 acceptance_criteria (test edilebilir kabul kriteri).
- id'ler BENZERSİZ: FE görevleri FE-1, FE-2…; BE görevleri BE-1, BE-2…
- Tüm metinler Türkçe; teknik terimler (API, endpoint vb.) İngilizce kalabilir.
- `[K: kaynak]` kanıt etiketi KOYMA (bunlar Jira'ya gitmez).

# ÇIKTI FORMATI
Yanıtı SADECE aşağıdaki XML+JSON formatında ver:

<fe_be_gorevler>
{
  "gorevler": [
    {
      "id": "BE-1",
      "katman": "BE",
      "summary": "...",
      "description": "...",
      "acceptance_criteria": ["...", "..."],
      "bagimli_be": []
    },
    {
      "id": "FE-1",
      "katman": "FE",
      "summary": "...",
      "description": "...",
      "acceptance_criteria": ["...", "..."],
      "bagimli_be": ["BE-1"]
    }
  ]
}
</fe_be_gorevler>"""


def _gorevler_uret(teknik_analiz: str, talimat: str = "") -> list[dict]:
    """teknik-analiz.md içeriğinden düz FE/BE görev listesi (JSON) üret.
    `talimat`: analistin bölme yönlendirmesi (ör. 'sadece 2 task: 1 FE + 1 BE',
    'ekran bazlı böl', 'şu konuya göre ayır'). Verilirse AI buna GÖRE böler."""
    steer = ""
    if (talimat or "").strip():
        steer = ("\n\n# ANALİST TALİMATI (BÖLME YÖNLENDİRMESİ — EN YÜKSEK ÖNCELİK)\n"
                 "Task'ları AŞAĞIDAKİ talimata GÖRE böl. Talimat kaç task / hangi ölçüt "
                 "(sadece FE+BE, ekran bazlı, konu bazlı, adet vb.) belirtiyorsa ONA UY; "
                 "gereksiz task açma, talimatın istediği granülerlikte kal:\n"
                 f"«{talimat.strip()}»")
    mesajlar = [{"role": "user", "content": [
        {"type": "text",
         "text": f"### Teknik Analiz\n\n{teknik_analiz}{steer}\n\nFE/BE görev listesini üret."}
    ]}]
    yanit = _api_cagri(_FE_BE_SISTEM, mesajlar, max_tokens=MAX_TOKENS_FE_BE)
    yanit = _metin_sikistir(yanit)
    json_str = _xml_ayir(yanit, "fe_be_gorevler")
    try:
        veri = json.loads(json_str)
    except json.JSONDecodeError as e:
        cleaned = re.sub(r'^```[a-z]*\n?', '', json_str.strip()).rstrip('`').strip()
        try:
            veri = json.loads(cleaned)
        except json.JSONDecodeError:
            raise ValueError(f"AI yanıtı JSON parse edilemedi: {e}\n---\n{json_str[:500]}")
    gorevler = veri.get("gorevler", []) or []
    return _gorevleri_normalize(gorevler)


def _plan_metni(fe: int, be: int, bagimlilik: int, talimat: str = "") -> str:
    """Analiste gösterilecek kısa bölme planı: kaç task, kaç FE/BE, kaç bağımlılık."""
    toplam = fe + be
    p = f"Bu teknik analizi {toplam} task'a bölmeyi öneriyorum: {fe} FE + {be} BE"
    if bagimlilik:
        p += f" ({bagimlilik} BE→FE bağımlılık)"
    p += "."
    if (talimat or "").strip():
        p += f" (Talimatınıza göre: «{talimat.strip()}»)"
    return p


def _katman_indirge(ham: str) -> str:
    """AI'ın katman etiketini FE veya BE'ye indirger (varsayılan BE = güvenli taraf:
    bir BE yanlışlıkla FE'ye bağlanmaz). 'Frontend'/'Backend'/'FE'/'BE'/'client'/'server'
    gibi yaygın yazımları tanır."""
    k = str(ham or "").strip().lower()
    if not k:
        return "BE"
    if "front" in k or k.startswith("fe") or k == "ui" or "client" in k:
        return "FE"
    if "back" in k or k.startswith("be") or "server" in k or "api" in k:
        return "BE"
    return "BE"


def _gorevleri_normalize(gorevler: list) -> list[dict]:
    """AI çıktısını temizler: katmanı FE/BE'ye indirger, id'leri benzersizleştirir,
    `bagimli_be`'yi yalnız GERÇEK BE id'lerine kısıtlar (hayalet bağ önlenir)."""
    temiz: list[dict] = []
    gecerli_idler: set[str] = set()
    for i, g in enumerate(gorevler, 1):
        if not isinstance(g, dict):
            continue
        katman = _katman_indirge(g.get("katman", ""))
        gid = str(g.get("id", "")).strip() or f"{katman}-{i}"
        if gid in gecerli_idler:
            gid = f"{gid}-{i}"
        gecerli_idler.add(gid)
        temiz.append({
            "id": gid,
            "katman": katman,
            "summary": str(g.get("summary", "")).strip() or f"{katman} görevi {i}",
            "description": str(g.get("description", "")).strip(),
            "acceptance_criteria": [str(c).strip() for c in (g.get("acceptance_criteria") or []) if str(c).strip()],
            "bagimli_be": [str(b).strip() for b in (g.get("bagimli_be") or []) if str(b).strip()],
        })
    # bagimli_be'yi yalnız var olan BE görevlerine kısıtla
    be_idler = {g["id"] for g in temiz if g["katman"] == "BE"}
    for g in temiz:
        g["bagimli_be"] = [b for b in g["bagimli_be"] if b in be_idler and b != g["id"]]
    return temiz


# ─── Önizleme: AI görev listesi üret (Jira'ya yazmaz) ────────────────────────

def jira_fe_be_uret(teknik_analiz_dosya: str = "teknik-analiz.md", talimat: str = "") -> dict:
    """teknik-analiz.md → düz FE/BE görev önerisi. Jira'ya HİÇBİR ŞEY YAZMAZ.

    `talimat`: analistin bölme yönlendirmesi (yinelemeli 'yeniden böl' döngüsü);
    boşsa AI işin doğal kırılımına göre böler, doluysa talimata göre.

    Döndürür:
    {
        "gorevler": [{id, katman, summary, description, acceptance_criteria, bagimli_be}],
        "proje": {"key": str, "task_var": bool},
        "ozet": {"fe": N, "be": M, "bagimlilik": K, "toplam": T},
        "plan": "Bu analizi T task'a bölmeyi öneriyorum: N FE + M BE …",
        "talimat": "<uygulanan talimat>"
    }
    """
    env = env_oku()
    cloud_id    = env.get("JIRA_CLOUD_ID", "")
    project_key = env.get("JIRA_PROJECT_KEY", "")
    if not cloud_id or not project_key:
        raise EnvironmentError("JIRA_CLOUD_ID veya JIRA_PROJECT_KEY tanımlı değil.")

    dosya_yolu = OUTPUT_DIR / teknik_analiz_dosya
    if not dosya_yolu.exists():
        raise FileNotFoundError(f"{teknik_analiz_dosya} bulunamadı. Önce teknik analiz yapın.")
    teknik_analiz = dosya_oku(dosya_yolu, MAX_CHARS_GENEL)
    # TL;DR + Canlı Gözlem Kapsamı analistin bilgisidir, göreve girmez
    teknik_analiz = yonetici_ozetini_cikar(teknik_analiz)
    teknik_analiz = canli_gozlem_kapsamini_cikar(teknik_analiz)
    print(f"  Teknik analiz okundu ({len(teknik_analiz):,} karakter)")

    # Task tipi projede var mı? (Task yoksa akış çalışmaz)
    print("  Proje issue type'ları alınıyor...")
    proje = _proje_bilgi(project_key, cloud_id)
    if not proje.get("task_id"):
        raise ValueError(
            f"Proje '{project_key}' 'Task' (görev) tipini desteklemiyor. "
            f"Mevcut tipler: {list(proje['issue_types'].keys())}"
        )

    talimat = (talimat or "").strip()
    print(f"  AI'dan FE/BE görev listesi üretiliyor{' (talimatlı)' if talimat else ''}...")
    gorevler = _gorevler_uret(teknik_analiz, talimat=talimat)

    fe = sum(1 for g in gorevler if g["katman"] == "FE")
    be = sum(1 for g in gorevler if g["katman"] == "BE")
    bagimlilik = sum(len(g["bagimli_be"]) for g in gorevler)
    print(f"  ✓ {fe} FE + {be} BE görev, {bagimlilik} bağımlılık önerildi.")
    return {
        "gorevler": gorevler,
        "proje": {"key": project_key, "task_var": True},
        "ozet": {"fe": fe, "be": be, "bagimlilik": bagimlilik, "toplam": fe + be},
        "plan": _plan_metni(fe, be, bagimlilik, talimat),
        "talimat": talimat,
    }


# ─── Blocks Link Tipi Tespiti ─────────────────────────────────────────────────

def _blocks_link_tipi(cloud_id: str) -> str | None:
    """Projede 'Blocks' issue link tipinin adını döndürür (yoksa None → link atlanır).
    Çoğu Jira'da ad tam 'Blocks'; yine de runtime'da doğrularız."""
    try:
        data = atlassian_get("/rest/api/3/issueLinkType", cloud_id=cloud_id)
        tipler = data.get("issueLinkTypes", []) or []
        for t in tipler:
            if str(t.get("name", "")).strip().lower() == "blocks":
                return t["name"]
        # 'blocks' outward'ı olan herhangi bir tip (ör. 'Dependency')
        for t in tipler:
            if "block" in str(t.get("outward", "")).strip().lower():
                return t["name"]
    except Exception as e:
        print(f"  ⚠ Link tipleri okunamadı ({e}); Blocks bağı atlanabilir.")
    return None


def _blocks_bagla(be_key: str, fe_key: str, tip_adi: str, cloud_id: str) -> bool:
    """BE 'blocks' FE bağı kurar (outwardIssue=BE bloklar, inwardIssue=FE bloklanan)."""
    body = {
        "type": {"name": tip_adi},
        "outwardIssue": {"key": be_key},   # bloklayan
        "inwardIssue": {"key": fe_key},    # bloklanan
    }
    atlassian_post("/rest/api/3/issueLink", body=body, cloud_id=cloud_id)
    return True


# ─── Oluşturma: Seçilen FE/BE görevlerini Task olarak aç + Blocks bağla ──────

def jira_fe_be_olustur(secim: dict, confluence_url: str | None = None) -> dict:
    """Analistin seçtiği/düzenlediği FE/BE görevlerini Jira'da **Task** olarak açar,
    sonra `bagimli_be` haritasına göre BE→FE **Blocks** bağlarını kurar (yalnız
    ikisi de açılan görevler arasında).

    secim = {"gorevler": [{id, katman, summary, description, acceptance_criteria, bagimli_be}]}
            — yalnız açılacak görevler.
    Döndürür: {"gorevler":[{id,key,katman,summary,url}], "linkler":[{be,fe,be_key,fe_key}],
               "toplam":int, "link_sayisi":int, "proje":str, "link_uyari":str|None}
    """
    env = env_oku()
    cloud_id    = env.get("JIRA_CLOUD_ID", "")
    project_key = env.get("JIRA_PROJECT_KEY", "")
    if not cloud_id or not project_key:
        raise EnvironmentError("JIRA_CLOUD_ID veya JIRA_PROJECT_KEY tanımlı değil.")

    gorevler = secim.get("gorevler", []) or []
    if not gorevler:
        raise ValueError("Oluşturulacak görev seçilmedi. En az bir görev seçin.")

    proje = _proje_bilgi(project_key, cloud_id)
    task_id = proje.get("task_id")
    if not task_id:
        raise ValueError(f"Proje '{project_key}' 'Task' tipini desteklemiyor.")

    secilen_idler = {str(g.get("id", "")).strip() for g in gorevler if g.get("id")}

    # BE'leri ÖNCE aç (blocker'lar), sonra FE'ler — deterministik sıra
    sirali = sorted(gorevler, key=lambda g: 0 if str(g.get("katman", "")).upper().startswith("BE") else 1)

    id_key: dict[str, str] = {}
    sonuc_gorevler: list[dict] = []
    from skills.atlassian import jira_site_url
    site = jira_site_url() or env.get("JIRA_URL") or ""

    print(f"  Plan: {len(sirali)} Task açılacak (BE→FE sırayla).")
    for g in sirali:
        gid     = str(g.get("id", "")).strip()
        katman  = "BE" if str(g.get("katman", "")).upper().startswith("BE") else "FE"
        summary = (g.get("summary") or f"{katman} görevi").strip()
        desc    = g.get("description", "") or ""
        ac      = g.get("acceptance_criteria", []) or []
        if confluence_url:
            desc = (desc + f"\n\nAnaliz dokümanı: {confluence_url}").strip()
        adf = _hikaye_adf(desc, ac)
        key = _issue_olustur(
            summary=summary, description_adf=adf, issue_type_id=task_id,
            project_key=project_key, cloud_id=cloud_id,
        )
        if gid:
            id_key[gid] = key
        sonuc_gorevler.append({
            "id": gid, "key": key, "katman": katman, "summary": summary,
            "url": f"{site}/browse/{key}" if site else "",
        })
        print(f"    ✓ {key} [{katman}] {summary[:50]}")

    # Blocks bağları: her FE için bagimli_be listesindeki BE 'blocks' FE
    linkler: list[dict] = []
    link_uyari: str | None = None
    ihtiyac_var = any(
        b in secilen_idler
        for g in gorevler for b in (g.get("bagimli_be") or [])
    )
    tip_adi = _blocks_link_tipi(cloud_id) if ihtiyac_var else None
    if ihtiyac_var and not tip_adi:
        link_uyari = "Projede 'Blocks' link tipi bulunamadı — task'lar açıldı ama bağ kurulamadı."
        print(f"  ⚠ {link_uyari}")

    if tip_adi:
        for g in gorevler:
            fe_id = str(g.get("id", "")).strip()
            fe_key = id_key.get(fe_id)
            if not fe_key:
                continue
            for be_id in (g.get("bagimli_be") or []):
                be_key = id_key.get(str(be_id).strip())
                if not be_key or be_key == fe_key:
                    continue
                try:
                    _blocks_bagla(be_key, fe_key, tip_adi, cloud_id)
                    linkler.append({"be": be_id, "fe": fe_id, "be_key": be_key, "fe_key": fe_key})
                    print(f"    ↪︎ {be_key} blocks {fe_key}")
                except Exception as e:
                    print(f"    ⚠ Bağ kurulamadı ({be_key}→{fe_key}): {e}")
                    if not link_uyari:
                        link_uyari = f"Bazı bağlar kurulamadı (ör. {be_key}→{fe_key}: {e})."

    print(f"✓ {len(sonuc_gorevler)} Task açıldı, {len(linkler)} Blocks bağı kuruldu.")
    return {
        "gorevler": sonuc_gorevler,
        "linkler": linkler,
        "toplam": len(sonuc_gorevler),
        "link_sayisi": len(linkler),
        "proje": project_key,
        "link_uyari": link_uyari,
    }
