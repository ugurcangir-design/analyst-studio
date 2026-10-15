"""İnteraktif Analiz — sohbetten BFF Keşfi (offline, 0 token, AI enjekte).

Kapsam:
  1. bff_kesfet: ekran boş → ValueError; miras live_app ANA adresi + ekran_bazli → oturum.bff + sistem mesajı
     (bulunan yazma servisleri özeti); başarısız → neden mesajı; aynı ekran tekrar → tek kayıt
  2. _bff_raporlari_blogu: taze rapor sohbet turuna ve üretim girdisine girer; eski rapor girmez
  3. app: bff-kesif uç doğrulamaları + bff-rapor anahtar doğrulaması + oturum özeti 'bff'
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("BILDIRIM", "false")

from skills import sohbet_analiz as SA  # noqa: E402
from skills import bff_kesif as BK  # noqa: E402

_hata = 0


def chk(ad, kosul, ek=""):
    global _hata
    if not kosul:
        _hata += 1
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if ek and not kosul else ""))


tmp = Path(tempfile.mkdtemp())
SA._SOHBET_DIR = tmp
SA._OTURUM_DOSYA = tmp / "oturum.json"
BK.BFF_DIR = tmp / "bff"
SA.referans_dosyalari_hazirla = lambda *a, **k: []
SA.live_app_urls = lambda: ["https://dev-ornek.local/app/x"]
BK.live_app_urls = lambda: ["https://dev-ornek.local/app/x"]
yakala: dict = {}
BK.canli_uygulama_baglami_hazirla = lambda **kw: (yakala.update(kw) or f"CANLI base={kw.get('base_url_override')}")
RAPOR = "<bff_rapor>\n## Ekran\n- /sports\n\n## CREATE\n- İstek: `POST /bff/sports` · 201\n\n## DELETE (ayrı kayıt)\n- `DELETE /bff/sports/9`\n</bff_rapor>"
BK._api_cagri = lambda s, m, **k: RAPOR
SA.oturum_sifirla()

print("1) bff_kesfet")
try:
    SA.bff_kesfet("")
    chk("ekran boş → ValueError", False)
except ValueError:
    chk("ekran boş → ValueError", True)
r = SA.bff_kesfet("Sport Basic Data › Sports")
o = SA.oturum_oku()
chk("miras ANA adres + ekran hedefi (ekran bazlı)", yakala.get("base_url_override") == "https://dev-ornek.local"
    and "hedef ekran: Sport Basic Data › Sports" in yakala.get("hedef_tarif", ""), yakala)
chk("oturum.bff kaydı + sistem mesajı (POST, DELETE özeti)", r["ok"] and o["bff"][0]["ekran"] == "Sport Basic Data › Sports"
    and o["mesajlar"][-1].get("sistem") and "POST" in o["mesajlar"][-1]["metin"] and "DELETE" in o["mesajlar"][-1]["metin"]
    and o["mesajlar"][-1].get("bff_anahtar") == r["anahtar"], o["mesajlar"][-1])
SA.bff_kesfet("Sport Basic Data › Sports")
chk("aynı ekran tekrar → tek kayıt", len(SA.oturum_oku()["bff"]) == 1)
BK._api_cagri = lambda s, m, **k: "blok yok"
r2 = SA.bff_kesfet("Groups")
chk("başarısız → ok False + neden mesajı", not r2["ok"] and "tamamlanamadı" in SA.oturum_oku()["mesajlar"][-1]["metin"])

print("2) raporlar sohbete + üretime girer")
blok = SA._bff_raporlari_blogu()
chk("taze rapor bloğu (başarısız olan girmez)", blok.count("### BFF SÖZLEŞME RAPORU") == 1 and "POST /bff/sports" in blok)
gorulen: dict = {}
SA._api_cagri = lambda s, m, **k: (gorulen.update({"metin": "\n".join(p.get("text", "") for mm in m for p in (mm.get("content") or []) if isinstance(p, dict))}) or "ok")
SA.sohbet_mesaj("servisleri özetle")
chk("sohbet turunda BFF bloğu", "BFF SÖZLEŞME RAPORU" in gorulen["metin"] and "POST /bff/sports" in gorulen["metin"])
g = SA._uretim_girdisi(SA.oturum_oku())
chk("üretim girdisinde BFF bloğu ÖNCE, sohbet sonra", g[0]["text"].startswith("### BFF SÖZLEŞME RAPORU") and "İnteraktif Analiz Oturumu" in g[1]["text"])
meta = BK.BFF_DIR / f"{r['anahtar']}.json"
m = json.loads(meta.read_text(encoding="utf-8"))
m["ts"] = time.time() - 8 * 86400
meta.write_text(json.dumps(m), encoding="utf-8")
chk("8 günlük rapor girmez", SA._bff_raporlari_blogu() == "")
chk("rapor_oku_anahtar: geçersiz/eksik → None", SA.rapor_oku_anahtar(None) is None and SA.rapor_oku_anahtar("yokyokyokyok") is None)

print("3) app")
import app as A  # noqa: E402
A._kimlik_tam_mi = lambda *a, **k: True
c = A.app.test_client()
H = {"Origin": "http://localhost"}
chk("bff-kesif ekran yok → 400", c.post("/api/sohbet/bff-kesif", json={}, headers=H).status_code == 400)
chk("bff-rapor geçersiz anahtar → 400", c.get("/api/sohbet/bff-rapor?anahtar=xyz").status_code == 400)
chk("bff-rapor bulunamadı → 404", c.get("/api/sohbet/bff-rapor?anahtar=0123456789ab").status_code == 404)
chk("oturum özeti 'bff' alanı", "bff" in A._sohbet_ozet({"mesajlar": []}))
src = Path(A.__file__).read_text(encoding="utf-8")
chk("iş dağıtımı: hedef 'bff'", 'elif hedef == "bff":' in src)

print()
if _hata:
    print(f"SOHBET BFF TESTLERİ BAŞARISIZ ({_hata} hata)")
    sys.exit(1)
print("SOHBET BFF TESTLERİ GEÇTİ")
