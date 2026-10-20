"""Yönetici Özeti — çift özet regresyonu (offline, 0 token).
Hata: few-shot örnekleri '📋 Yönetici Özeti' ile başladığından model kendi özetini yazıyor, kod üstüne
ikincisini ekliyordu. Beklenen: model özeti varsa maddeleri bizim özete BİRLEŞİR, gövdede ikinci özet kalmaz;
örnek havuzuna kaydedilirken özet çıkar."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("BILDIRIM", "false")

from skills.base import yonetici_ozeti_olustur, yonetici_ozetini_cikar  # noqa: E402
from skills import ornek_havuzu as OH  # noqa: E402

_hata = 0


def chk(ad, kosul, ek=""):
    global _hata
    if not kosul:
        _hata += 1
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if ek and not kosul else ""))


MODEL = ("## 📋 Yönetici Özeti\n*(Hızlı tarama için)*\n\n- **Kapsam:** Export özelliği\n- **Kritik çelişki:** CORE-535\n"
         "- **Açık sorular:** 3 — modelin yanlış sayımı\n\n---\n\n")
GOVDE = "# BAŞLIK\n\n## AMAÇ\nmetin\n\n### Açık Sorular\n\n### Q-001: a\n- Soru: x\n\n### Q-002: b\n- Soru: y\n"

print("1) birleştirme")
oz = yonetici_ozeti_olustur(MODEL + GOVDE)
gov = yonetici_ozetini_cikar(MODEL + GOVDE)
son = oz + gov
chk("tek özet", son.count("## 📋 Yönetici Özeti") == 1)
chk("model maddeleri korundu", "**Kapsam:** Export özelliği" in oz and "**Kritik çelişki:** CORE-535" in oz)
chk("açık soru sayacı deterministik (model sayımı atılır)", "**Açık sorular:** 2" in oz and "3 — modelin" not in oz, oz)
chk("kapsam sayacı modelin Kapsam maddesini tekrarlamaz", oz.count("**Kapsam:**") == 1)
chk("gövde başlıkla başlar", gov.startswith("# BAŞLIK"))

oz_k = yonetici_ozeti_olustur("### Açık Sorular\n\n### Q-T-001: a\n- Öncelik: Kritik\n- Soru: x\n\n### Q-002: b\n- Önem: Kritik\n- Soru: y\n")
chk("kritik sayımı 'Öncelik:' (teknik Q-T) ve 'Önem:' (süreç/BRD) ikisini de sayar", "**Açık sorular:** 2 (2 kritik)" in oz_k, oz_k)

print("2) model özeti yokken eski davranış")
oz2 = yonetici_ozeti_olustur(GOVDE)
chk("yalnız deterministik satırlar", "**Açık sorular:** 2" in oz2 and "Kritik çelişki" not in oz2)
chk("özetsiz gövde değişmez", yonetici_ozetini_cikar(GOVDE) == GOVDE)

print("3) çikar: TÜM özet bloklarını siler (eski çift-özetli dosya)")
cift = "## 📋 Yönetici Özeti\n- a\n\n---\n\n<!-- meta -->\n\n---\n\n" + MODEL + GOVDE
t = yonetici_ozetini_cikar(cift)
chk("ikisi de gitti, gövde kaldı", "Yönetici Özeti" not in t and "# BAŞLIK" in t and "<!-- meta -->" in t, t[:120])

print("4) few-shot örneğine özet girmez")
chk("_temizle özeti çıkarır", "Yönetici Özeti" not in OH._temizle(MODEL + GOVDE) and "# BAŞLIK" in OH._temizle(MODEL + GOVDE))

print()
if _hata:
    print(f"YÖNETİCİ ÖZETİ TESTLERİ BAŞARISIZ ({_hata} hata)")
    sys.exit(1)
print("YÖNETİCİ ÖZETİ TESTLERİ GEÇTİ")
