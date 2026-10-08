"""Onaylı analiz örnek havuzu — few-shot eğitimi (kullanım raporu deseninin İÇERİK versiyonu).

Analist bir analizi ONAYLAYINCA (süreç/teknik) onaylı çıktı bir 'örnek' olarak:
  (1) YEREL `reference/ornekler/`'e yazılır (agent hemen kendi onaylı işinden öğrenir),
  (2) merkezi sink'e (telemetri Apps Script) push edilir → `ornekleri_cek()` ('Uzaktan Çek'
      benzeri) ile TÜM analistlerin havuzuna iner (ekip paylaşımı).
Analiz üretiminde `ornek_bloklari()` mevcut girdiye EN ALAKALI örnekleri (BM25) prompt'a
"onaylı örnek — stil/derinlik referansı" olarak enjekte eder.

GİZLİLİK: bu özellik analiz İÇERİĞİNİ merkeze taşır (app-sahibi bilinçli kararı; kullanım
raporunda yalnız metadata giderdi). Yerel havuz gitignore'lu (git'e girmez). FAIL-SAFE:
hiçbir fonksiyon analizi/onayı bloklamaz — tüm çağrılar try/except ile izole.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
ORNEK_DIR = BASE_DIR / "reference" / "ornekler"
_DURUM_DOSYA = ORNEK_DIR / ".durum.json"   # son çekim bilgisi (görünürlük; few-shot'ı etkilemez)
_MAX_ORNEK = 80          # yerel havuz üst sınırı (en yeni tutulur)
_MAX_ICERIK = 45000      # örnek başına içerik tavanı (Sheet hücre limiti ~50k)


def _slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (s or "").strip().lower()).strip("-")
    return s[:40] or "ornek"


def _id(tip: str, icerik: str) -> str:
    return hashlib.sha1((tip + "|" + icerik[:3000]).encode("utf-8", "ignore")).hexdigest()[:12]


def _temizle(md: str) -> str:
    """[K:] kanıt etiketlerini çıkar (örnek stil referansı — etiket gürültüsü girmez)."""
    try:
        from .base import kanit_etiketlerini_temizle
        return kanit_etiketlerini_temizle(md or "")
    except Exception:
        return md or ""


def _ayni_key_temizle(jira_key: str, yeni_id: str) -> None:
    """Aynı jira_key'e ait ESKİ yerel örnekleri sil → task başına EN GÜNCEL tek örnek
    (yeniden üretim/düzenleme havuzu şişirmesin). jira_key boşsa no-op (pipeline onayları)."""
    jk = (jira_key or "").strip()
    if not jk:
        return
    try:
        for p in ORNEK_DIR.glob("*.json"):
            if p.name.startswith("."):
                continue
            try:
                o = json.loads(p.read_text(encoding="utf-8"))
                if (o.get("jira_key") or "").strip() == jk and o.get("id") != yeni_id:
                    p.unlink(missing_ok=True)
            except Exception:
                continue
    except Exception:
        pass


def _yaz(kayit: dict) -> None:
    ORNEK_DIR.mkdir(parents=True, exist_ok=True)
    _ayni_key_temizle(kayit.get("jira_key", ""), kayit["id"])
    yol = ORNEK_DIR / f"{kayit['tip']}_{kayit['id']}.json"
    yol.write_text(json.dumps(kayit, ensure_ascii=False), encoding="utf-8")
    _buda()


def _buda() -> None:
    """Havuzu _MAX_ORNEK ile sınırla (en eski JSON'ları sil)."""
    try:
        dosyalar = sorted((p for p in ORNEK_DIR.glob("*.json") if not p.name.startswith(".")),
                          key=lambda p: p.stat().st_mtime, reverse=True)
        for p in dosyalar[_MAX_ORNEK:]:
            p.unlink(missing_ok=True)
    except Exception:
        pass


def _sink_push(kayit: dict) -> None:
    """Örneği merkezi sink'e (telemetri Apps Script) 'ornek' olayı olarak POST eder (best-effort)."""
    try:
        from . import telemetri
        import requests
        url = telemetri._sink_url()
        if not url:
            return
        govde = {
            "olay": "ornek", "tip": kayit["tip"], "ts": kayit["ts"],
            "analist": kayit.get("analist", ""), "eposta": kayit.get("eposta", ""),
            "proje": kayit.get("proje", ""), "jira_key": kayit.get("jira_key", ""),
            "ozet": kayit.get("ozet", ""), "icerik": kayit.get("icerik", ""),
            "id": kayit["id"],
        }
        requests.post(url, json=govde, timeout=10)
    except Exception:
        pass  # sink erişilemezse yerel havuz yine dolar


def ornekleri_paylas(mevcut_idler: set | None = None) -> int:
    """Yerel havuzdaki örnekleri merkezi sink'e (yeniden) push eder — 'eski işleri' ortak
    havuza taşır (Yol 1). `mevcut_idler` (çekilen merkez id'leri) verilirse onlar atlanır →
    gereksiz push yok, yalnız yerelde olup merkezde olmayanlar gider. Sink id-dedup'lar.
    Dönen: push denenen örnek sayısı. Best-effort (asla patlamaz)."""
    n = 0
    try:
        mevcut = mevcut_idler or set()
        for o in _oku_hepsi():
            oid = o.get("id")
            if not oid or oid in mevcut:
                continue
            if (o.get("tip") in ("surec", "teknik")) and len((o.get("icerik") or "")) >= 300:
                _sink_push(o)
                n += 1
    except Exception:
        pass
    return n


def ornek_kaydet(tip: str, cikti_md: str, girdi_ozeti: str = "",
                 proje: str = "", jira_key: str = "") -> bool:
    """Onaylı analizi örnek olarak yereli+sink'e kaydeder. tip: 'surec'|'teknik'. Fail-safe."""
    try:
        tip = (tip or "").strip().lower()
        icerik = _temizle(cikti_md or "").strip()
        if tip not in ("surec", "teknik") or len(icerik) < 300:
            return False  # anlamlı bir örnek değil
        if len(icerik) > _MAX_ICERIK:
            icerik = icerik[:_MAX_ICERIK] + "\n\n…(örnek kırpıldı)"
        try:
            from . import telemetri
            kimlik = telemetri.analist_kimlik_oku()
            analist, eposta = kimlik.get("ad_soyad", ""), kimlik.get("eposta", "")
        except Exception:
            analist, eposta = "", ""
        kayit = {
            "id": _id(tip, icerik), "tip": tip, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "analist": analist, "eposta": eposta, "proje": (proje or "").strip(),
            "jira_key": (jira_key or "").strip(), "ozet": (girdi_ozeti or "")[:400].strip(),
            "icerik": icerik,
        }
        _yaz(kayit)
        _sink_push(kayit)
        return True
    except Exception:
        return False


def ornekleri_cek() -> tuple[bool, str]:
    """Merkezi sink'ten ekip örneklerini çekip yerel havuza yazar ('Uzaktan Çek' benzeri).
    Sunucu-tarafı e-posta kapısı (owner listesi) ile aynı yetki; ?ornekler=1&email=<...>."""
    try:
        from . import telemetri
        import requests
        url = telemetri._sink_url()
        if not url:
            return False, "Sink URL yok."
        params = {"ornekler": "1"}
        eposta = ""
        try:
            eposta = (telemetri.analist_eposta_oku() or "").strip()
        except Exception:
            pass
        if eposta:
            params["email"] = eposta
        key = ""
        try:
            key = telemetri._sink_key()
        except Exception:
            pass
        if key:
            params["read"] = key
        r = requests.get(url, params=params, timeout=20)
        try:
            veri = r.json()
        except Exception:
            return False, "Sink 'ornekler' ucuna yanıt vermedi (Apps Script güncellenmemiş olabilir)."
        if not isinstance(veri, list):
            mesaj = veri.get("error") if isinstance(veri, dict) else ""
            return False, (mesaj or "Yetki yok ya da beklenmeyen yanıt.")
        n = 0
        ORNEK_DIR.mkdir(parents=True, exist_ok=True)
        for o in veri:
            try:
                tip = (o.get("tip") or "").strip().lower()
                icerik = (o.get("icerik") or "").strip()
                if tip not in ("surec", "teknik") or len(icerik) < 300:
                    continue
                kayit = {
                    "id": o.get("id") or _id(tip, icerik), "tip": tip,
                    "ts": o.get("ts", ""), "analist": o.get("analist", ""),
                    "eposta": o.get("eposta", ""), "proje": o.get("proje", ""),
                    "jira_key": o.get("jira_key", ""), "ozet": o.get("ozet", ""),
                    "icerik": icerik,
                }
                (ORNEK_DIR / f"{tip}_{kayit['id']}.json").write_text(
                    json.dumps(kayit, ensure_ascii=False), encoding="utf-8")
                n += 1
            except Exception:
                continue
        # Yerelde olup merkezde OLMAYAN örnekleri merkeze taşı (eski işleri ortaklaştır;
        # sink id-dedup'lar → çift satır olmaz). Her analistin günlük sync'i havuzu birleştirir.
        paylasilan = 0
        try:
            cekilen_idler = {o.get("id") for o in veri if isinstance(o, dict) and o.get("id")}
            paylasilan = ornekleri_paylas(cekilen_idler)
        except Exception:
            paylasilan = 0
        _buda()
        msg = f"{n} örnek çekildi" + (f", {paylasilan} yerel örnek paylaşıldı" if paylasilan else "") + "."
        _durum_yaz(True, msg)
        return True, msg
    except Exception as e:
        _durum_yaz(False, f"Çekme başarısız: {e}")
        return False, f"Çekme başarısız: {e}"


def _durum_yaz(ok: bool, mesaj: str) -> None:
    try:
        ORNEK_DIR.mkdir(parents=True, exist_ok=True)
        _DURUM_DOSYA.write_text(json.dumps(
            {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": ok, "mesaj": mesaj},
            ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def durum() -> dict:
    """Görünürlük: yerel havuz adedi (tip bazlı) + son çekim bilgisi. Owner panelinde gösterilir."""
    hepsi = _oku_hepsi()
    tipler: dict = {}
    for o in hepsi:
        t = o.get("tip", "?")
        tipler[t] = tipler.get(t, 0) + 1
    son = {}
    try:
        if _DURUM_DOSYA.exists():
            son = json.loads(_DURUM_DOSYA.read_text(encoding="utf-8"))
    except Exception:
        son = {}
    return {"toplam": len(hepsi), "tipler": tipler, "limit": _MAX_ORNEK, "son_cekim": son}


def tani() -> dict:
    """Teşhis: sink 'ornekler' ucuna AYNEN istek atıp ham yanıtı özetler — '0 çekildi' nedeni.
    Owner panelinde gösterilir; sır (anahtar/e-posta) döndürmez, yalnız gönderilip gönderilmediğini."""
    out: dict = {"email_gonderildi": False, "read_gonderildi": False}
    try:
        from . import telemetri
        import requests
        url = telemetri._sink_url()
        out["url_son"] = ("…" + url[-32:]) if url else ""
        if not url:
            out["hata"] = "Sink URL yok."
            return out
        params = {"ornekler": "1"}
        try:
            em = (telemetri.analist_eposta_oku() or "").strip()
            if em:
                params["email"] = em
                out["email_gonderildi"] = True
        except Exception:
            pass
        try:
            k = telemetri._sink_key()
            if k:
                params["read"] = k
                out["read_gonderildi"] = True
        except Exception:
            pass
        r = requests.get(url, params=params, timeout=20)
        out["http_status"] = r.status_code
        out["ham_ozet"] = (r.text or "")[:200]
        try:
            veri = r.json()
        except Exception:
            out["yanit_tipi"] = "metin (JSON değil — muhtemelen yetki/forbidden ya da eski kod)"
            return out
        if isinstance(veri, list):
            out["yanit_tipi"] = "liste"
            out["liste_adet"] = len(veri)
            out["gecerli_ornek"] = sum(
                1 for o in veri if isinstance(o, dict)
                and (o.get("tip") in ("surec", "teknik")) and len((o.get("icerik") or "")) >= 300)
            # Örnek şeması mı yoksa kullanım-olayı mı (eski kod bunu döndürür)?
            ilk = veri[0] if veri else {}
            out["ornek_semasi"] = isinstance(ilk, dict) and ("icerik" in ilk or "tip" in ilk)
            out["kullanim_semasi"] = isinstance(ilk, dict) and ("olay" in ilk)
        elif isinstance(veri, dict):
            out["yanit_tipi"] = "nesne"
            out["mesaj"] = str(veri.get("error", ""))[:200]
        return out
    except Exception as e:
        out["hata"] = str(e)[:200]
        return out


def _oku_hepsi() -> list[dict]:
    out = []
    try:
        for p in ORNEK_DIR.glob("*.json"):
            if p.name.startswith("."):   # .durum.json gibi meta dosyaları örnek sayma
                continue
            try:
                out.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                continue
    except Exception:
        pass
    return out


def ornek_listesi() -> list[dict]:
    """Kürasyon için özet liste (içeriksiz): [{id, tip, proje, jira_key, analist, ts, ozet}]."""
    liste = [{k: o.get(k, "") for k in ("id", "tip", "proje", "jira_key", "analist", "ts", "ozet")}
             for o in _oku_hepsi()]
    return sorted(liste, key=lambda x: str(x.get("ts", "")), reverse=True)


def ornek_sil(ornek_id: str) -> bool:
    try:
        n = False
        for p in ORNEK_DIR.glob(f"*_{ornek_id}.json"):
            p.unlink(missing_ok=True)
            n = True
        return n
    except Exception:
        return False


def ornek_bloklari(sorgu_metni: str, tip: str | None = None, n: int = 2,
                   butce: int = 16000) -> list[dict]:
    """Few-shot: mevcut girdiye (sorgu_metni) EN ALAKALI n örneği BM25 ile seçip prompt
    içerik bloğu listesi döndürür. Örnek yoksa/alaka yoksa boş liste. Fail-safe (asla patlamaz)."""
    try:
        havuz = [o for o in _oku_hepsi() if not tip or o.get("tip") == tip]
        if not havuz or not (sorgu_metni or "").strip():
            return []
        # BM25 sıralama (retrieval hazır; yoksa basit örtüşme).
        sirali_idx: list[int]
        try:
            from .retrieval import BM25, _tokenle
            dokumanlar = [_tokenle(o.get("icerik", "") + " " + o.get("ozet", "")) for o in havuz]
            bm = BM25(dokumanlar)
            sirali = bm.sirala(_tokenle(sorgu_metni))
            sirali_idx = [i for i, _s in sirali]
        except Exception:
            q = set(re.findall(r"\w+", (sorgu_metni or "").lower()))
            skor = [(i, len(q & set(re.findall(r"\w+", o.get("icerik", "").lower()))))
                    for i, o in enumerate(havuz)]
            sirali_idx = [i for i, _s in sorted(skor, key=lambda x: x[1], reverse=True)]
        bloklar: list[dict] = []
        kalan = butce
        for i in sirali_idx[:max(1, n)]:
            o = havuz[i]
            icerik = o.get("icerik", "")
            pay = min(len(icerik), kalan, butce // max(1, n))
            if pay < 300:
                break
            etiket = ("### ONAYLI ÖRNEK ANALİZ (ekip tarafından onaylanmış — STİL/DERİNLİK "
                      "referansı; BİREBİR KOPYALAMA, kendi konun için üret)"
                      + (f" · proje: {o.get('proje')}" if o.get("proje") else "")
                      + (f" · {o.get('jira_key')}" if o.get("jira_key") else "") + "\n\n")
            bloklar.append({"type": "text", "text": etiket + icerik[:pay]})
            kalan -= pay
            if kalan < 300:
                break
        return bloklar
    except Exception:
        return []
