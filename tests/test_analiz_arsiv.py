"""Analiz İnceleme arşivi (owner 2026-11-06, 5/5): kaydet/liste/oku/not, soru özeti gömme-çözme, yakalama noktaları
(workflow geçişi, Task analizi, sohbet üretimi), uçlar (usage-gate). Offline / 0 token; sink'e gitmez (test modu)."""
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("TELEMETRI_SINK", "off")

from skills import analiz_arsiv as AR  # noqa: E402

tmp = Path(tempfile.mkdtemp())
AR.ARSIV_DIR = tmp / "arsiv"
AR.UZAK_DIR = AR.ARSIV_DIR / "uzak"
AR.NOT_DOSYA = AR.ARSIV_DIR / "notlar.json"
hatalar = []


def chk(ad, kosul, ek=""):
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f" — {ek}" if ek and not kosul else ""))
    if not kosul:
        hatalar.append(ad)


SORU = """### Q-T-001: Katman
- Tür: Teknik Araştırma
- Soru: sıralama hangi serviste?

### Q-T-002: Ürün
- Tür: İş Kararı
- Zorunlu: Evet
- Soru: metin değer gelirse ne olmalı?
"""
print("1) kaydet / liste / oku / not")
k = AR.kaydet("teknik", "MBSTRADE-1502.txt", "## 1. Amaç\n" + "x" * 300 + "\nşifre: gizli123", SORU, jira_key="MBSTRADE-1502", proje="MBSTRADE")
chk("kayıt yerel dosyaya yazıldı, tip inceleme:teknik, ozet gömülü", k and (AR.ARSIV_DIR / f"{k['id']}.json").exists()
    and k["tip"] == "inceleme:teknik" and "⟨inc" in k["ozet"] and "Açık Sorular (arşiv)" in k["icerik"])
L = AR.liste()
chk("liste: soru sayıları çözüldü (1 iş, 1 teknik, 1 zorunlu), kaynak", L and L[0]["sorular"] == {"is": 1, "teknik": 1, "dogru": 0, "zorunlu": 1, "toplam": 2}
    and L[0]["kaynak"] == "MBSTRADE-1502.txt" and L[0]["tip"] == "teknik", L)
chk("kısa içerik kaydedilmez", AR.kaydet("surec", "x", "kısa") is None)
chk("not yaz/oku + geçersiz id reddi", AR.not_yaz(k["id"], "24 soru çok fazla") and AR.oku(k["id"])["not"] == "24 soru çok fazla"
    and not AR.not_yaz("../x", "y") and AR.oku("../x") is None)
chk("not silme", AR.not_yaz(k["id"], "") and AR.oku(k["id"])["not"] == "")
chk("ozet gömme/çözme round-trip", AR._ozet_coz(AR._ozet_gom("K", {"is": 2, "teknik": 3, "dogru": 1, "zorunlu": 1, "toplam": 6}))
    == ("K", {"is": 2, "teknik": 3, "dogru": 1, "zorunlu": 1, "toplam": 6}))
chk("test modunda uzaktan çekme ağ açmaz", AR.cek()[0] is False)

print("2) app yakalama noktaları + uçlar")
sys.argv = ["test_analiz_arsiv"]
import app as A  # noqa: E402
from skills import telemetri as T  # noqa: E402
T.USAGE_DIR = tmp / "usage"
T.EVENTS_DOSYA = T.USAGE_DIR / "events.jsonl"
T._sink_gonder = lambda k: None
import skills.gorev_deposu as GD  # noqa: E402
GD.kaydet = lambda *a, **k: None
A._ornek_yakala_md = lambda *a, **k: None
n0 = len(AR.liste())
A._gorev_egitim_topla("EKRAN-1", "Sports", "", "fe-be-ayir", {"fe_be": {"be": {"markdown": "## 1. Amaç\n" + "b" * 300, "acik_sorular": SORU},
                                                                "fe": {"markdown": "## 1. Amaç\n" + "f" * 300, "acik_sorular": ""}}})
chk("Task FE+BE (sentetik EKRAN- dahil) → 2 arşiv kaydı", len(AR.liste()) == n0 + 2 and any(x["jira_key"] == "EKRAN-1::FE" for x in AR.liste()))
A._gorev_egitim_topla("MBS-1", "s", "", "formatla", {"markdown": "x" * 500})
chk("formatla arşivlenmez", len(AR.liste()) == n0 + 2)
out = tmp / "output"
out.mkdir()
(out / "surec-analizi.md").write_text("# Süreç\n" + "s" * 400, encoding="utf-8")
A.OUTPUT_DIR = out
A.INPUT_DIR = tmp / "input"
A.INPUT_DIR.mkdir()
(A.INPUT_DIR / "dok.txt").write_text("d")
import workflow as WF  # noqa: E402
WF.ozet = lambda: {"onay_bekleniyor": True}
A._analiz_arsiv_kontrol()
A._analiz_arsiv_kontrol()
chk("süreç onay geçişinde TEK kez arşiv (dedup)", len(AR.liste()) == n0 + 3 and any(x["tip"] == "surec" and x["kaynak"] == "dok.txt" for x in AR.liste()))
WF.ozet = lambda: {}
A._analiz_arsiv_kontrol()
time.sleep(1.1)
(out / "surec-analizi.md").write_text("# Süreç 2\n" + "s" * 400, encoding="utf-8")
WF.ozet = lambda: {"onay_bekleniyor": True}
A._analiz_arsiv_kontrol()
chk("yeni koşu (mtime değişti) → yeni arşiv", len(AR.liste()) == n0 + 4)
A._usage_yetkili_mi = lambda: True
c = A.app.test_client()
H = {"Origin": "http://localhost"}
r = c.get("/api/analiz-arsiv").get_json()
chk("GET liste", r.get("ok") and len(r["kayitlar"]) == n0 + 4)
oid = r["kayitlar"][0]["id"]
chk("GET kayıt + POST not", c.get(f"/api/analiz-arsiv/{oid}").get_json()["kayit"]["id"] == oid
    and c.post("/api/analiz-arsiv/not", json={"id": oid, "not": "ok"}, headers=H).get_json()["ok"]
    and c.post("/api/analiz-arsiv/not", json={"id": "x", "not": "ok"}, headers=H).status_code == 400
    and c.get("/api/analiz-arsiv/inc-0000000000000000").status_code == 404)
A._usage_yetkili_mi = lambda: False
chk("usage-gate: yetkisiz 403", c.get("/api/analiz-arsiv").status_code == 403)

print(f"\n{'ANALİZ ARŞİVİ TESTLERİ GEÇTİ' if not hatalar else 'HATA: ' + ', '.join(hatalar)}")
sys.exit(1 if hatalar else 0)
