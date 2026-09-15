"""Soru cevabı → HEDEFLİ düzeltme yönlendirmesi (offline, 0 token, AI MOCK).

Regresyon: süreç analizi (surec-analizi.md) açık sorularının cevabı, TÜM analizi
yeniden yazmak yerine yalnız `bagli_id`'nin (PA-XXX/BR-XXX) işaret ettiği bölümü
düzeltmeli (teknik analizle aynı hedefli davranış). Bölüm bulunamazsa yine tam
yeniden üretime düşer.

Çalıştır:  venv/bin/python tests/test_soru_hedefli.py
"""

import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

import app  # noqa: E402
from skills import revizyon, revizyon_ai  # noqa: E402
from skills import base as B  # noqa: E402

basari = 0


def kontrol(ad: str, kosul: bool) -> None:
    global basari
    if not kosul:
        raise SystemExit(f"FAIL {ad}")
    basari += 1
    print(f"  ✓ {ad}")


# ── Harita: her analiz dosyası hedefli düzeltilebilir olmalı ────────────────────
kontrol("surec-analizi.md kendine hedefli", app._SORU_HEDEF_ANALIZ.get("surec-analizi.md") == "surec-analizi.md")
kontrol("acik-sorular.md → teknik-analiz.md", app._SORU_HEDEF_ANALIZ.get("acik-sorular.md") == "teknik-analiz.md")
kontrol("brd-sorular.md → brd-analizi.md", app._SORU_HEDEF_ANALIZ.get("brd-sorular.md") == "brd-analizi.md")

# ── Ortam: geçici OUTPUT_DIR + surec-analizi.md ────────────────────────────────
tmp = Path(tempfile.mkdtemp())
app.OUTPUT_DIR = tmp
(tmp / "surec-analizi.md").write_text("## Süreç\n\n**PA-003:** Sipariş onay adımı ...\n", encoding="utf-8")

_REVIZE = "## Süreç\n\n**PA-003:** Onay 2 aşamalı — CEVAP UYGULANDI\n"
cagri = {"bolum_duzenle": [], "yeniden_calistir": []}
revizyon_ai.bolum_bul = lambda md, anahtar: {"baslik": "PA-003"} if "PA-003" in (anahtar or "") else None
revizyon_ai.bolum_duzenle = lambda hedef, bid, notu: (cagri["bolum_duzenle"].append((hedef, bid)), {"id": "r1"})[1]
revizyon.onayla = lambda hedef, rid: None
revizyon.onayli_icerik = lambda hedef: _REVIZE      # onaylı (revize) içerik
B.yeniden_calistir = lambda kaynak, notu: cagri["yeniden_calistir"].append(kaynak)

# ── 1) bagli_id bölümü BULUNUR → yalnız o bölüm düzeltilir (tam üretim YOK) ─────
s_bulunur = [{"id": "Q-001", "kaynak_dosya": "surec-analizi.md", "bagli_id": "PA-003",
              "durum": "cevaplandi", "cevap": "Onay 2 aşamalı"}]
ozet = app._sorulari_hedefli_uygula("surec-analizi.md", s_bulunur)
kontrol("süreç sorusu → hedefli (1)", ozet["hedefli"] == 1 and ozet["tam"] == 0)
kontrol("yalnız PA-003 bölümü düzenlendi", cagri["bolum_duzenle"] == [("surec-analizi.md", "PA-003")])
kontrol("tam yeniden üretim ÇAĞRILMADI", cagri["yeniden_calistir"] == [])
# KRİTİK: onaylı revize içerik DİSKE yazıldı mı? (yoksa teknik analiz bayat okur)
kontrol("hedefli cevap surec-analizi.md'ye DİSKE yazıldı",
        (tmp / "surec-analizi.md").read_text(encoding="utf-8") == _REVIZE)

# ── 2) bagli_id bölümü BULUNAMAZ → tam yeniden üretime düşer (son çare) ─────────
cagri["bolum_duzenle"].clear()
cagri["yeniden_calistir"].clear()
s_bulunmaz = [{"id": "Q-002", "kaynak_dosya": "surec-analizi.md", "bagli_id": "YOK-999",
               "durum": "cevaplandi", "cevap": "x"}]
ozet2 = app._sorulari_hedefli_uygula("surec-analizi.md", s_bulunmaz)
kontrol("bölüm bulunamazsa tam üretim (1)", ozet2["hedefli"] == 0 and ozet2["tam"] == 1)
kontrol("tam yeniden üretim surec-analizi.md için çağrıldı", cagri["yeniden_calistir"] == ["surec-analizi.md"])
kontrol("bölüm düzenleme yapılmadı", cagri["bolum_duzenle"] == [])

# ── 3) FALLBACK HEDEF dosyayı üretir (kaynak≠hedef): acik-sorular.md → teknik-analiz.md ──
# Bölüm bulunamayınca cevap ANALİZ dosyasına (hedef) işlenmeli, SORU dosyasına (kaynak) değil.
cagri["bolum_duzenle"].clear()
cagri["yeniden_calistir"].clear()
(tmp / "acik-sorular.md").write_text("### Q-T-9\n- Soru: x\n", encoding="utf-8")
(tmp / "teknik-analiz.md").write_text("## Teknik Analiz\n", encoding="utf-8")
s_teknik = [{"id": "Q-T-9", "kaynak_dosya": "acik-sorular.md", "bagli_id": "YOK-1",
             "durum": "cevaplandi", "cevap": "x"}]
ozet3 = app._sorulari_hedefli_uygula("acik-sorular.md", s_teknik)
kontrol("acik-sorular fallback → HEDEF teknik-analiz.md üretilir (kaynak değil)",
        cagri["yeniden_calistir"] == ["teknik-analiz.md"])

print(f"\nSORU HEDEFLİ TESTLERİ GEÇTİ ({basari} kontrol)")
