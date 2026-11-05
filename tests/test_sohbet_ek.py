"""İnteraktif Analiz — sohbete ekran görüntüsü eki (owner 2026-11-05). ek_kaydet doğrulama/güvenli ad, ek_yolu yol gezinmesi
reddi, sohbet_mesaj: CLI modunda Read yolu notu + okunur_dosyalar, API modunda image bloğu, eski mesajın eki ad olarak kalır,
uçlar (yükle/göster/mesaj). Offline / 0 token; gerçek oturum/ek dizinine DOKUNMAZ."""
import io
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("TELEMETRI_SINK", "off")

from skills import base as B  # noqa: E402
from skills import sohbet_analiz as SA  # noqa: E402

tmp = Path(tempfile.mkdtemp())
SA._SOHBET_DIR = tmp
SA._OTURUM_DOSYA = tmp / "oturum.json"
SA._EK_DIR = tmp / "ekler"
B.CONTEXT_FILTER_PATH = tmp / "context_filter.json"
B.CONTEXT_FILTER_PATH.write_text("{}", encoding="utf-8")
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
hatalar = []


def chk(ad, kosul, ek=""):
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f" — {ek}" if ek and not kosul else ""))
    if not kosul:
        hatalar.append(ad)


print("1) ek_kaydet / ek_yolu")
ek = SA.ek_kaydet("Ekran Görüntüsü 2026.png", PNG)
chk("güvenli ad (ek-<ts>-<hex>.png) + dosya yazıldı", SA._EK_AD.match(ek["ad"]) and Path(ek["yol"]).read_bytes() == PNG)
for kotu, veri, neden in (("x.pdf", PNG, "uzantı"), ("x.png", b"", "boş"), ("x.png", b"0" * (SA._EK_AZAMI_BAYT + 1), "boyut")):
    try:
        SA.ek_kaydet(kotu, veri)
        chk(f"ret: {neden}", False)
    except ValueError:
        chk(f"ret: {neden}", True)
chk("ek_yolu: yol gezinmesi / desen dışı → None", SA.ek_yolu("../oturum.json") is None and SA.ek_yolu("ek-1-abcdef.png") is None
    and SA.ek_yolu(ek["ad"]) == SA._EK_DIR / ek["ad"])

print("2) sohbet_mesaj — CLI modu: Read yolu notu + okunur_dosyalar; eski ek ad olarak kalır")
yak = {}


def sahte_ai(sistem, mesajlar, **kw):
    yak["mesajlar"] = mesajlar
    yak["kw"] = kw
    return "gördüm"


SA._api_cagri = sahte_ai
SA.referans_dosyalari_hazirla = lambda: []
SA.live_app_urls = lambda: []
B.USE_CLAUDE_CLI = True
SA.oturum_sifirla()
o = SA.sohbet_mesaj("bu ekrana bak", ekler=[ek["ad"], "ek-1-abcdef.png", "../x"])
son_user = [m for m in yak["mesajlar"] if m["role"] == "user"][-1]
metin = "\n".join(p.get("text", "") for p in son_user["content"] if p.get("type") == "text")
chk("mesaj kaydı yalnız geçerli ek adıyla", o["mesajlar"][0].get("ekler") == [ek["ad"]])
chk("CLI: prompta 'Read aracıyla AÇ' + mutlak yol; image bloğu YOK",
    "Read" in metin and ek["yol"] in metin and not any(p.get("type") == "image" for p in son_user["content"]))
chk("CLI: _api_cagri okunur_dosyalar=[yol]", yak["kw"].get("okunur_dosyalar") == [str(Path(ek["yol"]).resolve())])
SA.sohbet_mesaj("devam")
kullanici = [m for m in yak["mesajlar"] if m["role"] == "user"]
eski = "\n".join(p.get("text", "") for p in kullanici[-2]["content"])
chk("sonraki turda eski ek yalnız AD olarak (Read yolu yok, okunur_dosyalar yok)",
    ek["ad"] in eski and "Read aracıyla" not in eski and "okunur_dosyalar" not in yak["kw"])
try:
    SA.sohbet_mesaj("", ekler=["ek-1-abcdef.png"])
    chk("metin boş + geçersiz ek → ValueError", False)
except ValueError:
    chk("metin boş + geçersiz ek → ValueError", True)
o = SA.sohbet_mesaj("", ekler=[ek["ad"]])
chk("metin boş + geçerli ek → varsayılan metin", "ekran görüntüsü" in o["mesajlar"][-2]["metin"])

print("3) API modu: image bloğu")
B.USE_CLAUDE_CLI = False
SA.oturum_sifirla()
SA.sohbet_mesaj("bak", ekler=[ek["ad"]])
son_user = [m for m in yak["mesajlar"] if m["role"] == "user"][-1]
img = [p for p in son_user["content"] if p.get("type") == "image"]
chk("API: image bloğu (png) + okunur_dosyalar yok", len(img) == 1 and img[0]["source"]["media_type"] == "image/png"
    and "okunur_dosyalar" not in yak["kw"])
B.USE_CLAUDE_CLI = True

print("4) base: Read-only araç argümanları")
args = B._yalin_cli_argumanlari(False, araclar=["Read"])
chk("--tools Read --allowedTools Read (boş --tools yok)", args[:4] == ["--tools", "Read", "--allowedTools", "Read"]
    and "" not in args)
chk("araç verilmezse eski davranış", B._yalin_cli_argumanlari(False)[:2] == ["--tools", ""])
chk("webp media type", B._GORSEL_MEDIA[".webp"] == "image/webp")

print("5) uçlar (Flask test client)")
sys.argv = ["test_sohbet_ek"]
import app as A  # noqa: E402
from skills import telemetri as T  # noqa: E402
T.USAGE_DIR = tmp / "usage"
T.EVENTS_DOSYA = T.USAGE_DIR / "events.jsonl"
T._sink_gonder = lambda k: None
A.app.config["TESTING"] = True
c = A.app.test_client()
h = {"Origin": "http://localhost"}
r = c.post("/api/sohbet/ek", data={"file": (io.BytesIO(PNG), "ss.png")}, headers=h, content_type="multipart/form-data")
d = r.get_json()
chk("POST /api/sohbet/ek → ad + url", r.status_code == 200 and d["ok"] and d["ek"]["url"].endswith(d["ek"]["ad"]), d)
r2 = c.post("/api/sohbet/ek", data={"file": (io.BytesIO(b"x"), "ss.txt")}, headers=h, content_type="multipart/form-data")
chk("uzantı reddi 400", r2.status_code == 400)
g = c.get(d["ek"]["url"])
chk("GET ek → dosya", g.status_code == 200 and g.data == PNG)
chk("GET desen dışı → 404", c.get("/api/sohbet/ek/..%2Foturum.json").status_code == 404 and c.get("/api/sohbet/ek/ek-1-abcdef.png").status_code == 404)
A._kimlik_tam_mi = lambda: True
r3 = c.post("/api/sohbet/mesaj", json={"metin": "", "ekler": [d["ek"]["ad"]]}, headers=h)
chk("POST mesaj yalnız ekle → ok, oturumda ekler", r3.status_code == 200 and r3.get_json()["oturum"]["mesajlar"][-2].get("ekler") == [d["ek"]["ad"]], r3.get_json())
r4 = c.post("/api/sohbet/mesaj", json={"metin": "", "ekler": []}, headers=h)
chk("boş mesaj + ek yok → 400", r4.status_code == 400)

print(f"\n{'SOHBET EK TESTLERİ GEÇTİ' if not hatalar else 'HATA: ' + ', '.join(hatalar)}")
sys.exit(1 if hatalar else 0)
