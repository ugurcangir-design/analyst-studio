"""İnteraktif Analiz — bayat çıktı gösterilmez + ön-söz/iç-konuşma kırpma (offline, 0 token).
Hata: 12 Eylül'de üretilmiş surec-analizi.md, 15 Ekim'deki yeni sohbetin ürünü gibi gösterildi; dosyada
modelin İngilizce iç konuşması ("I have sufficient focused observation… Now I'll produce…") kalmıştı."""
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("BILDIRIM", "false")

from skills import sohbet_analiz as SA  # noqa: E402
from skills.base import _onsoz_kirp  # noqa: E402

_hata = 0


def chk(ad, kosul, ek=""):
    global _hata
    if not kosul:
        _hata += 1
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if ek and not kosul else ""))


print("1) bayat çıktı oturuma ait sayılmaz")
tmp = Path(tempfile.mkdtemp())
SA.OUTPUT_DIR = tmp
dosya = tmp / "surec-analizi.md"
dosya.write_text("# eski", encoding="utf-8")
eski = time.time() - 3600
os.utime(dosya, (eski, eski))
oturum = {"created": time.time() - 60, "mesajlar": [{"rol": "analist", "metin": "x", "ts": time.time() - 30}]}
chk("1 saat önceki dosya, 30 sn önce başlayan sohbete ait DEĞİL", SA.surec_var_mi(oturum) is False)
simdi = time.time() + 5
os.utime(dosya, (simdi, simdi))
chk("sohbetten sonra üretilen dosya ait", SA.surec_var_mi(oturum) is True)
chk("mesajsız oturumda created eşik", SA.surec_var_mi({"created": time.time() + 100, "mesajlar": []}) is False)
chk("dosya yoksa False", SA.teknik_var_mi(oturum) is False)

print("2) ön-söz / iç konuşma kırpma")
meta = "<!--\nKULLANILAN REFERANSLAR:\n- a.pdf\n-->\n\n"
ic = "I have sufficient focused observation. Let me verify the sort isn't needed. Now I'll produce the process analysis report.\n\n"
govde = "---\n\n| Alan | Değer |\n|---|---|\n| Epic | |\n\n# BAŞLIK\n\n## AMAÇ\nmetin\n"
r = _onsoz_kirp(ic + govde)
chk("baştaki iç konuşma kırpılır, gövde korunur", r == govde.lstrip("\n"), r[:80])
r = _onsoz_kirp(meta + ic + govde)
chk("meta yorumdan SONRAKİ iç konuşma da kırpılır", "I have sufficient" not in r and "KULLANILAN" in r and "| Alan |" in r, r[:120])
g = "# Başlık\n\nI think this field is optional and the team agreed.\n\n## Alt\n"
chk("gövde içindeki İngilizce paragraf DOKUNULMAZ", _onsoz_kirp(g) == g)
j = '{"a": 1}\n\n# R\n'
chk("JSON gövdesi kırpılmaz", _onsoz_kirp(j) == j)
tr = "Bu rapor süreç analizidir.\n\n# R\n"
chk("Türkçe düz giriş cümlesi (ön-söz) klasik kat ile kırpılır", _onsoz_kirp(tr) == "# R\n")

print()
if _hata:
    print(f"SOHBET TAZELİK TESTLERİ BAŞARISIZ ({_hata} hata)")
    sys.exit(1)
print("SOHBET TAZELİK TESTLERİ GEÇTİ")
