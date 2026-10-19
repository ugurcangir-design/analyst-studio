"""Kullanım telemetrisi — analiz olaylarını loglar (yalnız metadata, doküman içeriği ASLA).

Tasarım:
- Lokal instance başına append-only JSONL: logs/usage/events.jsonl
- İsteğe bağlı uzak "sink" (USAGE_SINK_URL): fire-and-forget POST — başarısız olursa sessiz.
- Owner (yalnız sen) tarafında dashboard bu olayları okuyup toplar (0-token, deterministik).
- FAIL-SAFE: hiçbir fonksiyon analizi bloklamaz/bozmaz; tüm çağrılar try/except ile izole.

Gizlilik: yalnız metadata (analist, olay tipi, süre, durum, model, açılan task adedi, bağlam
başlıkları) tutulur. BRD/analiz metni ASLA loglanmaz.
"""

from __future__ import annotations

import getpass
import json
import os
import re
import socket
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
USAGE_DIR = BASE_DIR / "logs" / "usage"
EVENTS_DOSYA = USAGE_DIR / "events.jsonl"          # bu makinenin kendi olayları
UZAK_DOSYA = USAGE_DIR / "remote.jsonl"            # owner: sink'ten çekilen ekip verisi
ANALIST_DOSYA = BASE_DIR / "analist.json"          # UI'dan girilen ad-soyad (gitignore)

# Toplayıcı (Apps Script) varsayılan URL — analist makineleri hiçbir şey ayarlamasın diye
# gömülü. Yalnız-YAZMA endpoint'i (okuma OKUMA_ANAHTARI ister). USAGE_SINK_URL env geçersizler.
VARSAYILAN_SINK_URL = "https://script.google.com/macros/s/AKfycbzxMWtRqoTmgWFyc9_LrsNS-ZOK4HvT5BxjB_x8nLL29D77NBklAcImtyNNdyN_xIiF/exec"


def _sink_url() -> str:
    return os.getenv("USAGE_SINK_URL", "").strip() or VARSAYILAN_SINK_URL


# Ekip verisini ÇEKME (okuma) anahtarı — SIR. app-sahibi bunu bir kez owner rolü verdiği kişilerle
# paylaşır; kişi UI'dan KENDİ makinesine girer → 'Uzaktan Çek' çalışır. Google Drive erişimi GEREKMEZ
# (sink app-sahibi adına okur). Yerel dosya gitignore'lu (git'e GİRMEZ) — sır asla repoya taşınmaz.
OKUMA_ANAHTARI_DOSYA = BASE_DIR / "reference" / "usage_sink.json"


def _sink_key() -> str:
    """Okuma anahtarı — öncelik: env `USAGE_SINK_KEY` > yerel `reference/usage_sink.json` ({"key":…})."""
    k = os.getenv("USAGE_SINK_KEY", "").strip()
    if k:
        return k
    try:
        if OKUMA_ANAHTARI_DOSYA.exists():
            return str(json.loads(OKUMA_ANAHTARI_DOSYA.read_text(encoding="utf-8")).get("key", "")).strip()
    except Exception:
        pass
    return ""


def okuma_anahtari_var_mi() -> bool:
    """Ekip verisi çekmek için okuma anahtarı ayarlı mı (env ya da yerel dosya)?"""
    return bool(_sink_key())


def okuma_anahtari_kaydet(key: str) -> None:
    """Okuma anahtarını YEREL gitignore'lu dosyaya yazar (0600; git'e GİRMEZ). Boş → dosyayı siler."""
    key = (key or "").strip()
    OKUMA_ANAHTARI_DOSYA.parent.mkdir(parents=True, exist_ok=True)
    if not key:
        try:
            OKUMA_ANAHTARI_DOSYA.unlink()
        except FileNotFoundError:
            pass
        return
    OKUMA_ANAHTARI_DOSYA.write_text(json.dumps({"key": key}, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(OKUMA_ANAHTARI_DOSYA, 0o600)
    except Exception:
        pass


def analist_kimlik_oku() -> dict:
    """UI'dan kaydedilen analist kimliği: {ad_soyad, eposta}. Yoksa boş dizeler.
    analist.json YEREL + gitignore → ham e-posta git'e ASLA girmez."""
    try:
        d = json.loads(ANALIST_DOSYA.read_text(encoding="utf-8"))
        return {"ad_soyad": str(d.get("ad_soyad", "")).strip(),
                "eposta": str(d.get("eposta", "")).strip()}
    except Exception:
        return {"ad_soyad": "", "eposta": ""}


def analist_oku() -> str:
    """UI'dan kaydedilen analist ad-soyad. Yoksa ''."""
    return analist_kimlik_oku()["ad_soyad"]


def analist_eposta_oku() -> str:
    """UI'dan kaydedilen analist şirket e-postası (küçük harf). Yoksa ''."""
    return analist_kimlik_oku()["eposta"].lower()


# 'Ad Soyad <e-posta>' — kimlik olayının analist alanına gömülü e-postayı ayrıştırır (sink eposta
# sütununu düşürdüğü için; bkz. kimlik_bildir).
_ANALIST_EPOSTA_DESEN = re.compile(r"^(.*?)\s*<([^<>@\s]+@[^<>@\s]+)>\s*$")


def analistler_listesi() -> list[dict]:
    """Kullanım verisinden BENZERSİZ analistler: [{ad, eposta}]. Owner Yetki ekranı rol atamak
    için çeker. HEM remote.jsonl (ekip, Uzaktan Çek) HEM events.jsonl (yerel — owner'ın kendi
    kimlik olayı round-trip beklemeden) okunur. Aynı kişi çift görünmez: e-postalı kayıt için
    e-posta anahtar; e-postasız isim, AYNI isim e-postalı bir kayıtta varsa GİZLENİR (yoksa Yetki'de
    kişi 'atanabilir owner' + 'e-posta bekleniyor' diye iki kez çıkardı)."""
    epostali: dict = {}          # eposta → {ad, eposta}
    epostali_adlar: set = set()  # e-postası olan normalize ad'lar
    adsiz: dict = {}             # ad_lower → {ad, eposta:""}
    for yol in (UZAK_DOSYA, EVENTS_DOSYA):
        if not yol.exists():
            continue
        try:
            satirlar = yol.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for satir in satirlar:
            try:
                o = json.loads(satir)
                if _test_kimligi_mi(o):
                    continue
            except Exception:
                continue
            eposta = (o.get("eposta") or "").strip().lower()
            ad = (o.get("analist") or "").strip()
            # Sink eposta sütununu düşürdüğü için kimlik olayı e-postayı 'Ad <eposta>' olarak
            # analist alanına gömer (kimlik_bildir). Burada geri ayrıştır.
            if not eposta:
                m = _ANALIST_EPOSTA_DESEN.match(ad)
                if m:
                    ad = m.group(1).strip()
                    eposta = m.group(2).strip().lower()
            if eposta:
                if eposta not in epostali:
                    epostali[eposta] = {"ad": ad, "eposta": eposta}
                elif ad and not epostali[eposta]["ad"]:
                    epostali[eposta]["ad"] = ad
                if ad:
                    epostali_adlar.add(ad.lower())
            elif ad:
                adsiz.setdefault(ad.lower(), {"ad": ad, "eposta": ""})
    liste = list(epostali.values()) + [v for k, v in adsiz.items() if k not in epostali_adlar]
    return sorted(liste, key=lambda x: (x["ad"] or x["eposta"]).lower())


def analist_yaz(ad_soyad: str, eposta: str | None = None) -> None:
    """Analist kimliğini yazar. `eposta` None ise mevcut e-posta KORUNUR (ad-soyad tek
    başına güncellenebilir); dize (boş dahil) verilirse üzerine yazılır."""
    try:
        mevcut = analist_kimlik_oku()
        yeni_eposta = mevcut["eposta"] if eposta is None else (eposta or "").strip()
        ANALIST_DOSYA.write_text(
            json.dumps({"ad_soyad": (ad_soyad or "").strip(), "eposta": yeni_eposta},
                       ensure_ascii=False),
            encoding="utf-8")
    except Exception:
        pass

# Geçerli olay tipleri (dashboard kırılımı bunlara göre)
OLAY_TIPLERI = (
    "surec_analizi", "teknik_analiz", "brd_analizi", "kapsam_analizi",
    "mockup", "gorev_analiz", "gorev_guncelle", "mutabakat", "jira_gonder",
)


# Jira task sayacı — bir jira_gonder run'ında açılan issue adedi (hem jira_agent tek-Task
# yolu hem jira_tasks hiyerarşi yolu buraya artırır; run.py okur). Aynı subprocess içinde
# TEK modül örneği (herkes `skills.telemetri` olarak import etmeli).
_JIRA_SAYAC = {"toplam": 0}
_JIRA_KEYLER: list[str] = []


def jira_task_arttir(n: int = 1) -> None:
    try:
        _JIRA_SAYAC["toplam"] += n
    except Exception:
        pass


def jira_key_ekle(key: str) -> None:
    try:
        if key:
            _JIRA_KEYLER.append(str(key))
    except Exception:
        pass


def jira_sayac_sifirla() -> None:
    _JIRA_SAYAC["toplam"] = 0
    _JIRA_KEYLER.clear()


def jira_sayac_oku() -> dict:
    return {"toplam": _JIRA_SAYAC["toplam"], "keyler": list(_JIRA_KEYLER)}


def _analist_belirle(acik: str | None = None) -> str:
    """Analist kimliği önceliği:
    açıkça verilen (login username) > ANALIST env > analist.json (UI ad-soyad)
    > ANALYST_NAME env > OS kullanıcısı."""
    for aday in (acik, os.getenv("ANALIST"), analist_oku(), os.getenv("ANALYST_NAME")):
        if aday and str(aday).strip():
            return str(aday).strip()
    try:
        return getpass.getuser()
    except Exception:
        return "bilinmeyen"


def _app_versiyon() -> str:
    try:
        import subprocess
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(BASE_DIR),
            stderr=subprocess.DEVNULL, text=True, timeout=3,
        ).strip()
    except Exception:
        return ""


def _sink_gonder(olay: dict) -> None:
    """Uzak toplayıcıya (Apps Script) SENKRON POST. Hata yutulur.

    Neden senkron: `olay_yaz` işlemin EN SONUNDA çağrılır (analizi bloklayacak bir şey yok),
    bu yüzden birkaç saniye beklemek sorun değil. Fire-and-forget daemon thread, `run.py`
    gibi KISA ÖMÜRLÜ subprocess'te süreç çıkışından önce öldürülüp POST kayboluyordu →
    süreç/teknik/BRD/kapsam olayları Sheet'e HİÇ ulaşmıyordu (in-process Flask'ta çalışıyordu).
    Senkron POST bu yarışı bitirir; başarısızsa lokal JSONL yedek zaten var."""
    if os.getenv("TELEMETRI_SINK", "").strip().lower() in ("off", "0", "false"):
        return   # test/geliştirme makinesi: ekip Sheet'ine gönderme
    url = _sink_url()
    if not url:
        return
    try:
        import requests  # certifi CA paketi → macOS SSL doğrulaması sorunsuz
        requests.post(url, json=olay, timeout=8)
    except Exception:
        pass


def olay_yaz(
    olay: str,
    durum: str = "ok",
    analist: str | None = None,
    sure_ms: int | None = None,
    model: str | None = None,
    ai_modu: str | None = None,
    jira: dict | None = None,
    baglam: dict | None = None,
    token: dict | None = None,
    kalite: dict | None = None,
) -> None:
    """Tek kullanım olayını lokal JSONL'e yazar + uzak sink'e gönderir. Asla hata fırlatmaz.
    `kalite`: {acik_soru, zorunlu_soru} — analiz kalitesi vekili (soru_sayilari). `baglam.islem` ile birlikte dokümana gömülür.

    `token`: {girdi, cikti, cache_yaz, cache_oku, cagri, maliyet_usd} — o işlemde harcanan
    AI token/maliyet birikimi (base.token_delta). Yoksa None (0-token deterministik işlemler)."""
    try:
        kayit = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "analist": _analist_belirle(analist),
            "eposta": analist_eposta_oku() or None,   # Kullanım Raporu'nda stabil atıf anahtarı
            "olay": olay,
            "durum": durum,
            "sure_ms": sure_ms,
            "model": model,
            "ai_modu": ai_modu,
            "jira": jira or None,
            "baglam": (({**(baglam or {}), "dokuman": ((baglam or {}).get("dokuman") or "") + " "
                         + _tok_gom(token if isinstance(token, dict) else None, kalite, (baglam or {}).get("islem"))})
                       if ((isinstance(token, dict) and token) or isinstance(kalite, dict) or (baglam or {}).get("islem"))
                       else (baglam or None)),
            "token": token or None,
            "kalite": kalite or None,
            "makine": socket.gethostname(),
            "app_versiyon": _app_versiyon(),
        }
        USAGE_DIR.mkdir(parents=True, exist_ok=True)
        with open(EVENTS_DOSYA, "a", encoding="utf-8") as f:
            f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
        _sink_gonder(kayit)
    except Exception:
        pass  # telemetri asla analizi bozmaz


# ── Token gömme (sink sınırı): Apps Script yalnız bilinen sütunları saklar → `token` alanı DÜŞER (ekip verisinde
# token hep boş). `eposta`'daki gibi, token özeti sink'in AYNEN koruduğu `dokuman` sütununa `⟨tok …⟩` işaretiyle GÖMÜLÜR;
# okuma/çekme tarafı (`_olay_normalize`) işareti ayrıştırıp `token`'a geri koyar ve dokümandan siler. Apps Script'e
# dokunmadan güncelleme sonrası tüm analistlerin token tüketimi Kullanım Raporu'na gelir. ─────────────────────────────
_TOK_DESEN = re.compile(r"\s*⟨tok ([^⟩]*)⟩\s*")
_TOK_ALANLAR = (("g", "girdi"), ("c", "cikti"), ("cy", "cache_yaz"), ("co", "cache_oku"), ("n", "cagri"), ("usd", "maliyet_usd"))
# Aynı işarete KALİTE vekilleri (sink bunları da düşürür): i=işlem (analiz/duzelt/cevap/fe-be-ayir…), aq=açık soru, zq=zorunlu soru
_KALITE_ALANLAR = (("aq", "acik_soru"), ("zq", "zorunlu_soru"))


def _tok_gom(token: dict | None, kalite: dict | None = None, islem: str | None = None) -> str:
    parca = []
    for kisa, uzun in _TOK_ALANLAR:
        v = (token or {}).get(uzun, 0) or 0
        parca.append(f"{kisa}={round(float(v), 4) if uzun == 'maliyet_usd' else int(v)}")
    for kisa, uzun in _KALITE_ALANLAR:
        if isinstance(kalite, dict) and kalite.get(uzun) is not None:
            parca.append(f"{kisa}={int(kalite.get(uzun) or 0)}")
    if islem:
        parca.append("i=" + re.sub(r"[^A-Za-z0-9_-]", "", str(islem))[:24])
    return "⟨tok " + ",".join(parca) + "⟩"


def _tok_coz(metin: str) -> tuple[str, dict | None, dict | None, str | None]:
    """→ (doküman_temiz, token|None, kalite|None, islem|None)."""
    m = _TOK_DESEN.search(metin or "")
    if not m:
        return (metin or ""), None, None, None
    tok, kal, islem = {}, {}, None
    for parca in m.group(1).split(","):
        if "=" not in parca:
            continue
        k, v = parca.split("=", 1)
        k = k.strip()
        if k == "i":
            islem = v.strip() or None
            continue
        uzun = dict(_TOK_ALANLAR).get(k)
        if uzun:
            try:
                tok[uzun] = float(v) if uzun == "maliyet_usd" else int(float(v))
            except ValueError:
                pass
            continue
        uzun = dict(_KALITE_ALANLAR).get(k)
        if uzun:
            try:
                kal[uzun] = int(float(v))
            except ValueError:
                pass
    return (metin[:m.start()] + metin[m.end():]).strip(), (tok or None), (kal or None), islem


_TEST_KIMLIK_AD = {"smoke analist", "test analist"}


def _test_kimligi_mi(e: dict) -> bool:
    """Test koşularının seed kimliği (example.com / 'Smoke Analist') — roster/istatistiğe girmesin (sink'e sızmış eski satırlar dahil)."""
    try:
        if (os.getenv("SIRKET_EPOSTA_DOMAIN") or "").strip().lower() == "example.com":
            return False   # test ortamı (domain example.com) — testlerin kendi seed kimlikleri görünür kalsın
        ad = str(e.get("analist") or "").strip().lower()
        ep = str(e.get("eposta") or "").strip().lower()
        return ad in _TEST_KIMLIK_AD or ad.startswith("smoke analist <") or ep.endswith("@example.com") or "@example.com>" in ad
    except Exception:
        return False


def _olay_normalize(e: dict) -> dict:
    """Gömülü işareti `token`/`kalite`/`baglam.islem` alanlarına geri taşır (yoksa), dokümandan siler. Her okuma/çekme yolunda."""
    try:
        b = e.get("baglam")
        if isinstance(b, dict) and isinstance(b.get("dokuman"), str) and "⟨tok " in b["dokuman"]:
            temiz, tok, kal, islem = _tok_coz(b["dokuman"])
            b["dokuman"] = temiz
            if tok and any(tok.values()) and not isinstance(e.get("token"), dict):
                e["token"] = tok
            if kal and not isinstance(e.get("kalite"), dict):
                e["kalite"] = kal
            if islem and not b.get("islem"):
                b["islem"] = islem
    except Exception:
        pass
    return e


_SORU_ID = re.compile(r"\b(?:Q-T-|Q-|PO-)\d{1,3}\b")


def soru_sayilari(md: str) -> dict:
    """Açık soru metninden kalite vekilleri: benzersiz soru id sayısı + 'Zorunlu: Evet' sayısı (0 token)."""
    md = md or ""
    ids = set(_SORU_ID.findall(md))
    if not ids and md.strip() and "tespit edilmedi" not in md.lower():
        ids = {f"#{i}" for i, _ in enumerate(re.findall(r"^\s*(?:[-*•]|\d+[.)])\s+\S", md, re.M))}
    return {"acik_soru": len(ids), "zorunlu_soru": len(re.findall(r"Zorunlu:\s*Evet", md, re.I))}


def kimlik_bildir() -> None:
    """Analist kimliğini (ad + e-posta) sink'e 'kimlik' olayı olarak bildirir → owner Yetki
    ekranında rol atamak için GÖRÜNÜR olsun (analiz çalıştırmayı beklemeden, e-posta girer
    girmez). E-posta yoksa no-op. best-effort (hata yutulur).

    SINK SINIRI: telemetri sink'i (Apps Script/Sheet) yalnız bilinen sütunları saklar; `eposta`
    alanını DÜŞÜRÜR (kanıtlandı: pull'da eposta hep None). Bu yüzden e-postayı, sink'in AYNEN
    koruduğu `analist` alanına 'Ad <eposta>' biçiminde GÖMERİZ; `analistler_listesi` bunu ayrıştırır.
    kimlik olayı istatistikten HARİÇ olduğundan Kullanım Raporu'nu kirletmez."""
    try:
        k = analist_kimlik_oku()
        if not k["eposta"]:
            return
        ad = k["ad_soyad"] or k["eposta"]
        olay_yaz("kimlik", analist=f"{ad} <{k['eposta']}>")
    except Exception:
        pass


def olaylari_oku() -> list[dict]:
    """Owner dashboard veri kaynağı.

    ÇİFT SAYIM ÖNLEME: owner'ın kendi olayları hem lokal `events.jsonl`'de hem de
    Sheet'e POST edildiği için `remote.jsonl`'de (Uzaktan Çek sonrası) bulunur. Bu yüzden
    `remote.jsonl` VARSA yalnız o kullanılır (Sheet = tüm ekip, owner dahil, TEK doğruluk
    kaynağı; hepsi aynı UTC saat biçiminde → tutarlı). Yoksa (henüz çekilmemiş) lokal
    `events.jsonl` kullanılır. Owner en güncel veriyi 'Uzaktan Çek' ile tazeler."""
    olaylar: list[dict] = []
    try:
        if UZAK_DOSYA.exists():
            dosyalar = [UZAK_DOSYA]
        elif EVENTS_DOSYA.exists():
            dosyalar = [EVENTS_DOSYA]
        else:
            return olaylar
        for yol in dosyalar:
            try:
                for satir in yol.read_text(encoding="utf-8").splitlines():
                    satir = satir.strip()
                    if not satir:
                        continue
                    try:
                        o = _olay_normalize(json.loads(satir))
                        if _test_kimligi_mi(o):
                            continue
                        olaylar.append(o)
                    except Exception:
                        continue
            except Exception:
                continue
    except Exception:
        pass
    return olaylar


def _donem_key(ts_str: str, donem: str) -> str:
    """Bir olayın tarihini dönem kovasına çevirir: gün=YYYY-MM-DD, hafta=YYYY-Hnn, ay=YYYY-MM."""
    if donem == "ay":
        return ts_str[:7]
    if donem == "hafta":
        try:
            y, w, _ = datetime.fromisoformat(ts_str[:10]).isocalendar()
            return f"{y}-H{w:02d}"
        except Exception:
            return ts_str[:10]
    return ts_str[:10]


def kota_olcum_baslangic() -> str:
    """Kota optimizasyonu 'öncesi/sonrası' kesim anı (ISO). Vars. Faz 2+3 + tarama-2 yayını; env ile değişir."""
    return (os.getenv("KOTA_OLCUM_BASLANGIC") or "2026-10-19T18:00:00").strip()


def kota_karsilastirma(olaylar: list[dict]) -> dict:
    """Olay tipi bazında güncelleme ÖNCESİ/SONRASI ortalama tüketim (token'lı olaylar): n, ort_okuma (girdi+cache_oku),
    ort_yazma (cache_yaz), ort_sure_sn, ort_maliyet. Ekip verisi gömülü token'la geldiği için güncellemeyi alan
    analistlerin işleri otomatik 'sonra' kovasına düşer (ts kesimi + token var)."""
    esik = kota_olcum_baslangic()
    grup: dict[str, dict[str, dict]] = {}
    for e in olaylar:
        tk = e.get("token")
        if not isinstance(tk, dict) or not (tk.get("girdi") or tk.get("cache_oku") or tk.get("cikti")):
            continue
        olay = e.get("olay") or "diger"
        kova = "sonra" if str(e.get("ts", "")) >= esik else "once"
        g = grup.setdefault(olay, {}).setdefault(kova, {"n": 0, "okuma": 0, "yazma": 0, "cikti": 0, "sure_sn": 0, "maliyet": 0.0})
        g["n"] += 1
        g["okuma"] += int(tk.get("girdi", 0) or 0) + int(tk.get("cache_oku", 0) or 0)
        g["yazma"] += int(tk.get("cache_yaz", 0) or 0)
        g["cikti"] += int(tk.get("cikti", 0) or 0)
        g["sure_sn"] += int((e.get("sure_ms") or 0) / 1000)
        g["maliyet"] += float(tk.get("maliyet_usd", 0) or 0)
    out = {}
    for olay, kovalar in grup.items():
        satir = {}
        for kova, g in kovalar.items():
            n = max(1, g["n"])
            satir[kova] = {"n": g["n"], "ort_okuma": g["okuma"] // n, "ort_yazma": g["yazma"] // n, "ort_cikti": g["cikti"] // n,
                           "ort_sure_sn": g["sure_sn"] // n, "ort_maliyet": round(g["maliyet"] / n, 3)}
        o, s = satir.get("once"), satir.get("sonra")
        satir["degisim_okuma_pct"] = (round((s["ort_okuma"] - o["ort_okuma"]) * 100 / o["ort_okuma"]) if o and s and o["ort_okuma"] else None)
        out[olay] = satir
    return {"esik": esik, "olaylar": out}


_ANALIZ_OLAYLARI = ("gorev_analiz", "surec_analizi", "teknik_analiz")
_DUZELTME_ISLEMLERI = ("duzelt", "cevap")


def kalite_ozeti(olaylar: list[dict]) -> dict:
    """Analiz kalitesi vekilleri — haftalık, olay tipi bazında: analiz sayısı, ort. açık soru, ort. zorunlu soru,
    düzeltme/cevap oranı (düzelt+cevap işlemi ÷ analiz). Yalnız `kalite` taşıyan (yeni sürüm) olaylar soru ortalamasına
    girer; düzeltme işlemleri `baglam.islem` ile sayılır. Azalan açık soru + düzeltme oranı = iyileşme sinyali."""
    grup: dict[tuple, dict] = {}
    for e in olaylar:
        olay = e.get("olay") or ""
        if olay not in _ANALIZ_OLAYLARI:
            continue
        ts = str(e.get("ts", ""))[:10]
        try:
            hafta = datetime.strptime(ts, "%Y-%m-%d").strftime("%G-W%V")
        except ValueError:
            continue
        g = grup.setdefault((hafta, olay), {"hafta": hafta, "olay": olay, "analiz": 0, "duzeltme": 0, "soru_n": 0, "acik": 0, "zorunlu": 0})
        islem = str((e.get("baglam") or {}).get("islem") or "analiz") if isinstance(e.get("baglam"), dict) else "analiz"
        if islem in _DUZELTME_ISLEMLERI:
            g["duzeltme"] += 1
            continue
        g["analiz"] += 1
        k = e.get("kalite")
        if isinstance(k, dict):
            g["soru_n"] += 1
            g["acik"] += int(k.get("acik_soru") or 0)
            g["zorunlu"] += int(k.get("zorunlu_soru") or 0)
    out = []
    for g in sorted(grup.values(), key=lambda x: (x["hafta"], x["olay"])):
        out.append({"hafta": g["hafta"], "olay": g["olay"], "analiz": g["analiz"], "duzeltme": g["duzeltme"],
                    "ort_acik_soru": (round(g["acik"] / g["soru_n"], 1) if g["soru_n"] else None),
                    "ort_zorunlu": (round(g["zorunlu"] / g["soru_n"], 1) if g["soru_n"] else None),
                    "duzeltme_orani": (round(g["duzeltme"] / g["analiz"], 2) if g["analiz"] else None)})
    return {"haftalar": out}


def _olaylari_filtrele(gun: int, analist: str | None = None) -> list[dict]:
    """gün aralığına (+opsiyonel analiste) göre olayları döndürür."""
    kesim = time.time() - gun * 86400
    out = []
    for e in olaylari_oku():
        ts_str = str(e.get("ts", ""))
        try:
            if datetime.fromisoformat(ts_str[:19]).timestamp() < kesim:
                continue
        except Exception:
            pass  # ts parse edilemezse dahil et
        if analist and (e.get("analist") or "") != analist:
            continue
        out.append(e)
    return out


def istatistik(gun: int = 90, donem: str = "gun", analist: str | None = None) -> dict:
    """Deterministik, 0-token özet. donem: gun|hafta|ay (trend kovası). analist: tek kişi filtresi."""
    if donem not in ("gun", "hafta", "ay"):
        donem = "gun"
    # 'kimlik' olayları (Yetki roster'ı için bildirilen ad+e-posta) İŞLEM sayılmaz → istatistikten çıkar.
    aralik = [e for e in _olaylari_filtrele(gun) if (e.get("olay") or "") != "kimlik"]  # dropdown + genel
    tum_analistler = sorted({(e.get("analist") or "bilinmeyen") for e in aralik},
                            key=lambda x: str(x).casefold())
    filtreli = [e for e in aralik if not analist or (e.get("analist") or "") == analist]

    now = datetime.now()
    bugun = now.strftime("%Y-%m-%d")
    y, w, _ = now.isocalendar()
    bu_hafta = f"{y}-H{w:02d}"
    bu_ay = now.strftime("%Y-%m")

    analistler: dict[str, dict] = {}
    tip_toplam: dict[str, int] = {}
    trend: dict[str, int] = {}
    ozet = {"bugun": 0, "bu_hafta": 0, "bu_ay": 0}
    toplam_task = 0
    son_tasklar: list[dict] = []
    # Token/maliyet toplamı (P0 madde 2) — genel + analist bazında birikim.
    token_ozet = {"girdi": 0, "cikti": 0, "cache_yaz": 0, "cache_oku": 0, "cagri": 0, "maliyet_usd": 0.0}

    for e in filtreli:
        a = e.get("analist") or "bilinmeyen"
        olay = e.get("olay") or "diger"
        durum = e.get("durum") or "ok"
        sure = e.get("sure_ms") or 0
        jira = e.get("jira") or {}
        task_adedi = int(jira.get("toplam", 0)) if isinstance(jira, dict) else 0

        an = analistler.setdefault(a, {
            "analist": a, "toplam": 0, "basarili": 0, "hatali": 0,
            "sure_ms_toplam": 0, "jira_task": 0, "tipler": {}, "tip_sure_ms": {},
            "token": {"girdi": 0, "cikti": 0, "cache_yaz": 0, "cache_oku": 0, "cagri": 0, "maliyet_usd": 0.0},
        })
        an["toplam"] += 1
        an["basarili" if durum == "ok" else "hatali"] += 1
        an["sure_ms_toplam"] += sure
        an["jira_task"] += task_adedi
        an["tipler"][olay] = an["tipler"].get(olay, 0) + 1
        an["tip_sure_ms"][olay] = an["tip_sure_ms"].get(olay, 0) + sure

        tk = e.get("token")
        if isinstance(tk, dict):
            for k in token_ozet:
                try:
                    v = tk.get(k, 0) or 0
                    an["token"][k] += v
                    token_ozet[k] += v
                except Exception:
                    pass

        tip_toplam[olay] = tip_toplam.get(olay, 0) + 1
        toplam_task += task_adedi
        ts_str = str(e.get("ts", ""))
        if isinstance(jira, dict) and jira.get("keyler"):
            son_tasklar.append({
                "ts": ts_str, "analist": a,
                "keyler": jira.get("keyler", []),
                "islem": jira.get("islem", ""),
            })
        trend[_donem_key(ts_str, donem)] = trend.get(_donem_key(ts_str, donem), 0) + 1
        if ts_str[:10] == bugun:
            ozet["bugun"] += 1
        if _donem_key(ts_str, "hafta") == bu_hafta:
            ozet["bu_hafta"] += 1
        if ts_str[:7] == bu_ay:
            ozet["bu_ay"] += 1

    for an in analistler.values():
        an["ort_sure_ms"] = round(an["sure_ms_toplam"] / an["toplam"]) if an["toplam"] else 0

    # İsim bazında SABİT sıralama + id (Ali=1, Veli=2 gibi; aynı kadro → aynı id).
    sirali = sorted(analistler.values(), key=lambda x: str(x["analist"]).casefold())
    for i, an in enumerate(sirali, start=1):
        an["id"] = i

    limit = {"gun": 14, "hafta": 12, "ay": 12}.get(donem, 14)
    trend_list = [{"etiket": k, "adet": v} for k, v in sorted(trend.items())[-limit:]]

    return {
        "gun": gun,
        "donem": donem,
        "analist": analist,
        "toplam_analiz": len(filtreli),
        "toplam_jira_task": toplam_task,
        "analist_sayisi": len(analistler),
        "ozet": ozet,
        "token_ozet": {**token_ozet, "maliyet_usd": round(token_ozet["maliyet_usd"], 4)},
        "karsilastirma": kota_karsilastirma(filtreli),
        "kalite": kalite_ozeti(filtreli),
        "analistler": sirali,
        "tum_analistler": list(tum_analistler),
        "tip_toplam": tip_toplam,
        "trend": trend_list,
        "son_tasklar": sorted(son_tasklar, key=lambda x: x["ts"], reverse=True)[:15],
    }


def donem_detay(baslangic: str, bitis: str) -> dict:
    """[baslangic, bitis] (YYYY-MM-DD, iki uç dahil) aralığındaki olaylar için drill-down verisi:
    analist × işlem-tipi matrisi + gün-gün dağılım (hafta/ay bloğuna tıklayınca alt-kırılım)."""
    b, s = (baslangic or "")[:10], (bitis or "")[:10]
    filt = [e for e in olaylari_oku() if b <= str(e.get("ts", ""))[:10] <= s]

    analistler: dict[str, dict] = {}
    tip_toplam: dict[str, int] = {}
    gunluk: dict[str, int] = {}
    for e in filt:
        a = e.get("analist") or "bilinmeyen"
        olay = e.get("olay") or "diger"
        an = analistler.setdefault(a, {"analist": a, "toplam": 0, "tipler": {}})
        an["toplam"] += 1
        an["tipler"][olay] = an["tipler"].get(olay, 0) + 1
        tip_toplam[olay] = tip_toplam.get(olay, 0) + 1
        g = str(e.get("ts", ""))[:10]
        if g:
            gunluk[g] = gunluk.get(g, 0) + 1

    sirali = sorted(analistler.values(), key=lambda x: str(x["analist"]).casefold())
    for i, an in enumerate(sirali, start=1):
        an["id"] = i

    return {
        "baslangic": b, "bitis": s,
        "toplam": len(filt),
        "analistler": sirali,
        "tip_toplam": tip_toplam,
        "gunluk": [{"etiket": k, "adet": v} for k, v in sorted(gunluk.items())],
    }


def uzaktan_cek() -> tuple[bool, str]:
    """Owner (rol): uzak sink'ten (Apps Script GET) ekip olaylarını çekip remote.jsonl'e yazar.

    **SUNUCU-TARAFI E-POSTA KAPISI (birincil):** istemcide SIR/anahtar TUTULMAZ — kullanıcının
    şirket e-postası (`analist_eposta_oku`) `?email=` ile sink'e geçer; Apps Script yalnız
    OWNER e-posta listesindekilere veri döndürür → güncelleme ile otomatik gelir, yalnız owner okur.
    **Geri uyum:** okuma anahtarı (env/yerel) varsa `?read=<key>` de gönderilir → eski Apps Script
    (e-posta kapısı henüz eklenmemiş) owner'da çalışmaya devam eder.
    """
    url = _sink_url()
    key = _sink_key()
    eposta = ""
    try:
        eposta = (analist_eposta_oku() or "").strip()
    except Exception:
        pass
    if not url:
        return False, "USAGE_SINK_URL tanımlı değil."
    if not key and not eposta:
        return False, "Kimlik yok — Ayarlar'dan şirket e-postanızı girin (owner listesinde olmalı)."
    try:
        import requests
        params: dict = {}
        if eposta:
            params["email"] = eposta        # sunucu-tarafı e-posta kapısı (birincil)
        if key:
            params["read"] = key            # geri uyum: eski anahtar yolu
        r = requests.get(url, params=params, timeout=15)
        try:
            veri = r.json()
        except Exception:
            # JSON değil (boş/HTML) → e-posta kapısı bu param'ı tanımıyor demektir.
            if params.get("email") and not params.get("read"):
                return False, ("Sink e-posta kapısına yanıt vermedi — Apps Script'te owner "
                               "e-posta kapısı (doGet) eklenmemiş/deploy edilmemiş olabilir.")
            return False, "Sink beklenmeyen (JSON olmayan) yanıt döndü."
        if not isinstance(veri, list):
            # Apps Script yetkisizde liste yerine {error:...} döndürebilir
            mesaj = ""
            if isinstance(veri, dict):
                mesaj = str(veri.get("error") or veri.get("message") or "")
            return False, (mesaj or "Yetki yok: e-postanız owner listesinde değil (app-sahibinden ekletin).")
        USAGE_DIR.mkdir(parents=True, exist_ok=True)
        with open(UZAK_DOSYA, "w", encoding="utf-8") as f:
            for e in veri:
                f.write(json.dumps(_olay_normalize(e) if isinstance(e, dict) else e, ensure_ascii=False) + "\n")
        return True, f"{len(veri)} olay çekildi."
    except Exception as e:
        return False, f"Çekme başarısız: {e}"
