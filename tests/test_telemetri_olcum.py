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
os.environ.setdefault("SIRKET_EPOSTA_DOMAIN", "example.com")   # test kimliği filtresi kapalı (test ortamı)
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
temiz, geri, _k, _i = T._tok_coz("surec-dokumani.docx " + isaret)
chk("çözme: doküman temiz + token geri", temiz == "surec-dokumani.docx" and geri == {"girdi": 12, "cikti": 345, "cache_yaz": 6789, "cache_oku": 123456, "cagri": 3, "maliyet_usd": 1.2345}, (temiz, geri))
chk("işaret yoksa dokunulmaz", T._tok_coz("x.docx") == ("x.docx", None, None, None))

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

# ── Kalite vekilleri ──
chk("soru_sayilari: Q-T id'leri + zorunlu", T.soru_sayilari("### Q-T-001: a\n- Zorunlu: Evet\n### Q-T-002: b\n- Zorunlu: Hayır\nbkz Q-T-001") == {"acik_soru": 2, "zorunlu_soru": 1})
chk("soru_sayilari: 'tespit edilmedi' → 0", T.soru_sayilari("Açık soru tespit edilmedi.") == {"acik_soru": 0, "zorunlu_soru": 0})
chk("soru_sayilari: id'siz madde listesi → madde sayısı", T.soru_sayilari("- x nedir?\n- y nedir?")["acik_soru"] == 2)
T.olay_yaz("gorev_analiz", "ok", sure_ms=1000, baglam={"gorev": "K-1", "islem": "analiz"}, token=tok, kalite={"acik_soru": 3, "zorunlu_soru": 1})
T.olay_yaz("gorev_analiz", "ok", sure_ms=500, baglam={"gorev": "K-1", "islem": "duzelt"})
ham = [json.loads(sat) for sat in T.EVENTS_DOSYA.read_text(encoding="utf-8").splitlines()]
chk("kalite + işlem dokümana gömülü (aq/zq/i)", "aq=3" in ham[-2]["baglam"]["dokuman"] and "zq=1" in ham[-2]["baglam"]["dokuman"] and "i=analiz" in ham[-2]["baglam"]["dokuman"]
    and "i=duzelt" in ham[-1]["baglam"]["dokuman"], ham[-1]["baglam"])
sink2 = {"ts": "2026-10-20T09:00:00", "olay": "gorev_analiz", "baglam": {"proje": "", "dokuman": ham[-2]["baglam"]["dokuman"]}}
n2 = T._olay_normalize(dict(sink2))
chk("sink satırı: kalite + islem geri geldi", n2["kalite"] == {"acik_soru": 3, "zorunlu_soru": 1} and n2["baglam"]["islem"] == "analiz" and n2["token"]["cache_oku"] == 123456)
sink3 = T._olay_normalize({"ts": "x", "olay": "gorev_analiz", "baglam": {"dokuman": ham[-1]["baglam"]["dokuman"]}})
chk("token'sız düzeltme satırı: token alanı yok, islem=duzelt", "token" not in sink3 and sink3["baglam"]["islem"] == "duzelt")
ko = T.kalite_ozeti([
    {"ts": "2026-10-13T10:00:00", "olay": "gorev_analiz", "baglam": {"islem": "analiz"}, "kalite": {"acik_soru": 6, "zorunlu_soru": 2}},
    {"ts": "2026-10-14T10:00:00", "olay": "gorev_analiz", "baglam": {"islem": "fe-be-ayir"}, "kalite": {"acik_soru": 2, "zorunlu_soru": 0}},
    {"ts": "2026-10-14T11:00:00", "olay": "gorev_analiz", "baglam": {"islem": "duzelt"}},
    {"ts": "2026-10-14T12:00:00", "olay": "gorev_analiz", "baglam": {"islem": "cevap"}},
    {"ts": "2026-10-20T10:00:00", "olay": "surec_analizi", "kalite": {"acik_soru": 4, "zorunlu_soru": 1}},
    {"ts": "2026-10-20T10:00:00", "olay": "surec_analizi", "baglam": {"islem": "duzelt"}},
    {"ts": "2026-10-20T10:00:00", "olay": "mutabakat"},
])["haftalar"]
g1 = [h for h in ko if h["olay"] == "gorev_analiz"][0]
chk("kalite_ozeti: haftalık ort açık soru 4.0, zorunlu 1.0, düzeltme 2/2 analiz = 100%", g1["hafta"] == "2026-W42" and g1["analiz"] == 2
    and g1["ort_acik_soru"] == 4.0 and g1["ort_zorunlu"] == 1.0 and g1["duzeltme"] == 2 and g1["duzeltme_orani"] == 1.0, g1)
g2 = [h for h in ko if h["olay"] == "surec_analizi"][0]
chk("süreç analizi satırı + mutabakat hariç", g2["analiz"] == 1 and g2["duzeltme_orani"] == 1.0 and all(h["olay"] != "mutabakat" for h in ko))
chk("istatistik() kalite döner", "kalite" in T.istatistik(gun=30))

# ── 2026-10-20 denetimi: kalite sayımı (yalnız durum=ok + analiz/fe-be-ayir), kimlik hariç, TZ-farkında ts, taze yerel birleştirme ──
ko2 = T.kalite_ozeti([
    {"ts": "2026-10-13T10:00:00", "olay": "gorev_analiz", "durum": "ok", "baglam": {"islem": "analiz"}, "kalite": {"acik_soru": 2}},
    {"ts": "2026-10-13T10:00:00", "olay": "gorev_analiz", "durum": "hata", "baglam": {"islem": "analiz"}, "kalite": {"acik_soru": 9}},
    {"ts": "2026-10-13T10:00:00", "olay": "gorev_analiz", "durum": "ok", "baglam": {"islem": "formatla"}},
    {"ts": "2026-10-13T10:00:00", "olay": "gorev_analiz", "durum": "ok", "baglam": {"islem": "kabul-kontrol"}},
    {"ts": "2026-10-13T10:00:00", "olay": "gorev_analiz", "durum": "ok", "baglam": {"islem": "bff-kesif"}},
    {"ts": "2026-10-13T10:00:00", "olay": "gorev_analiz", "durum": "ok", "baglam": {"islem": "akis-kapat"}},
    {"ts": "2026-10-13T10:00:00", "olay": "gorev_analiz", "durum": "hata", "baglam": {"islem": "duzelt"}},
])["haftalar"]
chk("kalite_ozeti: hata + formatla/kabul/bff/akis modları analiz SAYILMAZ (1 analiz, ort 2.0, düzeltme 0)",
    len(ko2) == 1 and ko2[0]["analiz"] == 1 and ko2[0]["ort_acik_soru"] == 2.0 and ko2[0]["duzeltme"] == 0, ko2)

chk("_ts_parse: 'Z' → farkında + yerele çevrilmiş; naif → yerel; ofsetli korunur; bozuk → None",
    T._ts_parse("2026-10-20T07:00:00Z").tzinfo is not None and T._ts_parse("2026-10-20T07:00:00.000Z") is not None
    and T._ts_parse("2026-10-20T10:00:00").tzinfo is not None and T._ts_parse("2026-10-20T10:00:00+03:00").utcoffset().total_seconds() == 3 * 3600
    and T._ts_parse("yok") is None and T._ts_parse("") is None)
chk("_ts_parse: UTC 'Z' ile ofsetli aynı anı eşit sayar", T._ts_parse("2026-10-20T07:00:00Z") == T._ts_parse("2026-10-20T10:00:00+03:00"))
chk("olay_yaz ts ofsetli yerel ISO (…+HH:MM / Z)", ham[-1]["ts"][-6] in "+-" or ham[-1]["ts"].endswith("Z"), ham[-1]["ts"])
os.environ["KOTA_OLCUM_BASLANGIC"] = "2026-10-19T18:00:00+03:00"
kk = T.kota_karsilastirma([{"ts": "2026-10-19T15:30:00Z", "olay": "x", "token": {"girdi": 1}},    # = 18:30+03 → sonra (dize kıyası 'once' derdi)
                           {"ts": "2026-10-19T14:30:00Z", "olay": "x", "token": {"girdi": 1}}])["olaylar"]["x"]   # = 17:30+03 → once
chk("kota_karsilastirma eşik kıyası TZ-farkında (UTC 'Z' damga ofsetli eşikle doğru kovada)", kk["sonra"]["n"] == 1 and kk["once"]["n"] == 1, kk)
os.environ.pop("KOTA_OLCUM_BASLANGIC", None)

# Taze yerel birleştirme: remote varken bu makinenin remote'taki en yeni ts'inden SONRAKİ yerel olaylar eklenir, tekrarlar düşer
import socket  # noqa: E402
tmp2 = Path(tempfile.mkdtemp())
T.USAGE_DIR, T.EVENTS_DOSYA, T.UZAK_DOSYA = tmp2, tmp2 / "events.jsonl", tmp2 / "remote.jsonl"
mk = socket.gethostname()
T.UZAK_DOSYA.write_text("\n".join(json.dumps(o) for o in [
    {"ts": "2026-10-01T07:00:00Z", "analist": "A", "olay": "surec_analizi", "makine": mk},
    {"ts": "2026-10-02T07:00:00Z", "analist": "A", "olay": "gorev_analiz", "makine": mk},
    {"ts": "2026-10-05T07:00:00Z", "analist": "B", "olay": "gorev_analiz", "makine": "baska-makine"},
    {"ts": "2026-10-03T10:00:00", "analist": "A", "olay": "kimlik", "makine": mk},
]) + "\n", encoding="utf-8")
T.EVENTS_DOSYA.write_text("\n".join(json.dumps(o) for o in [
    {"ts": "2026-10-01T10:00:00+03:00", "analist": "A", "olay": "surec_analizi", "makine": mk},   # == remote[0] (aynı an) → eski, girmez
    {"ts": "2026-10-02T07:00:00Z", "analist": "A", "olay": "gorev_analiz", "makine": mk},         # remote ile birebir aynı → dedup
    {"ts": "2026-10-04T09:00:00+03:00", "analist": "A", "olay": "teknik_analiz", "makine": mk},   # en yeni remote'tan SONRA → eklenir
    {"ts": "2026-10-06T09:00:00+03:00", "analist": "Z", "olay": "teknik_analiz", "makine": "yabanci"},  # başka makine → eklenmez
]) + "\n", encoding="utf-8")
ol = T.olaylari_oku()
chk("olaylari_oku: remote 4 + yalnız 1 taze yerel (teknik_analiz) = 5; tekrar/eski/yabancı yok",
    len(ol) == 5 and sum(1 for o in ol if o["olay"] == "teknik_analiz") == 1 and all(o.get("analist") != "Z" for o in ol), [(o["ts"], o["olay"]) for o in ol])
dd = T.donem_detay("2026-10-01", "2026-10-10")
chk("donem_detay: kimlik olayı HARİÇ (4 olay), gün kovası yerel saatle", dd["toplam"] == 4 and "kimlik" not in dd["tip_toplam"], dd)
chk("istatistik: kimlik hariç toplam 4", T.istatistik(gun=3650)["toplam_analiz"] == 4)

print()
if HATA:
    print(f"FAIL — {HATA} kontrol başarısız")
    sys.exit(1)
print("TELEMETRİ ÖLÇÜM TESTLERİ GEÇTİ")
