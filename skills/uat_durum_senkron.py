"""UAT Durum Senkronu — TRADE/OPS task'ı geliştirmeye alınınca ilişkili UAT task'ını 'Devam Ediyor'a taşır.

Analist UAT board'undaki (MBSUATEAM) maddeyi elle güncellemesin diye periyodik (vars. 2 saat) kontrol:
  · UAT task'ı Backlog / Yapılacaklar'da (bilinçli Hold/Tamam/İptal'e DOKUNULMAZ, geri yön YOK)
  · DOĞRUDAN Jira linkiyle bağlı TRADE/OPS task'larından biri geliştirmeye alınmış
    (Devam Ediyor ve sonrası: Test, READY FOR TEST, UAT, Tamam…) → Story köprüsü KULLANILMAZ
  → UAT task'ı 'Devam Ediyor'a geçirilir + "🤖 … geliştirmeye alındı" yorumu düşülür.

Güvenlik: varsayılan KAPALI (`aktif:false`) + ilk açılış **rapor modu** (hiçbir şey değiştirmeden "şunları
taşıyacaktım" listesi); analist onaylayınca `mod:'otomatik'`. Ayar `reference/uat_senkron.json` (makine-yerel,
gitignore) · durum/geçmiş `output/uat-senkron/durum.json`. 0 token (yalnız Jira REST). Bağlı task'ın durumu
issue-link verisinde zaten gelir → ek Jira okuması yok. Taşıma idempotent: yalnız hâlâ Backlog/Yapılacaklar
olan UAT taşınır (birden çok analistte açık olsa da çift işlem olmaz).
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from .atlassian import atlassian_get, atlassian_post
from .jira_gorevleri import _cloud_id, _iptal_statusu_mu, _KAPSAYICI_TIP_ADLARI

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
AYAR_DOSYA = BASE_DIR / "reference" / "uat_senkron.json"
DURUM_DOSYA = BASE_DIR / "output" / "uat-senkron" / "durum.json"

VARSAYILAN = {
    "aktif": False,
    "mod": "rapor",                       # rapor = değiştirmeden listele · otomatik = taşı + yorum
    "aralik_sn": 7200,                    # 2 saat
    "uat_proje": "MBSUATEAM",
    "hedef_projeler": ["MBSTRADE", "MBSOPS"],
    "hedef_durum": "Devam Ediyor",        # UAT task'ının taşınacağı durum
    "uat_kaynak_durumlar": ["Backlog", "Yapılacaklar"],
    # "Geliştirmeye alındı" = Devam Ediyor VE sonrası (2 saatlik aralıkta ileri geçen task kaçmasın)
    "tetik_durumlar": ["Devam Ediyor", "In Progress", "Code Review", "In Review", "Test", "READY FOR TEST",
                       "TEST BLOCKED", "UAT", "Tamam", "Done", "Closed", "Resolved"],
}
_MIN_ARALIK = 600
_GECMIS_MAX = 300


def _norm(s: str) -> str:
    return (s or "").replace("İ", "i").replace("I", "ı").strip().casefold()


def ayarlar() -> dict:
    a = dict(VARSAYILAN)
    try:
        if AYAR_DOSYA.exists():
            d = json.loads(AYAR_DOSYA.read_text(encoding="utf-8"))
            a.update({k: v for k, v in d.items() if k in VARSAYILAN and v not in (None, "", [])})
    except Exception as e:
        logger.warning("UAT senkron ayarı okunamadı (varsayılan kullanılıyor): %s", e)
    a["aktif"] = bool(a["aktif"])
    a["mod"] = a["mod"] if a["mod"] in ("rapor", "otomatik") else "rapor"
    a["aralik_sn"] = max(_MIN_ARALIK, int(a.get("aralik_sn") or VARSAYILAN["aralik_sn"]))
    return a


def ayar_kaydet(degisim: dict) -> dict:
    """Yalnız aktif / mod / aralik_sn değiştirilebilir (proje/durum listeleri dosyadan)."""
    try:
        mevcut = json.loads(AYAR_DOSYA.read_text(encoding="utf-8")) if AYAR_DOSYA.exists() else {}
    except Exception:
        mevcut = {}
    if "aktif" in degisim:
        mevcut["aktif"] = bool(degisim["aktif"])
    if "mod" in degisim:
        if degisim["mod"] not in ("rapor", "otomatik"):
            raise ValueError("mod 'rapor' ya da 'otomatik' olmalı")
        mevcut["mod"] = degisim["mod"]
    if "aralik_sn" in degisim:
        mevcut["aralik_sn"] = max(_MIN_ARALIK, int(degisim["aralik_sn"]))
    AYAR_DOSYA.parent.mkdir(parents=True, exist_ok=True)
    AYAR_DOSYA.write_text(json.dumps(mevcut, ensure_ascii=False, indent=2), encoding="utf-8")
    return ayarlar()


def durum_oku() -> dict:
    try:
        return json.loads(DURUM_DOSYA.read_text(encoding="utf-8")) if DURUM_DOSYA.exists() else {}
    except Exception:
        return {}


def _durum_yaz(d: dict) -> None:
    DURUM_DOSYA.parent.mkdir(parents=True, exist_ok=True)
    DURUM_DOSYA.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Plan (deterministik, Jira'ya YAZMAZ) ─────────────────────────────────────
def plan_hesapla(uat_gorevler: list[dict], ayar: dict) -> list[dict]:
    """Taşınacak UAT task'ları: kaynak durumda + doğrudan linkli hedef task geliştirmeye alınmış."""
    kaynak = {_norm(d) for d in ayar["uat_kaynak_durumlar"]}
    tetik = {_norm(d) for d in ayar["tetik_durumlar"]}
    projeler = {p.upper() for p in ayar["hedef_projeler"]}
    plan: list[dict] = []
    for u in uat_gorevler:
        if _norm(u.get("status", "")) not in kaynak:
            continue
        if _norm(u.get("type", "")) in _KAPSAYICI_TIP_ADLARI:
            continue   # Epic/Story UAT kalemi değil
        tetikleyenler = []
        for lk in u.get("baglantililar", []) or []:
            k = (lk.get("key") or "").upper()
            if k.split("-", 1)[0] not in projeler:
                continue
            if _norm(lk.get("type", "")) in _KAPSAYICI_TIP_ADLARI:
                continue   # yalnız DOĞRUDAN iş kalemi linki (Story köprüsü yok)
            durum = lk.get("durum", "")
            if _iptal_statusu_mu(durum) or _norm(durum) not in tetik:
                continue
            tetikleyenler.append({"key": k, "durum": durum, "ozet": lk.get("summary", "")})
        if tetikleyenler:
            plan.append({"uat_key": u["key"], "uat_ozet": u.get("summary", ""), "uat_durum": u.get("status", ""),
                         "tetikleyenler": tetikleyenler})
    return plan


def _uat_gorevlerini_cek(ayar: dict, cloud_id: str) -> list[dict]:
    from .backlog_senkron import _jql_ara, _jql_kacis
    durumlar = ", ".join(f'"{_jql_kacis(d)}"' for d in ayar["uat_kaynak_durumlar"])
    jql = f'project = "{_jql_kacis(ayar["uat_proje"])}" AND status IN ({durumlar}) ORDER BY created ASC'
    return _jql_ara(jql, cloud_id)   # link filtresi plan_hesapla'da (yalnız doğrudan linkli olanlar)


# ── Uygulama (Jira'ya YAZAR) ─────────────────────────────────────────────────
def _yorum_metni(it: dict, hedef_durum: str) -> str:
    t = ", ".join(f"{x['key']} ({x['durum']})" for x in it["tetikleyenler"])
    return (f"🤖 **Analyst Studio — otomatik durum güncellemesi:** İlişkili geliştirme task'ı {t} işleme "
            f"alındığı için bu UAT maddesi '{it['uat_durum']}' → '{hedef_durum}' durumuna alındı.")


def tasi(it: dict, hedef_durum: str, cloud_id: str, *, yorum: bool = True) -> dict:
    """Tek UAT task'ını hedef duruma geçirir. Geçiş yoksa ya da hata varsa {ok:False, hata}."""
    key = it["uat_key"]
    try:
        gecisler = (atlassian_get(f"/rest/api/3/issue/{key}/transitions", cloud_id) or {}).get("transitions", [])
        h = _norm(hedef_durum)
        gecis = next((g for g in gecisler if _norm((g.get("to") or {}).get("name", "")) == h), None) \
            or next((g for g in gecisler if _norm(g.get("name", "")) == h), None)
        if not gecis:
            mevcut = ", ".join(sorted({(g.get("to") or {}).get("name", "") for g in gecisler})) or "yok"
            return {"ok": False, "hata": f"'{hedef_durum}' geçişi bulunamadı (mümkün: {mevcut})"}
        atlassian_post(f"/rest/api/3/issue/{key}/transitions", {"transition": {"id": gecis["id"]}}, cloud_id)
    except Exception as e:
        return {"ok": False, "hata": str(e)[:200]}
    yorum_ok = True
    if yorum:
        try:
            from .jira_kopru import jira_yorum_ekle
            jira_yorum_ekle(key, _yorum_metni(it, hedef_durum))
        except Exception as e:
            yorum_ok = False
            logger.warning("UAT senkron: %s taşındı ama yorum eklenemedi: %s", key, e)
    return {"ok": True, "yorum": yorum_ok}


def tur(uygula: bool | None = None) -> dict:
    """Bir kontrol turu. uygula=None → ayardaki moda göre (otomatik=uygula). Sonuç durum dosyasına yazılır."""
    ayar = ayarlar()
    cloud_id = _cloud_id()
    uat = _uat_gorevlerini_cek(ayar, cloud_id)
    plan = plan_hesapla(uat, ayar)
    uygulanacak = (ayar["mod"] == "otomatik") if uygula is None else bool(uygula)
    sonuclar: list[dict] = []
    if uygulanacak:
        for it in plan:
            r = tasi(it, ayar["hedef_durum"], cloud_id)
            sonuclar.append({**it, **r})
    d = durum_oku()
    simdi = time.time()
    tasinan = [s for s in sonuclar if s.get("ok")]
    gecmis = (d.get("gecmis") or []) + [{"ts": simdi, "uat_key": s["uat_key"], "uat_ozet": s["uat_ozet"],
                                         "eski": s["uat_durum"], "tetikleyenler": s["tetikleyenler"]}
                                        for s in tasinan]
    d.update({
        "son_tur_ts": simdi, "son_mod": "uygula" if uygulanacak else "rapor",
        "taranan": len(uat), "plan": plan, "sonuclar": sonuclar,
        "tasinan": len(tasinan), "hatali": sum(1 for s in sonuclar if not s.get("ok")),
        "gecmis": gecmis[-_GECMIS_MAX:], "son_hata": None,
    })
    _durum_yaz(d)
    logger.info("UAT senkron turu: %d UAT tarandı · %d aday · %s", len(uat), len(plan),
                f"{len(tasinan)} taşındı" if uygulanacak else "rapor modu (değişiklik yok)")
    return d


def hata_kaydet(mesaj: str) -> None:
    d = durum_oku()
    d.update({"son_hata_ts": time.time(), "son_hata": (mesaj or "")[:300]})   # tur zamanı DEĞİŞMEZ → kısa aralıkla tekrar denenir
    _durum_yaz(d)


def sira_geldi_mi(ayar: dict | None = None) -> bool:
    ayar = ayar or ayarlar()
    son = durum_oku().get("son_tur_ts") or 0
    return ayar["aktif"] and (time.time() - son) >= ayar["aralik_sn"]
