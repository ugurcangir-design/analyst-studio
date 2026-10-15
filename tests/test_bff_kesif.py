"""BFF Keşfi (CRUD gözlemi) — offline, 0 token (AI enjekte).

Kapsam:
  1. Anahtar/önbellek: rapor yok → None; kesfet → md+json yazılır; rapor_oku/taze_mi (7 gün); eski rapor taze değil
  2. kesfet: canlı hedef yoksa AI çağrılmaz; ekran bazlı → base URL + 'surec'; görev hedefi → 'gorev'; plan CRUD
     adımlarını ve 'kayıt kalsın / ayrı kayıtta sil' kuralını içerir; eksik rapor → ok=False ama kaydedilir
  3. otomatik_acik ayarı; rapor_blogu başlığı
  4. gorev_analiz_et bff_rapor bloğunu prompta koyar; gorev_fe_be_analiz iki çağrıya da geçirir
  5. app: bff-kesif iş modu + aktif_not + eğitim toplamaz; context normalize bff_otomatik
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("BILDIRIM", "false")

from skills import bff_kesif as BK  # noqa: E402

_hata = 0


def chk(ad, kosul, ek=""):
    global _hata
    if not kosul:
        _hata += 1
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if ek and not kosul else ""))


BK.BFF_DIR = Path(tempfile.mkdtemp())
BK._api_cagri = lambda *a, **k: (_ for _ in ()).throw(AssertionError("Gerçek AI çağrısı!"))
yakala: dict = {}


def sahte_ai(cevap):
    def f(sistem, mesajlar, kapsam):
        yakala["sistem"] = sistem
        yakala["kapsam"] = kapsam
        yakala["metin"] = "\n".join(p.get("text", "") for p in mesajlar[0]["content"])
        return cevap
    return f


RAPOR = "<bff_rapor>\n## Ekran\n- /sports\n\n## CREATE\n- İstek: `POST /bff/sports` · status 201\n\n## UPDATE\n- `PUT /bff/sports/1`\n</bff_rapor>"

print("1) önbellek")
chk("rapor yok → None", BK.rapor_oku("https://uat.ornek/app/sports") is None)
BK.gorev_live_app_urls = lambda: ["https://uat.ornek/app/sports"]
BK.live_app_urls = lambda: ["https://dev.ornek/app"]
BK.canli_uygulama_baglami_hazirla = lambda **kw: f"CANLI gorev={kw.get('gorev')} base={kw.get('base_url_override')}\n{kw.get('hedef_tarif')}"
r = BK.kesfet("https://uat.ornek/app/sports", _ai=sahte_ai(RAPOR))
chk("kesfet ok + dosyalar yazıldı", r["ok"] and Path(r["yol"]).exists() and Path(r["yol"]).with_suffix(".json").exists(), r)
o = BK.rapor_oku("https://uat.ornek/app/sports")
chk("rapor_oku: md + meta + taze", o and "POST /bff/sports" in o["md"] and BK.taze_mi(o) and o["yas_gun"] < 0.1)
meta = Path(o["yol"]).with_suffix(".json")
m = json.loads(meta.read_text(encoding="utf-8"))
m["ts"] = time.time() - 8 * 86400
meta.write_text(json.dumps(m), encoding="utf-8")
chk("8 günlük rapor taze değil", not BK.taze_mi(BK.rapor_oku("https://uat.ornek/app/sports")))
chk("anahtar: ekran tarifi ayrı rapor", BK._anahtar("https://x/", "Sports") != BK._anahtar("https://x/", "Groups")
    and BK._anahtar("https://x/a", "") == BK._anahtar("https://x/a/", ""))

print("2) kesfet davranışı")
chk("görev hedefi → kapsam 'gorev', gorev=True", yakala["kapsam"] == "gorev" and "gorev=True" in yakala["metin"])
plan = yakala["metin"]
chk("plan: CRUD adımları + kayıt kalsın + ayrı kayıtta sil + geri alınamaz hariç + AI-TEST",
    all(x in plan for x in ("OLUŞTUR", "GÜNCELLE", "SİL", "DOĞRULAMA", "KALSIN", "AYRI ikinci", "GERİ ALINAMAZ", "AI-TEST-")), plan[:200])
chk("çıktı biçimi + maskeleme kuralı", "<bff_rapor>" in plan and "MASKELE" in plan)
r2 = BK.kesfet("https://dev.ornek/app", "Sport Basic Data › Sports", ekran_bazli=True, _ai=sahte_ai(RAPOR))
chk("ekran bazlı → base URL + 'surec' + ekran tarifi planda", yakala["kapsam"] == "surec" and "base=https://dev.ornek" in yakala["metin"]
    and "hedef ekran: Sport Basic Data › Sports" in yakala["metin"] and r2["ok"])
BK.gorev_live_app_urls = lambda: []
r3 = BK.kesfet("", _ai=lambda *a: (_ for _ in ()).throw(AssertionError("çağrılmamalı")))
chk("canlı hedef yoksa AI çağrılmaz, ok=False", not r3["ok"] and "tanımlı değil" in r3["neden"])
BK.gorev_live_app_urls = lambda: ["https://uat.ornek/app/x"]
r4 = BK.kesfet("https://uat.ornek/app/x", _ai=sahte_ai("<bff_rapor>\n## Gezilemeyen\n- login reddedildi\n</bff_rapor>"))
chk("eksik rapor → ok=False ama kaydedilir (neden açıklanır)", not r4["ok"] and "yarım" in r4["neden"] and Path(r4["yol"]).exists())
chk("eksik rapor taze sayılmaz → otomatik tekrar dener", not BK.taze_mi(BK.rapor_oku("https://uat.ornek/app/x")))
r5 = BK.kesfet("https://uat.ornek/app/x", _ai=lambda *a: "rapor bloğu yok")
chk("blok yok → ok=False, neden", not r5["ok"] and "üretilemedi" in r5["neden"])

print("3) ayar + blok")
BK.load_context_filter = lambda: {"live_app_gorev": {"bff_otomatik": False}}
chk("bff_otomatik=false → kapalı", BK.otomatik_acik() is False)
BK.load_context_filter = lambda: {"live_app_gorev": {}}
chk("varsayılan açık", BK.otomatik_acik() is True)
blok = BK.rapor_blogu(r)
chk("rapor bloğu: başlık + UYDURMA kuralı + md", blok.startswith("### BFF SÖZLEŞME RAPORU") and "UYDURMA" in blok and "POST /bff/sports" in blok)

print("4) analiz motoru")
from skills import jira_gorevleri as JG  # noqa: E402
JG.referans_dosyalari_hazirla = lambda *a, **k: []
JG.canli_uygulama_baglami_hazirla = lambda *a, **k: ""
JG.load_context_filter = lambda *a, **k: {}
JG._gorev_acik_sorular_uret = lambda *a, **k: ""
import skills.ornek_havuzu as OH  # noqa: E402
OH.ornek_bloklari = lambda *a, **k: []
gorulen = []


def _api(s, m, **k):
    gorulen.append("\n".join(p.get("text", "") for p in m[0]["content"] if isinstance(p, dict)))
    return "<teknik_analiz>## 1. Amaç\nx\n</teknik_analiz>"


JG._api_cagri = _api
JG.gorev_analiz_et({"key": "MBSTRADE-1", "summary": "s", "description": "d" * 50, "issuetype": "Görev"}, bff_rapor=blok)
chk("gorev_analiz_et: BFF bloğu promptta", "BFF SÖZLEŞME RAPORU" in gorulen[-1])
gorulen.clear()
JG.gorev_analiz_et({"key": "MBSTRADE-1", "summary": "s", "description": "d" * 50, "issuetype": "Görev"})
chk("bff_rapor yoksa blok yok", "BFF SÖZLEŞME RAPORU" not in gorulen[-1])
gorulen.clear()
JG.gorev_fe_be_analiz({"key": "MBSTRADE-2", "summary": "s", "description": "d" * 50, "issuetype": "Görev"}, bff_rapor=blok)
chk("fe-be: iki çağrıda da BFF bloğu", len(gorulen) == 2 and all("BFF SÖZLEŞME RAPORU" in g for g in gorulen))

print("5) app + normalize")
import app as A  # noqa: E402
src = Path(A.__file__).read_text(encoding="utf-8")
chk("app: bff-kesif modu + otomatik keşif + aktif_not", 'mode == "bff-kesif"' in src and "bff_kesif.taze_mi" in src and '"aktif_not": job.get("aktif_not", "")' in src)
cagri = []
A._ornek_yakala_md = lambda *a, **k: cagri.append(a)
A._gorev_egitim_topla("MBSTRADE-9", "x", "", "bff-kesif", {"markdown": "y" * 500})
chk("bff-kesif eğitim havuzuna girmez", cagri == [])
from skills.base import _context_filter_normalize  # noqa: E402
n = _context_filter_normalize({"live_app_gorev": {"target_url": "https://u/x", "bff_otomatik": False}})
chk("normalize: bff_otomatik korunur (false) / varsayılan true",
    n["live_app_gorev"]["bff_otomatik"] is False and _context_filter_normalize({})["live_app_gorev"]["bff_otomatik"] is True)

print()
if _hata:
    print(f"BFF KEŞFİ TESTLERİ BAŞARISIZ ({_hata} hata)")
    sys.exit(1)
print("BFF KEŞFİ TESTLERİ GEÇTİ")
