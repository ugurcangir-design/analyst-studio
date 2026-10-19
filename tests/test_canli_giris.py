"""Canlı uygulama GİRİŞ KAPISI — analiz öncesi giriş doğrulaması (offline, 0 token, AI MOCK).

Kapsam:
  1. durum(): URL yok → var=False, gerekli=False, 'gözlem yapılmadan' mesajı · URL var + sonuç yok → gerekli=True
  2. test_et(): başarılı/başarısız sonuç imzayla kaydedilir; durum() taze+ok → gerekli=False; başarısız taze → 'başlatılmaz'
  3. imza: URL ya da şifre değişince sonuç geçersiz (gerekli=True); geçerlilik süresi dolunca taze=False
  4. URL yoksa AI çağrılmaz; AI bozuk → ok=False net neden; gorev kapsamı gorev=True, surec kapsamı base override
  5. app: uçlar + arka plan iş store'u `_arka_plan_isleri_calisiyor` listesinde; UI kapısı iş başlatmadan önce çalışır
"""
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("BILDIRIM", "false")

from skills import canli_giris as CG  # noqa: E402
CG.oturum_durumu = lambda: {}   # kayıtlı agent oturumu YOK (gate davranışı deterministik)

_hata = 0


def chk(ad, kosul, ek=""):
    global _hata
    if not kosul:
        _hata += 1
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if ek and not kosul else ""))


CG.OUTPUT_DIR = Path(tempfile.mkdtemp())
CG._api_cagri = lambda *a, **k: (_ for _ in ()).throw(AssertionError("Gerçek AI çağrısı!"))
ctx = {"live_app_auth": {"username": "u", "password": "p1"}}
CG.load_context_filter = lambda: ctx
CG.gorev_live_app_urls = lambda: []
CG.live_app_urls = lambda: []
yak: dict = {}
CG.canli_uygulama_baglami_hazirla = lambda **kw: (yak.update(kw) or "CANLI")

print("1) durum — URL yok / var")
d = CG.durum("gorev")
chk("URL yok → var=False, gerekli=False, gözlemsiz bilgi", not d["var"] and not d["gerekli"] and "YAPILMADAN" in d["mesaj"])
CG.gorev_live_app_urls = lambda: ["https://uat-ornek.local/app/x"]
d = CG.durum("gorev")
chk("URL var + sonuç yok → gerekli=True", d["var"] and d["gerekli"] and d["giris"] is None and d["url"].startswith("https://uat"))

print("2) test_et + önbellek")
def ai(cevap):
    def f(s, m):
        yak["metin"] = "\n".join(p["text"] for p in m[0]["content"])
        return cevap
    return f
r = CG.test_et("gorev", _ai=ai('<giris_sonuc>{"ok": true, "neden": "", "ekran": "/dashboard", "menu": ["A"]}</giris_sonuc>'))
chk("başarılı giriş → ok + ekran + url, gorev kapsamı gorev=True", r["ok"] and r["ekran"] == "/dashboard" and r["url"].startswith("https://uat") and yak.get("gorev") is True)
d = CG.durum("gorev")
chk("durum: taze+ok → gerekli=False, 'doğrulandı'", not d["gerekli"] and d["giris"]["ok"] and d["giris"]["taze"] and "doğrulandı" in d["mesaj"])
r = CG.test_et("gorev", _ai=ai('<giris_sonuc>{"ok": false, "neden": "Wrong Password !!!"}</giris_sonuc>'))
d = CG.durum("gorev")
chk("başarısız giriş → neden aynen, gerekli=True, 'başlatılmaz'", not r["ok"] and r["neden"] == "Wrong Password !!!" and d["gerekli"] and "başlatılmaz" in d["mesaj"])

print("3) imza + geçerlilik")
CG.test_et("gorev", _ai=ai('<giris_sonuc>{"ok": true, "ekran": "/x"}</giris_sonuc>'))
chk("ok sonrası gerekli=False", not CG.durum("gorev")["gerekli"])
ctx["live_app_auth"]["password"] = "p2"
chk("şifre değişti → imza farklı → gerekli=True (taze değil)", CG.durum("gorev")["gerekli"] and not CG.durum("gorev")["giris"]["taze"])
ctx["live_app_auth"]["password"] = "p1"
CG.gorev_live_app_urls = lambda: ["https://dev-ornek.local/app"]
chk("URL değişti → gerekli=True", CG.durum("gorev")["gerekli"])
CG.gorev_live_app_urls = lambda: ["https://uat-ornek.local/app/x"]
chk("eski URL+şifre → yine taze/ok", not CG.durum("gorev")["gerekli"])
os.environ["GIRIS_TEST_GECERLILIK"] = "60"
import json  # noqa: E402
m = CG._oku("gorev")
m["ts"] = time.time() - 120
CG._dosya("gorev").write_text(json.dumps(m), encoding="utf-8")
chk("süre doldu → taze=False, gerekli=True", CG.durum("gorev")["gerekli"])
os.environ.pop("GIRIS_TEST_GECERLILIK", None)

print("4) güvenlik + surec kapsamı")
CG.gorev_live_app_urls = lambda: []
r = CG.test_et("gorev", _ai=lambda s, m: (_ for _ in ()).throw(AssertionError("çağrılmamalı")))
chk("URL yoksa AI çağrılmaz", not r["ok"] and "tanımlı değil" in r["neden"])
CG.live_app_urls = lambda: ["https://dev-ornek.local/app/deep/page"]
r = CG.test_et("surec", _ai=ai("tarayıcı açılmadı"))
chk("surec kapsamı: ANA adres override + bozuk çıktı → ok=False net neden", yak.get("base_url_override") == "https://dev-ornek.local" and not r["ok"] and "okunamadı" in r["neden"])
r = CG.test_et("surec", _ai=lambda s, m: (_ for _ in ()).throw(RuntimeError("MCP yok")))
chk("AI hatası → ok=False, fırlatmaz", not r["ok"] and "çalıştırılamadı" in r["neden"])

print("5) app + UI")
import app as A  # noqa: E402
src = Path(A.__file__).read_text(encoding="utf-8")
chk("app: uçlar + arka plan iş farkındalığı", '"/api/live-app/giris-durum"' in src and '"/api/live-app/giris-test"' in src and '("_giris_isler", "canlı uygulama giriş doğrulaması")' in src)
ui = Path(A.__file__).parent.joinpath("templates/index.html").read_text(encoding="utf-8")
chk("UI: kapı iş başlatmadan önce + canlı modlar + 'Girişi Doğrula' düğmesi", "if (!(await _jgCanliKapi(adimlar))) return;" in ui
    and "_JG_CANLI_MODLAR" in ui and "jgGirisDogrula()" in ui and "YAPILMADAN üretilecek" in ui)
from skills import sohbet_analiz as SA  # noqa: E402
chk("İnteraktif Girişi Test Et aynı çekirdeği kullanır", "canli_giris import test_et" in Path(SA.__file__).read_text(encoding="utf-8"))

print()
if _hata:
    print(f"CANLI GİRİŞ TESTLERİ BAŞARISIZ ({_hata} hata)")
    sys.exit(1)
print("CANLI GİRİŞ TESTLERİ GEÇTİ")
