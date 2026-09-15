"""
Revizyon belkemiği + bölüm-hedefli düzenleme deterministik testleri (AI enjekte, kota YOK).
Çalıştır:  venv/bin/python tests/test_revizyon.py
"""

import sys
import importlib
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

tmp = Path(tempfile.mkdtemp())
import skills.base as base                         # noqa: E402
base.OUTPUT_DIR = tmp
import skills.revizyon as r                        # noqa: E402
importlib.reload(r)
r.OUTPUT_DIR = tmp
r.REVIZYON_DIR = tmp / "revizyon"
import skills.revizyon_ai as ra                    # noqa: E402
importlib.reload(ra)
ra.OUTPUT_DIR = tmp
ra.revizyon = r

ok = 0


def esit(a, b, ad):
    global ok
    assert a == b, f"FAIL {ad}: {a!r} != {b!r}"
    ok += 1
    print(f"  ✓ {ad}")


def dogru(kosul, ad):
    global ok
    assert kosul, f"FAIL {ad}"
    ok += 1
    print(f"  ✓ {ad}")


H = "surec-analizi.md"
o = r.baslat(H, "# Rapor\nSatır A\nSatır B\n", "İlk üretim")
esit(o["aktif_versiyon"], "v1", "baslat v1")
esit(r.baslat(H, "FARKLI")["versiyonlar"][0]["hash"], o["versiyonlar"][0]["hash"], "baslat idempotent")

rev = r.revizyon_oner(H, "# Rapor\nSatır A DÜZELTİLDİ\nSatır B\n", tip="bolum", istek="a", ozet="o")
esit(rev["onay_durumu"], "beklemede", "öneri beklemede")
esit(r.oturum_yukle(H)["aktif_versiyon"], "v1", "öneri aktifi değiştirmez")
dogru("DÜZELTİLDİ" in r.diff(H, "v1", "v2"), "diff")

r.onayla(H, rev["id"])
esit(r.oturum_yukle(H)["aktif_versiyon"], "v2", "onay → v2")
try:
    r.onayla(H, rev["id"])
    raise SystemExit("çift onay geçmemeliydi")
except ValueError:
    dogru(True, "çift onay engellendi")

rev2 = r.revizyon_oner(H, "X\n", tip="sohbet")
r.reddet(H, rev2["id"])
esit(r.oturum_yukle(H)["aktif_versiyon"], "v2", "ret aktifi korur")

r.geri_al(H, "v1")
dogru("DÜZELTİLDİ" not in r.onayli_icerik(H), "geri-al")
esit(r.ozet(H)["bekleyen"], None, "bekleyen yok")

MD = ("<!-- m -->\n\n## Amaç\nx\n\n## Süreç Adımları\n### PA-001: Giriş\nKullanıcı giriş yapar.\n"
      "### PA-002: Onay\nY.\n\n## Açık Sorular\n| Q-001 |\n")
sa = ra.bolum_bul(MD, "Süreç Adımları")
dogru("PA-001" in sa["icerik"] and "Açık Sorular" not in sa["icerik"], "üst bölüm alt PA'ları kapsar")
pa1 = ra.bolum_bul(MD, "PA-001")
dogru("PA-002" not in pa1["icerik"], "PA-001 tekil")
esit(ra.bolum_bul(MD, "YOK"), None, "bulunamayan None")

# Bulgu 1b — gövde-içi ID fallback: süreç analizinde ID'ler başlıkta DEĞİL, gövdede
# satır-içi (`**PA-003:** …`). Başlık eşleşmesi başarısızsa ID'yi içeren en derin bölüm dönmeli.
MD2 = ("# Rapor\n\n## 2. İş Gereksinimleri\n### 2.1. Alan\n**BR-001:** 4 kolon.\n**BR-006:** FE giriş.\n"
       "### 2.2. Endpoint\n**BR-005:** Bulk update.\n\n## 7. Frontend\n**PA-003:** Manuel giriş · Bağlı: BR-006\n")
b = ra.bolum_bul(MD2, "PA-003")
dogru(b is not None and b["baslik"].startswith("7."), "gövde-içi PA-003 → 7. Frontend bölümü")
b = ra.bolum_bul(MD2, "BR-005")
dogru(b is not None and b["baslik"].startswith("2.2"), "gövde-içi BR-005 → 2.2 bölümü")
b = ra.bolum_bul(MD2, "BR-001/BR-006")
dogru(b is not None and b["baslik"].startswith("2.1"), "bileşik ID → en derin (2.1) bölüm")
esit(ra.bolum_bul(MD2, "ZZ-999"), None, "gövdede olmayan ID → None (tam-regen)")
esit(ra.bolum_bul(MD2, "İş Kuralları"), None, "ID'siz başlık metni eşleşmezse None (fallback devre dışı)")
esit(ra._anahtar_idleri("BR-001/BR-006"), ["BR-001", "BR-006"], "bileşik anahtardan ID çıkarımı")
esit(ra._anahtar_idleri("MOCKUP/EK-001"), ["EK-001"], "harf-only segment ID sayılmaz")

(tmp / "t.md").write_text(MD, encoding="utf-8")
rv = ra.bolum_duzenle("t.md", "PA-001", "2fa ekle",
                      _ai_fn=lambda t, b: "### PA-001: Giriş\nE-posta + 2FA (DÜZENLENDİ).\n")
v2 = r.versiyon_icerik("t.md", "v2")
dogru("DÜZENLENDİ" in v2 and "PA-002" in v2 and v2.count("### PA-001") == 1, "splice komşuları korur")
esit(rv["onay_durumu"], "beklemede", "bölüm düzenleme beklemede")

# ── BAYAT OTURUM KORUMASI (#1 veri kaybı önleme) ──────────────────────────────
# Disk pipeline/rerun/upload ile yeniden üretildiğinde, hedefli düzeltme oturumdaki ESKİ
# içeriği değil DİSKTEKİ güncel içeriği baz almalı; yoksa güncel analiz eski içerikle ezilir.
H3 = "teknik-analiz.md"
(tmp / H3).write_text("### PA-001: Giriş\nESKI_A içerik.\n", encoding="utf-8")
r.baslat(H3, (tmp / H3).read_text(encoding="utf-8"), "İlk (A)")
(tmp / H3).write_text("### PA-001: Giriş\nYENI_B içerik tamamen farklı.\n", encoding="utf-8")  # disk B'ye üretildi
rv3 = ra.bolum_duzenle(H3, "PA-001", "kısalt",
                       _ai_fn=lambda t, b: "### PA-001: Giriş\nDÜZENLENDİ_B.\n")
aktif = r.onayli_icerik(H3)
dogru("YENI_B" in aktif and "ESKI_A" not in aktif, "#1 oturum diske (B) yeniden bazlandı — eski A ezmez")
esit(rv3["onay_durumu"], "beklemede", "#1 yeniden bazlama sonrası öneri beklemede")
dogru("ESKI_A" not in r.versiyon_icerik(H3, "v2"), "#1 öneri eski A içeriği taşımaz")

print(f"\nREVİZYON TESTLERİ GEÇTİ ({ok} assert)")
