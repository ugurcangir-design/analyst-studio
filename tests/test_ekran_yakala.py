"""Canlı ekran yakalama (mockup kaynağı) — offline, 0 token; Node/slot MOCK.

yakala(): slot alır, Node yakalayıcıyı çalıştırır, baseline/meta doğrular, login → ok False, 7 gün önbellek;
sadelestir(): script/svg/attr atılır, tablo satırları N örnek, aria-label/disabled/class korunur.
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skills import ekran_yakala as EY  # noqa: E402

HATA = 0


def chk(ad, kosul, ek=""):
    global HATA
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if (ek and not kosul) else ""))
    if not kosul:
        HATA += 1


tmp = Path(tempfile.mkdtemp())
EY.MOCKUP_KAYNAK_DIR = tmp
SLOT = (9, tmp / "slot-9")
URL = "https://uat-example.test/mapping-data/sports/"

HTML = ("<html><head><script>x()</script><style>.a{}</style></head><body>"
        "<svg><path d='M0 0'/></svg><button aria-label=\"Assign\" class=\"MuiButton-root css-1\" data-x=\"1\" style=\"c\">A</button>"
        "<button disabled>Unmap</button><table><tbody>"
        + "".join(f"<tr><td>r{i}</td></tr>" for i in range(10)) + "</tbody></table></body></html>")


def _fake_calistir(login=False, rc=0, html=HTML * 20, erisim_yok=False):
    def f(arg, zaman_asimi):
        d = Path(arg["out"])
        d.mkdir(parents=True, exist_ok=True)
        (d / "baseline.html").write_text(html)
        (d / "live.png").write_bytes(b"\x89PNG")
        meta = {"url": arg["url"], "title": "Sports | X", "login": login, "erisim_yok": erisim_yok,
                "html_kc": len(html), "css_kc": 10, "sheet": 2}
        return rc, json.dumps(meta), ""
    return f


# ── 1 taze yakalama ──
r = EY.yakala(URL, _calistir=_fake_calistir(), _slot=SLOT)
chk("ok + baseline + png", r["ok"] and Path(r["baseline"]).exists() and Path(r["png"]).exists(), r.get("neden"))
chk("url normalize (sondaki / atılır) + anahtar sabit", EY.anahtar(URL) == EY.anahtar(URL.rstrip("/")))
chk("meta.json yazıldı, ok True", json.loads((Path(r["dizin"]) / "meta.json").read_text())["ok"] is True)

# ── 2 önbellek: taze → Node ÇALIŞMAZ ──
r2 = EY.yakala(URL, _calistir=lambda a, z: (_ for _ in ()).throw(AssertionError("Node çağrıldı!")), _slot=SLOT)
chk("taze önbellek yeniden kullanıldı", r2["ok"] and r2["yeniden_kullanildi"] is True)
# bayat → yeniden çalışır
m = Path(r["dizin"]) / "meta.json"
eski = time.time() - (EY.onbellek_gun() * 86400 + 10)
import os  # noqa: E402
os.utime(m, (eski, eski))
r3 = EY.yakala(URL, _calistir=_fake_calistir(), _slot=SLOT)
chk("bayat önbellek → taze yakalama", r3["ok"] and r3["yeniden_kullanildi"] is False)
# yeniden=True → önbellek atlanır
sayac = {"n": 0}


def _say(a, z):
    sayac["n"] += 1
    return _fake_calistir()(a, z)


EY.yakala(URL, yeniden=True, _calistir=_say, _slot=SLOT)
chk("yeniden=True önbelleği atlar", sayac["n"] == 1)

# ── 3 login formu → ok False, önbelleğe TAZE sayılmaz ──
U2 = "https://dev-example.test/mapping-data/markets"
r = EY.yakala(U2, _calistir=_fake_calistir(login=True), _slot=SLOT)
chk("login → ok False + neden", r["ok"] is False and "Oturum" in r["neden"])
chk("başarısız kayıt taze sayılmaz", not EY.taze_mi(EY.oku(U2)))
r = EY.yakala(U2, _calistir=_fake_calistir(erisim_yok=True), _slot=SLOT)
chk("Access Denied → ok False + neden", r["ok"] is False and "Yetki" in r["neden"])
r = EY.yakala(U2, _calistir=_fake_calistir(rc=1), _slot=SLOT)
chk("Node rc≠0 → ok False", r["ok"] is False and "hata" in r["neden"].lower())
r = EY.yakala(U2, _calistir=_fake_calistir(html="<html></html>"), _slot=SLOT)
chk("boş baseline → ok False", r["ok"] is False)
chk("geçersiz URL → ok False", EY.yakala("mapping-data/sports", _calistir=_fake_calistir(), _slot=SLOT)["ok"] is False)

# ── 4 slot: gerçek _slot_al/_slot_birak kullanıldığında serbest bırakılır ──
from skills import base as B  # noqa: E402
_al, _birak = B._slot_al, B._slot_birak
birakildi = []
B._slot_al = lambda bekle_sn=None: (3, tmp / "slot-3")
B._slot_birak = lambda n=None: birakildi.append(n)
try:
    EY.yakala("https://x.test/a", yeniden=True, _calistir=lambda a, z: (_ for _ in ()).throw(RuntimeError("patladı")))
    chk("yakalayıcı hata verse de slot bırakılır", birakildi == [3])
    B._slot_al = lambda bekle_sn=None: None
    r = EY.yakala("https://x.test/b", yeniden=True, _calistir=_fake_calistir())
    chk("slot alınamazsa ok False", r["ok"] is False and "slot" in r["neden"].lower())
finally:
    B._slot_al, B._slot_birak = _al, _birak

# ── 5 sadeleştir ──
s = EY.sadelestir(HTML, satir_ornek=3)
chk("script/style/svg gövdesi atıldı", "x()" not in s and ".a{}" not in s and "M0 0" not in s and "<svg/>" in s)
chk("data-/style attr atıldı, aria-label+class+disabled korundu",
    'data-x' not in s and 'style="c"' not in s and 'aria-label="Assign"' in s and "MuiButton-root" in s and "disabled" in s)
chk("tablo 3 örnek satır + kalan notu", s.count("<tr>") == 3 and "7 satır daha" in s)
chk("azami kırpma", EY.sadelestir(HTML * 50, azami_kc=500).endswith("<!-- … kırpıldı -->"))

# ── 6 hazır / keşif (makineye bağlı; yalnız tip kontrolü) ──
ok, neden = EY.hazir()
chk("hazir() tuple döner", isinstance(ok, bool) and isinstance(neden, str))
chk("ozet metni", "yakalandı" in EY.ozet({"ok": True, "title": "T"}) and "yakalanamadı" in EY.ozet({"ok": False, "neden": "n"}))

print(f"\n{'TÜM TESTLER GEÇTİ' if HATA == 0 else str(HATA) + ' HATA'}")
sys.exit(1 if HATA else 0)
