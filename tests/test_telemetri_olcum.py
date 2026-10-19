"""Kota ölçümü (ekip) — token sink'e gömülü taşınır + geri çözülür; güncelleme öncesi/sonrası karşılaştırma (offline, 0 token).

Sink (Apps Script) `token` alanını DÜŞÜRÜR → `olay_yaz` token özetini `baglam.dokuman`'a `⟨tok …⟩` olarak gömer;
`_olay_normalize` (okuma + Uzaktan Çek) işareti `token`'a geri taşır ve dokümandan siler. `kota_karsilastirma` olay tipi
bazında KOTA_OLCUM_BASLANGIC öncesi/sonrası ortalama okuma/süre/maliyet + Δ% verir; `istatistik()` bunu döner."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("AUTO_UPDATE", "false")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skills import telemetri as T  # noqa: E402

HATA = 0


def chk(ad, kosul, ek=""):
    global HATA
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if (ek and not kosul) else ""))
    if not kosul:
        HATA += 1


tmp = Path(tempfile.mkdtemp())
T.USAGE_DIR = tmp
T.EVENTS_DOSYA = tmp / "events.jsonl"
T.UZAK_DOSYA = tmp / "remote.jsonl"
T._sink_gonder = lambda kayit: None
T._analist_belirle = lambda a: "Test Analist"

tok = {"girdi": 12, "cikti": 345, "cache_yaz": 6789, "cache_oku": 123456, "cagri": 3, "maliyet_usd": 1.2345}
isaret = T._tok_gom(tok)
chk("gömme biçimi", isaret.startswith("⟨tok g=12,c=345,cy=6789,co=123456,n=3,usd=1.2345⟩"), isaret)
temiz, geri = T._tok_coz("surec-dokumani.docx " + isaret)
chk("çözme: doküman temiz + token geri", temiz == "surec-dokumani.docx" and geri == {"girdi": 12, "cikti": 345, "cache_yaz": 6789, "cache_oku": 123456, "cagri": 3, "maliyet_usd": 1.2345}, (temiz, geri))
chk("işaret yoksa dokunulmaz", T._tok_coz("x.docx") == ("x.docx", None))

T.olay_yaz("gorev_analiz", "ok", sure_ms=60000, baglam={"proje": "P", "dokuman": ""}, token=tok)
T.olay_yaz("surec_analizi", "ok", sure_ms=120000, baglam={"proje": "P", "dokuman": "brd.docx"}, token={"girdi": 5, "cikti": 6, "cache_yaz": 7, "cache_oku": 8, "cagri": 1, "maliyet_usd": 0.1})
T.olay_yaz("mutabakat", "ok", sure_ms=10)   # token'sız olay → gömme yok
ham = [json.loads(sat) for sat in T.EVENTS_DOSYA.read_text(encoding="utf-8").splitlines()]
chk("yerel kayıt: token alanı + dokümanda gömülü işaret (sink bunu korur)", ham[0]["token"] == tok and "⟨tok " in ham[0]["baglam"]["dokuman"]
    and ham[1]["baglam"]["dokuman"].startswith("brd.docx ⟨tok"), ham[0]["baglam"])
chk("token'sız olayda baglam dokunulmaz", ham[2]["baglam"] is None)
okunan = T.olaylari_oku()
chk("okuma normalize: doküman işaretsiz, token korunur", okunan[1]["baglam"]["dokuman"] == "brd.docx" and okunan[1]["token"]["cache_oku"] == 8)
# Sink'ten gelen satır (token sütunu YOK, dokuman'da işaret var) → normalize token'ı geri getirir
sink_satir = {"ts": "2026-10-20T09:00:00", "analist": "A", "olay": "gorev_analiz", "durum": "ok", "sure_ms": 30000,
              "baglam": {"proje": "P", "dokuman": isaret}, "app_versiyon": "abc"}
n = T._olay_normalize(dict(sink_satir))
chk("sink satırı: token geri geldi, doküman boş", n["token"]["cache_oku"] == 123456 and n["baglam"]["dokuman"] == "")

# Karşılaştırma
os.environ["KOTA_OLCUM_BASLANGIC"] = "2026-10-19T18:00:00"
olaylar = [
    {"ts": "2026-10-10T10:00:00", "olay": "gorev_analiz", "sure_ms": 600000, "token": {"girdi": 0, "cache_oku": 3_000_000, "cikti": 1}},
    {"ts": "2026-10-11T10:00:00", "olay": "gorev_analiz", "sure_ms": 600000, "token": {"girdi": 0, "cache_oku": 1_000_000, "cikti": 1}},
    {"ts": "2026-10-20T10:00:00", "olay": "gorev_analiz", "sure_ms": 300000, "token": {"girdi": 0, "cache_oku": 1_000_000, "cikti": 1}},
    {"ts": "2026-10-20T11:00:00", "olay": "surec_analizi", "sure_ms": 100000, "token": {"girdi": 10, "cache_oku": 90, "cikti": 1}},
    {"ts": "2026-10-20T11:00:00", "olay": "mutabakat", "sure_ms": 100},
]
k = T.kota_karsilastirma(olaylar)
g = k["olaylar"]["gorev_analiz"]
chk("önce/sonra ortalama okuma + Δ% (2M → 1M = -50%)", g["once"]["n"] == 2 and g["once"]["ort_okuma"] == 2_000_000 and g["sonra"]["n"] == 1
    and g["sonra"]["ort_okuma"] == 1_000_000 and g["degisim_okuma_pct"] == -50 and g["sonra"]["ort_sure_sn"] == 300, g)
chk("yalnız 'sonra' olan olay: Δ yok", k["olaylar"]["surec_analizi"].get("once") is None and k["olaylar"]["surec_analizi"]["degisim_okuma_pct"] is None)
chk("token'sız olay tabloya girmez", "mutabakat" not in k["olaylar"])
chk("ozet() karşılaştırmayı döner", "karsilastirma" in T.istatistik(gun=30) and T.istatistik(gun=30)["karsilastirma"]["esik"] == "2026-10-19T18:00:00")
os.environ.pop("KOTA_OLCUM_BASLANGIC", None)

print()
if HATA:
    print(f"FAIL — {HATA} kontrol başarısız")
    sys.exit(1)
print("TELEMETRİ ÖLÇÜM TESTLERİ GEÇTİ")
