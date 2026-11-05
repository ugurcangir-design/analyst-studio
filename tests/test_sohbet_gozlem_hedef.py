"""İnteraktif Analiz — canlı gözlem hedefi SOHBETTEN gelir; Süreç ekranının Bağlam Filtresi'ndeki
`live_app.gozlem_kapsami` (başka doküman için girilmiş) sohbet gözlemine/üretimine KARIŞMAZ.
Bulgu 2026-11-05: analist 'Sport Basic Data ekranlarını tara' dedi, gözlemci miras kapsamdaki
'Match Status filtresi / Match Info kolonu'nu aradı. Offline / 0 token."""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("TELEMETRI_SINK", "off")

from skills import base as B  # noqa: E402
from skills import sohbet_analiz as SA  # noqa: E402
from skills import surec_analizi as SU  # noqa: E402
from skills import teknik_analiz as TA  # noqa: E402

tmp = Path(tempfile.mkdtemp())
SA._OTURUM_DOSYA = tmp / "oturum.json"   # gerçek output/sohbet/oturum.json'a DOKUNMA
B.CONTEXT_FILTER_PATH = tmp / "context_filter.json"
B.CONTEXT_FILTER_PATH.write_text(json.dumps({
    "live_app": {"target_url": "https://dev-ornek.local/some/page", "use_as_sample": True,
                 "gozlem_kapsami": "match status filtresi All ile match info kolonu"},
    "live_app_auth": {"username": "u", "password": "p"},
}), encoding="utf-8")

hatalar = []


def chk(ad, kosul, ek=""):
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f" — {ek}" if ek and not kosul else ""))
    if not kosul:
        hatalar.append(ad)


# 1) base: kapsam_birlestir=False → miras kapsam bloğa girmez; True (varsayılan) → girer (Task/BFF davranışı korunur)
blok_t = B.canli_uygulama_baglami_hazirla(base_url_override="https://dev-ornek.local", hedef_tarif="Sports ekranı")
blok_f = B.canli_uygulama_baglami_hazirla(base_url_override="https://dev-ornek.local", hedef_tarif="Sports ekranı",
                                          kapsam_birlestir=False)
chk("varsayılan: miras gözlem kapsamı birleştirilir (Task/BFF yolu değişmedi)", "match info kolonu" in (blok_t or ""))
chk("kapsam_birlestir=False: miras kapsam bloğa GİRMEZ, hedef girer",
    "match info" not in (blok_f or "") and "Sports ekranı" in (blok_f or ""))

# 2) sohbet gözlem turu: hedef = mesaj, miras kapsam yok
blok_s = SA._canli_tabanli_baglam("sport basic data ekranı ana menüsü altını tara")
chk("sohbet hedefi: mesaj var, miras 'match status' yok",
    "sport basic data" in (blok_s or "") and "match status" not in (blok_s or "").lower())

# 3) sohbetten üretim: motorlara canlı blok override olarak sohbet hedefi gider
oturum = {"mesajlar": [{"rol": "analist", "metin": "Odds multiplier ondalık davranışı: Sports/Groups/Competitions edit modalı", "ts": 1},
                       {"rol": "agent", "metin": "tamam", "ts": 2}], "created": 0}
tarif = SA._sohbet_hedef_tarifi(oturum)
chk("hedef tarifi analist mesajlarından", "Odds multiplier" in tarif and "tamam" not in tarif)
yak = {}
SU.surec_analizi_yap = lambda **kw: (yak.update(kw) or Path("x"))
TA.teknik_analiz_yap = lambda **kw: (yak.update(kw) or (Path("x"), Path("y")))
SA._uretim_girdisi = lambda o: [{"type": "text", "text": "girdi"}]
SA.surec_uret(oturum)
cb = yak.get("canli_baglam_override") or ""
chk("surec_uret: canli_baglam_override sohbet hedefli, miras kapsamsız",
    "Odds multiplier" in cb and "match status" not in cb.lower() and yak.get("ozel_atla") is True)
yak.clear()
SA.teknik_uret(oturum)
cb = yak.get("canli_baglam_override") or ""
chk("teknik_uret: aynı override", "Odds multiplier" in cb and "match status" not in cb.lower())

# 5) 🌐 turu: agent'ın önceki turda önerdiği plan gözlem hedefine taşınır; modal kuralı gözlem promptuna girer;
#    tur bütçesi sohbet için yükseltilir (bulgu 2026-11-05: 'Edit Sport aç → 1,111111 yaz' planı gözlemciye gitmiyordu,
#    40 tur menü listelemeye gitti, hiçbir modal açılmadı)
from skills import gozlem as GZ  # noqa: E402
plan = "## Karar önerim\n`/basic-data/sports` → Edit Sport aç → Odd Multiplier Web'e `1,111111` yaz → kaç basamak kabul ediyor?"
ot = {"mesajlar": [{"rol": "analist", "metin": "multiplier işi", "ts": 1}, {"rol": "agent", "metin": "A" * 3000 + "\n" + plan, "ts": 2},
                   {"rol": "analist", "metin": "sport basic data altını tara, karar vererek ilerleyelim", "ts": 3, "gozlem": True}]}
h = SA._gozlem_hedefi(ot, "sport basic data altını tara, karar vererek ilerleyelim")
chk("gözlem hedefi: analist mesajı + önceki agent planı (son kısım, 'Edit Sport aç' + değer)",
    h.startswith("sport basic data altını tara") and "Edit Sport aç" in h and "1,111111" in h and "A" * 2000 not in h)
chk("önceki agent yanıtı yoksa hedef = mesaj", SA._gozlem_hedefi({"mesajlar": [{"rol": "analist", "metin": "x"}]}, "x") == "x")
dl = GZ._dogrulama_listesi(h)
chk("gözlem zorunlu listesi: hedefte Edit/modal geçince 'modalı AÇ' maddesi", "modalı AÇ" in dl and "Save'e basmadan" in dl)
chk("hedefte modal/parametre yoksa liste boş (prompt büyümez)", GZ._dogrulama_listesi("listeyi tara") == "")
chk("rapor formatı: modal = gözlem hedefi + önce derinlik kuralı",
    "MODAL/FORM = GÖZLEM HEDEFİ" in GZ._RAPOR_FORMAT and "ÖNCE DERİNLİK" in GZ._RAPOR_FORMAT)
gz_kw = {}
GZ.rapor_al = lambda canli, kapsam, gorev_ozet="", yeniden=True, **k: (gz_kw.update({"ozet": gorev_ozet, "canli": canli, **k})
                                                                       or {"ok": True, "md": "## Ekran\n- x `[K: Canlı UI:/x]`"})
SA._api_cagri = lambda *a, **k: "tamam"
SA.referans_dosyalari_hazirla = lambda: []
SA.oturum_sifirla()
SA.sohbet_mesaj("multiplier işi")
o = SA.oturum_oku()
o["mesajlar"][-1]["metin"] = plan
SA._oturum_yaz(o)
B.CONTEXT_FILTER_PATH.write_text(json.dumps({"live_app": {"target_url": "https://dev-ornek.local/some/page"},
                                             "live_app_auth": {"username": "u", "password": "p"}}), encoding="utf-8")
SA.sohbet_mesaj("sport basic data altını tara", gozlem=True)
chk("sohbet_mesaj(gozlem=True): rapor_al özeti + canlı bloğu planı taşır, tur bütçesi 70 + devam 1",
    "Edit Sport aç" in gz_kw.get("ozet", "") and "Edit Sport aç" in gz_kw.get("canli", "")
    and gz_kw.get("max_turns") == 70 and gz_kw.get("tur_devam") == 1, gz_kw.keys())

# 4) URL yoksa override None → motor kendi (gözlemsiz) yoluna düşer
B.CONTEXT_FILTER_PATH.write_text(json.dumps({"live_app": {}}), encoding="utf-8")
chk("URL yoksa sohbet üretim canlı bloğu None", SA._uretim_canli_baglami(oturum) is None)

print(f"\n{'TÜM KONTROLLER GEÇTİ' if not hatalar else 'HATA: ' + ', '.join(hatalar)}")
sys.exit(1 if hatalar else 0)
