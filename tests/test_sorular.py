"""Soru Defteri — oturum-aidiyeti / bayat cevap taşınmaması (offline, 0 token).

Regresyon: analist YENİ bir süreç analizi çalıştırdığında, önceki oturumun aynı
konumsal id'li (Q-001…) CEVAPLANMIŞ soruları yeni sorulara TAŞINMAMALI — yoksa yeni
açık sorular yanlışlıkla 'tümü cevaplandı' görünür (Emin senaryosu).

Çalıştır:  venv/bin/python tests/test_sorular.py
"""

import sys
import tempfile
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

import skills.sorular as S  # noqa: E402

basari = 0


def kontrol(ad: str, kosul: bool) -> None:
    global basari
    if not kosul:
        raise SystemExit(f"FAIL {ad}")
    basari += 1
    print(f"  ✓ {ad}")


def _izole_output():
    tmp = Path(tempfile.mkdtemp())
    S.OUTPUT_DIR = tmp
    S.SORULAR_DOSYA = tmp / "sorular.json"
    return tmp


def _yaz_surec(tmp: Path, qs):
    L = ["## 12. Açık Sorular", "",
         "| ID | Konu | Tip | Önem | Bağlı | Mevcut | Beklenen Yanıt |",
         "|----|------|-----|------|-------|--------|----------------|"]
    for qid, konu in qs:
        L.append(f"| {qid} | {konu} | İş | Yüksek | PA-1 | ? | {konu} yanıtı |")
    (tmp / "surec-analizi.md").write_text("\n".join(L), encoding="utf-8")


# ── 1) Çapraz oturum: bayat 'cevaplandı' YENİ sorulara taşınmaz ────────────────
tmp = _izole_output()
onceki = time.time()
_yaz_surec(tmp, [("Q-001", "Eski soru A"), ("Q-002", "Eski soru B")])
S.parse_ve_birlestir(taze_esik=onceki)
S.soru_guncelle("Q-001", "surec-analizi.md", "cevaplandi", cevap="Eski cevap A")
S.soru_guncelle("Q-002", "surec-analizi.md", "cevaplandi", cevap="Eski cevap B")

time.sleep(1.1)                              # yeni oturum, farklı saniye
yeni = time.time()
time.sleep(0.05)
_yaz_surec(tmp, [("Q-001", "YENİ soru X"), ("Q-002", "YENİ soru Y"),
                 ("Q-003", "YENİ soru Z"), ("Q-004", "YENİ soru W")])
d = S.parse_ve_birlestir(taze_esik=yeni)
ist = d["istatistik"]
durum = {s["id"]: s["durum"] for s in d["sorular"]}
baslik = {s["id"]: s.get("baslik") for s in d["sorular"]}

kontrol("yeni oturum → 4 açık soru", ist["acik"] == 4)
kontrol("yeni oturum → 0 cevaplandı (bayat cevap taşınmadı)", ist["cevaplandi"] == 0)
kontrol("Q-001 durum='acik'", durum.get("Q-001") == "acik")
kontrol("Q-001 içeriği yenilendi", baslik.get("Q-001") == "YENİ soru X")

# ── 2) Aynı oturum: cevap POLLING (tekrar parse) sonrası KORUNUR ───────────────
tmp = _izole_output()
oturum = time.time()
_yaz_surec(tmp, [("Q-001", "Soru A"), ("Q-002", "Soru B")])
S.parse_ve_birlestir(taze_esik=oturum)
S.soru_guncelle("Q-001", "surec-analizi.md", "cevaplandi", cevap="Cevap A")
d2 = S.parse_ve_birlestir(taze_esik=oturum)   # UI polling'i simüle et
durum2 = {s["id"]: s["durum"] for s in d2["sorular"]}
kontrol("aynı oturum → cevap korunur", durum2.get("Q-001") == "cevaplandi")
kontrol("aynı oturum → cevaplanmamış açık kalır", durum2.get("Q-002") == "acik")

# ── 3) taze_esik=None → geriye-uyumlu (hep koru) ───────────────────────────────
tmp = _izole_output()
_yaz_surec(tmp, [("Q-001", "Soru A")])
S.parse_ve_birlestir(taze_esik=None)
S.soru_guncelle("Q-001", "surec-analizi.md", "cevaplandi", cevap="C")
d3 = S.parse_ve_birlestir(taze_esik=None)
kontrol("taze_esik=None → cevap korunur (geriye-uyumlu)",
        {s["id"]: s["durum"] for s in d3["sorular"]}.get("Q-001") == "cevaplandi")

# ── 4) _iso_epoch sağlamlığı ───────────────────────────────────────────────────
kontrol("_iso_epoch geçersiz → None", S._iso_epoch("çöp") is None)
kontrol("_iso_epoch None → None", S._iso_epoch(None) is None)
kontrol("_iso_epoch geçerli → float", isinstance(S._iso_epoch("2026-09-15T10:30:00"), float))

print(f"\nSORULAR TESTLERİ GEÇTİ ({basari} kontrol)")
