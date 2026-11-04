"""Otomatik mockup Faz 2 — yama tabanlı üretim (offline, 0 token; AI + yakalama MOCK).

yama_uret(): AI'dan <mockup_yama> JSON alır, geçersiz op/selector eler; ilgili_bolumler(): analizin UI bölümleri;
selector_on_kontrol(): baseline'da olmayan ipuçlarını işaretler; mockup_olustur(): baseline + gömülü yama + JS + redline;
uret(): yakala→yama→kaydet, yakalama düşerse fallback=True.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skills import mockup_yama as MY  # noqa: E402

HATA = 0


def chk(ad, kosul, ek=""):
    global HATA
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if (ek and not kosul) else ""))
    if not kosul:
        HATA += 1


BASE = ("<html><head><style>.x{}</style></head><body><nav class=\"MuiList\">menu</nav><main><table><tbody>"
        "<tr><td><a href=\"/basic-data/sports?open=1\">Hentbol</a></td><td><button aria-label=\"Assign\" class=\"MuiIconButton-root\">A</button>"
        "<button aria-label=\"Unmap\">U</button></td></tr><tr><td>—</td><td><button aria-label=\"Assign\">A</button></td></tr>"
        "</tbody></table></main></body></html>")
ANALIZ = """## 1. Amaç
Eşlenmiş satırda Assign pasif.
## 3. Teknik Gereksinimler
### 3.1 Liste
uç bilgisi
## 4. Veri
db
## 6. Kabul Kriterleri
* **AC-1:** eşlenmiş satırda Assign disabled.
"""
YANIT = """Analiz ettim.
<mockup_yama>{"ozet":"Eşlenmiş satırda Assign pasif","yamalar":[
 {"op":"disable","selector":"tr:has(a[href*=\\"open=\\"]) button[aria-label=\\"Assign\\"]","ac":"AC-1","not":"eşlenmiş satır"},
 {"op":"attr","selector":"tr:has(a[href*=\\"open=\\"]) button[aria-label=\\"Assign\\"]","attr":{"title":"This record is already mapped."},"not":"tooltip"},
 {"op":"add","selector":"nav.MuiList","konum":"append","html":"<li class=\\"MuiListItem\\">Yeni</li>","not":"menü"},
 {"op":"add","selector":"nav","html":""},
 {"op":"fly","selector":"x"},
 {"op":"text","selector":"td"},
 {"op":"replace","selector":".yok-boyle-sinif","html":"<b>x</b>","not":"şüpheli"}
]}</mockup_yama>"""

# ── 1 ilgili bölümler ──
b = MY.ilgili_bolumler(ANALIZ)
chk("UI bölümleri seçildi, ilgisiz (Veri) atıldı", "Amaç" in b and "Kabul" in b and "Teknik" in b and "## 4. Veri" not in b)
chk("başlıksız metin olduğu gibi (kırpılı)", MY.ilgili_bolumler("x" * 20000, azami_kc=100).startswith("x" * 100))

# ── 2 yama ayıkla / yama_uret ──
y = MY.yama_uret(ANALIZ, BASE, baslik="T", _ai=lambda s, m: YANIT)
chk("ok + geçersizler elendi (boş html add, bilinmeyen op, text'siz text)", y["ok"] and len(y["yamalar"]) == 4, str(len(y["yamalar"])))
chk("add varsayılan konum after / verilen konum korunur", y["yamalar"][2]["konum"] == "append")
chk("ozet alındı", y["ozet"].startswith("Eşlenmiş"))
chk("JSON bozuk → ok False", MY.yama_uret(ANALIZ, BASE, _ai=lambda s, m: "<mockup_yama>{bozuk</mockup_yama>")["ok"] is False)
chk("AI hata → ok False + neden", "başarısız" in MY.yama_uret(ANALIZ, BASE, _ai=lambda s, m: (_ for _ in ()).throw(RuntimeError("x")))["neden"])
# prompt içeriği: sadeleştirilmiş DOM + analiz bölümleri gider, yeni ekran modunda içerik selector'ü sistemde
yakalanan = {}


def _ai_yakala(s, m):
    yakalanan["sistem"] = s
    yakalanan["kullanici"] = "\n".join(p["text"] for p in m[0]["content"])
    return YANIT


MY.yama_uret(ANALIZ, BASE, _ai=_ai_yakala)
chk("prompt: analiz bölümleri + sadeleştirilmiş DOM (style yok)", "AC-1" in yakalanan["kullanici"] and "MuiIconButton-root" in yakalanan["kullanici"] and ".x{}" not in yakalanan["kullanici"])
chk("normal mod sistem = yama kuralları", "YENİDEN ÇİZMEZSİN" in yakalanan["sistem"])
MY.yama_uret(ANALIZ, BASE, yeni_ekran=True, _ai=_ai_yakala)
chk("yeni ekran modu: kabuk + içerik selector main", "KABUK" in yakalanan["sistem"] and "`main`" in yakalanan["sistem"])

# ── 3 selector ön-kontrol ──
onk = MY.selector_on_kontrol(y["yamalar"], BASE)
chk("gerçek ipuçları şüphesiz, .yok-boyle-sinif şüpheli", not onk[0]["suphe"] and not onk[2]["suphe"] and onk[3]["suphe"] and onk[3]["eksik"] == ["yok-boyle-sinif"])

# ── 4 mockup_olustur ──
html = MY.mockup_olustur(BASE, y["yamalar"], y["ozet"], "T", "https://x.test/a")
chk("baseline korunur + yama JSON + uygulayıcı + redline css gömülü",
    "MuiIconButton-root" in html and "__MOCKUP_YAMA=" in html and "mockup-uygula" in html and "data-mockup" in html and html.index("mockup-yama") < html.index("</body>"))
veri = json.loads(html.split("__MOCKUP_YAMA=", 1)[1].split(";</script>", 1)[0].replace("<\\/", "</"))
chk("gömülü JSON geri okunur, 4 yama", len(veri["yamalar"]) == 4 and veri["yamalar"][0]["op"] == "disable")
chk("</script> kaçışı (html içinde script kapanışı JSON'u bozmaz)",
    "</scr" not in MY.mockup_olustur("<body></body>", [{"op": "add", "selector": "b", "html": "<script></script>"}]).split("__MOCKUP_YAMA=", 1)[1].split(";</script>", 1)[0])
chk("body yoksa sona eklenir", MY.mockup_olustur("<div>x</div>", []).endswith("</script>\n"))

# ── 5 uret: yakala→yama→kaydet; yakalama düşerse fallback ──
tmp = Path(tempfile.mkdtemp())
MY.OUTPUT_DIR = tmp
def _kaydet(ad, icerik):
    (tmp / ad).write_text(icerik)
    return tmp / ad


MY._kaydet = _kaydet
bl = tmp / "baseline.html"
bl.write_text(BASE)
r = MY.uret(ANALIZ, "https://x.test/a", baslik="T", _ai=lambda s, m: YANIT,
            _yakala=lambda url, bekle="", yeniden=False: {"ok": True, "baseline": str(bl), "url": url, "png": "", "yeniden_kullanildi": True})
chk("uret ok: dosya + yamalar + canli-baseline + onbellek bayrağı", r["ok"] and (tmp / "gorev-mockup.html").exists() and len(r["yamalar"]) == 4 and r["tasarim_kaynagi"] == "canli-baseline" and r["yakalama_onbellek"])
chk("yama meta json yazıldı", (tmp / "gorev-mockup.yama.json").exists() and json.loads((tmp / "gorev-mockup.yama.json").read_text())["kaynak_url"] == "https://x.test/a")
chk("şüpheli selector raporlanır", len(r["eslesmeyen"]) == 1)
r = MY.uret(ANALIZ, "https://x.test/b", _ai=lambda s, m: YANIT, _yakala=lambda url, bekle="", yeniden=False: {"ok": False, "neden": "Oturum yok"})
chk("yakalama düşerse fallback=True + neden", r["ok"] is False and r["fallback"] and "Oturum" in r["neden"])
r = MY.uret(ANALIZ, "https://x.test/a", _ai=lambda s, m: "hiçbir şey", _yakala=lambda url, bekle="", yeniden=False: {"ok": True, "baseline": str(bl), "url": url})
chk("yama üretilemezse fallback=True", r["ok"] is False and r["fallback"])
chk("süreç dosya adı parametreyle", MY.uret(ANALIZ, "https://x.test/a", dosya=MY.SUREC_MOCKUP_DOSYA, _ai=lambda s, m: YANIT,
    _yakala=lambda url, bekle="", yeniden=False: {"ok": True, "baseline": str(bl), "url": url})["dosya"] == "mockup.html")

print(f"\n{'TÜM TESTLER GEÇTİ' if HATA == 0 else str(HATA) + ' HATA'}")
sys.exit(1 if HATA else 0)
