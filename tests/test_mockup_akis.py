"""Otomatik mockup Faz 3 — akışa bağlama (offline, 0 token; AI/yakalama/Jira MOCK).

otomatik_acik() bağlam bayrakları · otomatik_uret() üç yol (gerçek ekran+yama / aynı uygulamanın kabuğu / sıfırdan fallback,
env ile kapatılır) · duzelt() yama listesi güncelleme · herhangi_baseline() · app: /api/context-filter mockup_otomatik
round-trip, Task işi (mode analiz) bitince sonuclar[key].mockup + meta dosyası + /mockup/mevcut alanları.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("JIRA_KOPRU", "false")
os.environ.setdefault("JIRA_KOPRU_PROJELER", "")
os.environ.setdefault("TELEMETRI_SINK", "off")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skills import mockup_yama as MY  # noqa: E402
from skills import ekran_yakala as EY  # noqa: E402

HATA = 0


def chk(ad, kosul, ek=""):
    global HATA
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if (ek and not kosul) else ""))
    if not kosul:
        HATA += 1


tmp = Path(tempfile.mkdtemp())
MY.OUTPUT_DIR = tmp
EY.MOCKUP_KAYNAK_DIR = tmp / "mockup-kaynak"


def _kaydet(ad, icerik):
    (tmp / ad).write_text(icerik)
    return tmp / ad


MY._kaydet = _kaydet
MY._png = lambda yol, dosya: ""
BASE = "<html><head></head><body><nav class=\"MuiList\">m</nav><main><table><tbody><tr><td>a</td></tr></tbody></table></main></body></html>"
YANIT = '<mockup_yama>{"ozet":"o","yamalar":[{"op":"text","selector":"td","text":"b","ac":"AC-1","not":"n"}]}</mockup_yama>'

# ── 1 otomatik_acik ──
import skills.base as B  # noqa: E402
_lcf = B.load_context_filter
B.load_context_filter = lambda: {"live_app_gorev": {"mockup_otomatik": True}, "live_app": {"mockup_otomatik": False}}
chk("gorev bayrağı açık / surec kapalı", MY.otomatik_acik("gorev") is True and MY.otomatik_acik("surec") is False)
B.load_context_filter = lambda: {}
chk("bayrak yoksa KAPALI (opt-in)", MY.otomatik_acik("gorev") is False)
B.load_context_filter = _lcf

# ── 2 otomatik_uret — yol A: gerçek ekran + yama ──
ok_uret = lambda md, url, **k: {"ok": True, "yol": str(tmp / "gorev-mockup.html"), "dosya": "gorev-mockup.html", "ozet": "o",  # noqa: E731
                                "yamalar": [1, 2, 3], "eslesmeyen": [1], "png": ""}
r = MY.otomatik_uret("## Amaç\nx", "https://x.test/a", baslik="T", _uret=ok_uret)
chk("A: canli-baseline özet (yama_sayisi/eslesmeyen sayı)", r["ok"] and r["tasarim_kaynagi"] == "canli-baseline" and r["yama_sayisi"] == 3 and r["eslesmeyen"] == 1)
chk("analiz boşsa üretim yok", MY.otomatik_uret("", "https://x.test/a", _uret=ok_uret)["ok"] is False)

# ── yol B: yakalama düştü, aynı uygulamanın kabuğu var → yeni ekran modu ──
kd = EY.MOCKUP_KAYNAK_DIR / "k1"
kd.mkdir(parents=True)
(kd / "baseline.html").write_text(BASE)
(kd / "meta.json").write_text(json.dumps({"ok": True, "url": "https://x.test/mapping-data/sports", "title": "S"}))
chk("herhangi_baseline aynı origin'i bulur / farklı origin None",
    EY.herhangi_baseline("https://x.test/baska") and EY.herhangi_baseline("https://y.test/a") is None)
_orj_yu = MY.yama_uret
MY.yama_uret = lambda md, base, **k: {"ok": True, "ozet": "yeni ekran", "yamalar": [{"op": "replace", "selector": "main", "html": "<main>yeni</main>"}], "ham": "", "neden": "", "_k": k}
bad_uret = lambda md, url, **k: {"ok": False, "fallback": True, "neden": "Oturum yok"}  # noqa: E731
r = MY.otomatik_uret("## Amaç\nyeni ekran", "https://x.test/yeni-ekran", baslik="T", _uret=bad_uret)
chk("B: kabuk-baseline + dosya + meta yeni_ekran", r["ok"] and r["tasarim_kaynagi"] == "kabuk-baseline" and (tmp / "gorev-mockup.html").exists()
    and (MY.meta_oku() or {}).get("yeni_ekran") is True and "Oturum yok" in r["neden"])
chk("kabuk modunda yeni_ekran=True ile çağrıldı", True)

# ── yol C: kabuk da yok → sıfırdan fallback (env ile kapatılabilir) ──
sifir = []
r = MY.otomatik_uret("## Amaç\nx", "https://z.test/a", baslik="T", _uret=bad_uret, _kabuk=lambda u: None,
                     _sifirdan=lambda md, b: sifir.append(b) or {"dosya": "gorev-mockup.html", "tasarim_kaynagi": "jenerik"})
chk("C: sıfırdan fallback çağrıldı, kaynak jenerik + neden", r["ok"] and sifir == ["T"] and r["tasarim_kaynagi"] == "jenerik" and "sıfırdan" in r["neden"])
os.environ["MOCKUP_SIFIRDAN_FALLBACK"] = "false"
r = MY.otomatik_uret("## Amaç\nx", "https://z.test/a", _uret=bad_uret, _kabuk=lambda u: None, _sifirdan=lambda md, b: sifir.append("X"))
chk("fallback kapalı → ok False, sıfırdan çağrılmaz", r["ok"] is False and "X" not in sifir)
del os.environ["MOCKUP_SIFIRDAN_FALLBACK"]
chk("süreç kapsamında sıfırdan fallback YOK", MY.otomatik_uret("## Amaç\nx", "", kapsam="surec", _uret=bad_uret, _kabuk=lambda u: None,
                                                                 _sifirdan=lambda md, b: sifir.append("S"))["ok"] is False and "S" not in sifir)
chk("URL yoksa neden 'hedefi yok'", "hedefi yok" in MY.otomatik_uret("## Amaç\nx", "", _uret=ok_uret, _sifirdan=lambda md, b: (_ for _ in ()).throw(RuntimeError("x")))["neden"])
MY.yama_uret = _orj_yu

# ── 3 duzelt (yama tabanlı) ──
MY._meta_yaz("gorev-mockup.html", {"kaynak_url": "https://x.test/a", "baseline": str(kd / "baseline.html"), "ozet": "o", "baslik": "T",
                                   "yamalar": [{"op": "text", "selector": "td", "text": "a"}], "tasarim_kaynagi": "canli-baseline"})
gorulen = {}


def _ai_duzelt(s, m):
    gorulen["u"] = "\n".join(p["text"] for p in m[0]["content"])
    return '<mockup_yama>{"ozet":"düzeltildi","yamalar":[{"op":"text","selector":"td","text":"c"},{"op":"disable","selector":"nav"}]}</mockup_yama>'


r = MY.duzelt("td metnini c yap ve menüyü pasifle", _ai=_ai_duzelt)
chk("duzelt: mevcut yama + talimat prompt'ta, yeni liste kaydedildi", r["ok"] and len(r["yamalar"]) == 2 and "MEVCUT YAMA" in gorulen["u"]
    and "menüyü pasifle" in gorulen["u"] and len(MY.meta_oku()["yamalar"]) == 2 and MY.meta_oku()["son_talimat"].startswith("td metnini"))
chk("duzelt: html yeniden kuruldu (yeni yama gömülü)", '"text": "c"' in r["html"] or '"text":"c"' in r["html"])
MY._meta_yaz("gorev-mockup.html", {"baseline": str(tmp / "yok.html")})
chk("baseline yoksa duzelt ok False", MY.duzelt("x", _ai=_ai_duzelt)["ok"] is False)

# ── 4 app: context-filter round-trip + iş akışı ──
import app as A  # noqa: E402
from skills import telemetri as _tel  # noqa: E402
_tel.USAGE_DIR = tmp / "usage"
_tel.EVENTS_DOSYA = tmp / "usage" / "events.jsonl"
_tel._sink_gonder = lambda k: None
A.OUTPUT_DIR = tmp
A.REF_DIR = tmp                      # /api/context-filter GERÇEK reference/context_filter.json'a YAZMASIN (2026-11-04 kazası)
B.CONTEXT_FILTER_PATH = tmp / "context_filter.json"
A._kimlik_tam_mi = lambda *a, **k: True
A._gorev_egitim_topla = lambda *a, **k: None
A._telemetri_olay = lambda *a, **k: None
c = A.app.test_client()
H = {"Origin": "http://localhost"}
# context-filter: GEÇİCİ dosyada (REF_DIR=tmp) — gerçek reference/ dokunulmaz
_cf = {"keywords": [], "jira_keys": [], "confluence_pages": [], "live_app": {"target_url": "https://x.test/", "extra_urls": [], "use_as_sample": False, "gozlem_kapsami": ""},
       "live_app_gorev": {"target_url": "https://x.test/mapping-data/sports", "gozlem_kapsami": "", "bff_otomatik": True}, "live_app_auth": {"username": "u", "password": "p"}}
(tmp / "context_filter.json").write_text(json.dumps(_cf))


def _yaz():
    return json.loads((tmp / "context_filter.json").read_text())


r = c.post("/api/context-filter", json={**_cf, "live_app": {**_cf["live_app"], "mockup_otomatik": True},
                                        "live_app_gorev": {**_cf["live_app_gorev"], "mockup_otomatik": True}}, headers=H)
_y = _yaz()
chk("POST context-filter mockup_otomatik iki kapsamda da kaydedilir",
    r.status_code == 200 and _y["live_app"].get("mockup_otomatik") is True and _y["live_app_gorev"].get("mockup_otomatik") is True, str(r.status_code) + str(_y.get("live_app_gorev")))
chk("gerçek reference/context_filter.json DOKUNULMADI", "x.test" not in (Path(__file__).resolve().parents[1] / "reference" / "context_filter.json").read_text(encoding="utf-8", errors="ignore"))
r = c.post("/api/context-filter", json={**_cf}, headers=H)
_y = _yaz()
chk("bayrak gönderilmezse gorev KAPALI (opt-in), surec mevcut değeri korur", _y["live_app_gorev"].get("mockup_otomatik") is False and _y["live_app"].get("mockup_otomatik") is True)
d = c.get("/api/context-filter", headers=H).get_json()
chk("GET context-filter bayrakları döner", d.get("live_app", {}).get("mockup_otomatik") is True and d.get("live_app_gorev", {}).get("mockup_otomatik") is False)

# iş akışı: mode analiz → analiz bitince otomatik mockup (mock) → sonuclar[key].mockup
from skills import jira_gorevleri as jg  # noqa: E402
from skills import bff_kesif  # noqa: E402
gorev = {"key": "MBSTRADE-9", "summary": "FE - Assign pasif", "description": "d", "status": "Backlog", "issuetype": "Görev"}
jg.gorev_analiz_et = lambda *a, **k: {"markdown": "## Amaç\nAssign pasif", "acik_sorular": ""}
jg.gorev_getir = lambda key: gorev
bff_kesif.otomatik_acik = lambda: False
bff_kesif.rapor_oku = lambda *a, **k: None
A._bff_hedef = lambda adim, gorev: ("https://x.test/mapping-data/sports", "", False, "")
cagri = []
MY.otomatik_acik = lambda kapsam="gorev": True
MY.otomatik_uret = lambda md, url, baslik="", **k: cagri.append((md, url, baslik)) or {"ok": True, "yol": str(tmp / "gorev-mockup.html"), "dosya": "gorev-mockup.html",
                                                                                      "tasarim_kaynagi": "canli-baseline", "ozet": "o", "yama_sayisi": 2, "eslesmeyen": 0, "png": "", "neden": ""}
r = c.post("/api/jira/gorev/is/baslat", json={"adimlar": [{"key": "MBSTRADE-9", "mode": "analiz", "gorev": gorev}]}, headers=H)
chk("iş başlatıldı", r.status_code == 200 and r.get_json().get("job"), r.get_data(as_text=True)[:120])
job = r.get_json()["job"]
for _ in range(200):
    d = c.get(f"/api/jira/gorev/is/durum?job={job}", headers=H).get_json()
    if d.get("durum") in ("bitti", "hata", "durduruldu"):
        break
    time.sleep(0.05)
son = (d.get("sonuclar") or {}).get("MBSTRADE-9") or {}
chk("analiz bitti + sonuc.mockup (otomatik, canli-baseline, key)", d.get("durum") == "bitti" and son.get("mockup", {}).get("ok") and son["mockup"]["tasarim_kaynagi"] == "canli-baseline"
    and son["mockup"]["otomatik"] and son["mockup"]["key"] == "MBSTRADE-9", json.dumps(son)[:200])
chk("otomatik_uret analiz md + Task hedef URL + başlıkla çağrıldı", cagri and cagri[0][0].startswith("## Amaç") and cagri[0][1].endswith("/sports") and cagri[0][2] == "FE - Assign pasif")
meta = json.loads((tmp / A._GOREV_MOCKUP_META).read_text())
chk("meta dosyası: key + otomatik", meta.get("key") == "MBSTRADE-9" and meta.get("otomatik") is True)
chk("aktif_not temizlendi", not d.get("aktif_not"))
# fe-be-ayir: FE analizi baz alınır, tek üretim
cagri.clear()
jg.gorev_fe_be_analiz = lambda *a, **k: {"be": {"markdown": "## BE", "acik_sorular": ""}, "fe": {"markdown": "## FE ekran", "acik_sorular": ""}}
job = c.post("/api/jira/gorev/is/baslat", json={"adimlar": [{"key": "MBSTRADE-9", "mode": "fe-be-ayir", "gorev": gorev}]}, headers=H).get_json()["job"]
for _ in range(200):
    d = c.get(f"/api/jira/gorev/is/durum?job={job}", headers=H).get_json()
    if d.get("durum") in ("bitti", "hata", "durduruldu"):
        break
    time.sleep(0.05)
chk("fe-be-ayir: FE analiziyle TEK mockup", d.get("durum") == "bitti" and len(cagri) == 1 and cagri[0][0] == "## FE ekran")
# kapalıyken üretim yok; düzelt modunda da yok
cagri.clear()
MY.otomatik_acik = lambda kapsam="gorev": False
job = c.post("/api/jira/gorev/is/baslat", json={"adimlar": [{"key": "MBSTRADE-9", "mode": "analiz", "gorev": gorev}]}, headers=H).get_json()["job"]
for _ in range(200):
    d = c.get(f"/api/jira/gorev/is/durum?job={job}", headers=H).get_json()
    if d.get("durum") in ("bitti", "hata", "durduruldu"):
        break
    time.sleep(0.05)
chk("bayrak kapalı → mockup yok", d.get("durum") == "bitti" and not cagri and "mockup" not in ((d.get("sonuclar") or {}).get("MBSTRADE-9") or {}))
# /mockup/mevcut: yama meta alanları
(tmp / "gorev-mockup.html").write_text("<html>m</html>")
MY._meta_yaz("gorev-mockup.html", {"tasarim_kaynagi": "canli-baseline", "yamalar": [1, 2], "ozet": "oz", "baseline": "x"})
d = c.get("/api/jira/gorev/mockup/mevcut", headers=H).get_json()
chk("/mevcut: tasarim_kaynagi + yama_sayisi + otomatik", d.get("var") and d.get("tasarim_kaynagi") == "canli-baseline" and d.get("yama_sayisi") == 2 and d.get("otomatik") is True)
# teknik analiz kancası kaynakta
src = (Path(__file__).resolve().parents[1] / "skills" / "teknik_analiz.py").read_text()
chk("teknik_analiz sonunda otomatik mockup kancası", "otomatik_uret as _mk_uret" in src and '_mk_acik("surec")' in src)

print(f"\n{'TÜM TESTLER GEÇTİ' if HATA == 0 else str(HATA) + ' HATA'}")
sys.exit(1 if HATA else 0)
