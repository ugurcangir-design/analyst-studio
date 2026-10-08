"""Task analizi eğitim toplama — sunucu deposu + few-shot havuzu (offline, 0 token).

Sink push MOCK'lanır, depo/havuz geçici dizine yönlendirilir → ekip havuzu ve gerçek
output/ kirlenmez. Kapsam:
  1. /api/jira/gorev/egitime-ekle doğrulama + başarı → depo + havuz + push
  2. Aynı key tekrar eklenince depo güncel sürüm, havuzda TEK örnek (dedup)
  3. FE+BE ayrı analiz otomatik toplama: BE=key, FE=key::FE → iki örnek de KALIR
     (regresyon: ikisi aynı jira_key ile yakalanınca dedup birini siliyordu) ve
     kurtarma UI entry anahtarlarıyla bulur.
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("BILDIRIM", "false")

import app as A  # noqa: E402
import skills.gorev_deposu as GD  # noqa: E402
import skills.ornek_havuzu as OH  # noqa: E402

_tmp = Path(tempfile.mkdtemp())
GD.DEPO_DIR = _tmp / "depo"
OH.ORNEK_DIR = _tmp / "ornekler"
OH._DURUM_DOSYA = OH.ORNEK_DIR / ".durum.json"
_pushlar: list = []
OH._sink_push = lambda k: _pushlar.append(k)

c = A.app.test_client()
H = {"Origin": "http://localhost"}
_hata = 0


def chk(ad, kosul, ek=""):
    global _hata
    if not kosul:
        _hata += 1
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if ek and not kosul else ""))


def bekle_push(n):
    for _ in range(100):
        if len(_pushlar) >= n:
            time.sleep(0.05)
            return
        time.sleep(0.05)


def ornekler():
    return [json.loads(p.read_text()) for p in OH.ORNEK_DIR.glob("*.json") if not p.name.startswith(".")]


def ekle(key, md):
    return c.post("/api/jira/gorev/egitime-ekle", headers=H,
                  json={"key": key, "markdown": md, "summary": "Test task", "katman": "be"})


md1 = "## Sorun\n" + "Birinci sürüm. " * 30
md2 = "## Sorun\n" + "İKİNCİ sürüm. " * 30

print("1) egitime-ekle")
chk("boş gövde 400", ekle("", "").status_code == 400)
chk("kısa içerik 400", ekle("ZZT-1", "kisa").status_code == 400)
r = ekle("zzt-1", md1)
chk("başarı 200", r.status_code == 200 and r.get_json().get("ok"), r.get_json())
bekle_push(1)
k = c.get("/api/jira/gorev/analiz-kayit?key=ZZT-1").get_json()
chk("depoda var (key büyük harf)", k.get("var") and "Birinci" in k.get("markdown", ""))
chk("summary/katman saklandı", k.get("summary") == "Test task" and k.get("katman") == "be")
chk("havuzda 1 örnek + push", len(ornekler()) == 1 and len(_pushlar) == 1)

print("2) aynı key tekrar → güncel sürüm, tek örnek")
time.sleep(1.1)   # örnek id'si saniye çözünürlüklü olabilir
ekle("ZZT-1", md2)
bekle_push(2)
k = c.get("/api/jira/gorev/analiz-kayit?key=ZZT-1").get_json()
chk("depo güncel sürüm", "İKİNCİ" in k.get("markdown", ""))
o = ornekler()
chk("havuzda tek örnek (en güncel)", len(o) == 1 and "İKİNCİ" in json.dumps(o, ensure_ascii=False), len(o))

print("3) FE+BE otomatik toplama (regresyon)")
be_md = "## BE\n" + "Backend sözleşmesi. " * 30
fe_md = "## FE\n" + "Frontend ekranı. " * 30
A._gorev_egitim_topla("ZZT-2", "FEBE task", "", "analiz",
                      {"fe_be": {"be": {"markdown": be_md}, "fe": {"markdown": fe_md}}})
bekle_push(4)
time.sleep(0.3)
zzt2 = [x for x in ornekler() if (x.get("jira_key") or "").startswith("ZZT-2")]
chk("BE ve FE örneği ikisi de havuzda", len(zzt2) == 2, [x.get("jira_key") for x in zzt2])
kb = c.get("/api/jira/gorev/analiz-kayit?key=ZZT-2").get_json()
kf = c.get("/api/jira/gorev/analiz-kayit?key=ZZT-2::FE").get_json()
chk("BE kurtarma entry key (ZZT-2) ile bulunur", kb.get("var") and "Backend" in kb.get("markdown", ""))
chk("FE kurtarma entry key (ZZT-2::FE) ile bulunur", kf.get("var") and "Frontend" in kf.get("markdown", ""))

print("4) formatla modu toplanmaz")
n0 = len(_pushlar)
A._gorev_egitim_topla("ZZT-3", "x", "", "formatla", {"markdown": md1})
time.sleep(0.3)
chk("formatla → depo/havuz yok", len(_pushlar) == n0
    and not c.get("/api/jira/gorev/analiz-kayit?key=ZZT-3").get_json().get("var"))

print()
if _hata:
    print(f"GÖREV EĞİTİM TESTLERİ BAŞARISIZ ({_hata} hata)")
    sys.exit(1)
print("GÖREV EĞİTİM TESTLERİ GEÇTİ")
