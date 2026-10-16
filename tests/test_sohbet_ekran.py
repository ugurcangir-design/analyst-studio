"""İnteraktif Analiz — ekran bazlı iş + giriş testi + gözlemli tur + sıralı cevaplar (offline, 0 token, AI enjekte).

Kapsam:
  1. sohbet_mesaj(gozlem=True): canlı görev bloğu + kapsam 'surec' + önbellek kapalı; URL yoksa açıklama
  2. _cevaplanan_sorular_metni: bu oturumun cevapları sohbete/üretime girer, önceki oturumunki girmez
  3. giris_testi: ok / reddedildi / çıktı bozuk → oturum.giris + sistem mesajı; URL yoksa AI çağrılmaz
  4. ekran_listesi_cikar → oturum.ekranlar (normalize, ≤40) ; ekran_gorevleri → fe-be-ayir adımları, EKRAN-n, canlı hedef
  5. app: uç doğrulamaları + is başlatma Jira bağlantısı gerektirmez (tüm adımlar görev dict'li) + canli_hedef taşınır
     + sentetik EKRAN- eğitim havuzuna girmez + gorev_yeni_task_olustur sentetik kaynak bağını atlar
"""
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("BILDIRIM", "false")

from skills import sohbet_analiz as SA  # noqa: E402

_hata = 0


def chk(ad, kosul, ek=""):
    global _hata
    if not kosul:
        _hata += 1
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if ek and not kosul else ""))


tmp = Path(tempfile.mkdtemp())
SA._SOHBET_DIR = tmp
SA._OTURUM_DOSYA = tmp / "oturum.json"
SA.referans_dosyalari_hazirla = lambda *a, **k: []
yakala: dict = {}


def sahte_ai(cevap):
    def f(sistem, mesajlar, **kw):
        yakala["sistem"] = sistem
        yakala["kw"] = kw
        yakala["metin"] = "\n".join(p.get("text", "") for m in mesajlar for p in (m.get("content") or []) if isinstance(p, dict))
        return cevap
    return f


print("1) gözlemli tur")
SA.live_app_urls = lambda: ["https://dev-ornek.local/app"]
SA.canli_uygulama_baglami_hazirla = lambda **kw: f"### CANLI GÖREV base={kw.get('base_url_override')} hedef={kw.get('hedef_tarif')}"
SA._api_cagri = sahte_ai("Sports ekranında Export butonu YOK; kolonlar: Name, Code.")
SA.oturum_sifirla()
o = SA.sohbet_mesaj("Sports ekranını gözlemle", gozlem=True)
chk("canlı görev bloğu + base URL + hedef", "base=https://dev-ornek.local" in yakala["metin"] and "hedef=Sports ekranını gözlemle" in yakala["metin"])
chk("kapsam 'surec' + önbellek kapalı", yakala["kw"].get("canli_uygulama_kapsami") == "surec" and yakala["kw"].get("onbellek") is False)
chk("mesajlar gözlem bayraklı", o["mesajlar"][0].get("gozlem") and o["mesajlar"][1].get("gozlem"))
SA.sohbet_mesaj("normal soru")
chk("normal tur: canlı görev yok, kapsam None", "CANLI GÖREV" not in yakala["metin"] and yakala["kw"].get("canli_uygulama_kapsami") is None)
SA.live_app_urls = lambda: []
SA.sohbet_mesaj("gözlemle", gozlem=True)
chk("URL yoksa: modele 'tanımlı değil' notu, kapsam None", "tanımlı değil" in yakala["metin"] and yakala["kw"].get("canli_uygulama_kapsami") is None)
chk("sistem promptu: sırayla sor + BRD referansta + ekran task'ları", "SIRAYLA SOR" in yakala["sistem"] and "BRD YÜKLENMEZ" in yakala["sistem"] and "Ekran Task'ları Üret" in yakala["sistem"])

print("2) cevaplanan sorular bağlamı")
from skills import sorular as SQ  # noqa: E402
simdi = time.time()
SQ.sorular_yukle = lambda: {"sorular": [
    {"id": "Q-001", "kaynak_dosya": "surec-analizi.md", "durum": "cevaplandi", "cevap": "CSV ve Excel ikisi de",
     "soru": "Format?", "guncellendi_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(simdi + 5))},
    {"id": "Q-002", "kaynak_dosya": "surec-analizi.md", "durum": "varsayim", "varsayim": "Sync indirme", "soru": "Mod?",
     "guncellendi_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(simdi + 5))},
    {"id": "Q-009", "kaynak_dosya": "surec-analizi.md", "durum": "cevaplandi", "cevap": "ESKİ", "soru": "eski",
     "guncellendi_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(simdi - 7200))},
    {"id": "Q-003", "kaynak_dosya": "surec-analizi.md", "durum": "acik", "soru": "açık"},
]}
m = SA._cevaplanan_sorular_metni()
chk("bu oturumun cevabı + varsayımı girer, önceki oturum ve açık girmez",
    "Q-001" in m and "VARSAYIM: Sync" in m and "Q-009" not in m and "Q-003" not in m, m)
SA.sohbet_mesaj("devam")
chk("sohbet turuna CEVAPLANAN SORULAR bloğu", "CEVAPLANAN SORULAR" in yakala["metin"] and "CSV ve Excel" in yakala["metin"])
g = SA._uretim_girdisi(SA.oturum_oku())[0]["text"]
chk("üretim girdisine de girer", "Analistin kesin cevapları" in g and "CSV ve Excel" in g)

print("3) giriş testi")
# Çekirdek artık skills.canli_giris (Task Analizi giriş kapısıyla ORTAK) → mock'lar o modüle
from skills import canli_giris as CG  # noqa: E402
CG.OUTPUT_DIR = tmp
CG.live_app_urls = lambda: ["https://dev-ornek.local/app"]
CG.canli_uygulama_baglami_hazirla = lambda **kw: f"### CANLI base={kw.get('base_url_override')}"
CG.load_context_filter = lambda: {"live_app_auth": {"username": "u", "password": "p"}}
SA.live_app_urls = lambda: ["https://dev-ornek.local/app"]
CG._api_cagri = sahte_ai('<giris_sonuc>{"ok": true, "neden": "", "ekran": "/dashboard", "menu": ["Sports", "Markets"]}</giris_sonuc>')
r = SA.giris_testi()
o = SA.oturum_oku()
chk("başarılı: oturum.giris + sistem mesajı", r["ok"] and o["giris"]["ekran"] == "/dashboard" and o["mesajlar"][-1].get("sistem")
    and "başarılı" in o["mesajlar"][-1]["metin"])
chk("giriş testi kapsam surec + önbellek kapalı", yakala["kw"].get("canli_uygulama_kapsami") == "surec" and yakala["kw"].get("onbellek") is False)
CG._api_cagri = sahte_ai('<giris_sonuc>{"ok": false, "neden": "Wrong Password !!!"}</giris_sonuc>')
r = SA.giris_testi()
chk("reddedildi: neden aynen + yönlendirme", not r["ok"] and r["neden"] == "Wrong Password !!!" and "Bağlam Filtresi" in SA.oturum_oku()["mesajlar"][-1]["metin"])
CG._api_cagri = sahte_ai("tarayıcı açılmadı")
chk("bozuk çıktı → ok=False, net neden", not SA.giris_testi()["ok"])
chk("sonuç imzalı önbelleğe yazıldı (Task kapısı da okur)", (tmp / ".giris-durum-surec.json").exists() and CG.durum("surec")["giris"] is not None)
CG.live_app_urls = lambda: []
SA.live_app_urls = lambda: []
CG._api_cagri = lambda *a, **k: (_ for _ in ()).throw(AssertionError("AI çağrılmamalı"))
chk("URL yoksa AI çağrılmaz", not SA.giris_testi()["ok"] and "tanımlı değil" in SA.oturum_oku()["giris"]["neden"])

print("4) ekran envanteri + ekran görevleri")
SA.live_app_urls = lambda: ["https://dev-ornek.local/app"]
SA._api_cagri = sahte_ai('<ekranlar>[{"ad":"Sports","menu":"Sport Basic Data › Sports","ister":"Export CSV/Excel eklenecek","brd_ref":"BRD §4.1"},'
                         '{"ad":"Groups","menu":"Sport Basic Data › Groups","ister":"Export","not":"tournament_group"},{"ad":""},"çöp"]</ekranlar>')
ek = SA.ekran_listesi_cikar()
chk("2 geçerli ekran, boş/çöp atıldı", [e["ad"] for e in ek] == ["Sports", "Groups"], ek)
chk("oturuma yazıldı + sistem mesajı", SA.oturum_oku()["ekranlar"] == ek and "Ekran envanteri" in SA.oturum_oku()["mesajlar"][-1]["metin"])
ad = SA.ekran_gorevleri([1, 0, 7])
chk("seçilen ekranlar → fe-be-ayir adımları (geçersiz index atlanır)", [a["key"] for a in ad] == ["EKRAN-2", "EKRAN-1"] and all(a["mode"] == "fe-be-ayir" for a in ad), ad)
chk("görev: başlık menü › ad, açıklama ister + cevaplar + sohbet, canlı hedef", ad[1]["gorev"]["summary"] == "Sport Basic Data › Sports"
    and "Export CSV/Excel" in ad[1]["gorev"]["description"] and "CSV ve Excel ikisi de" in ad[1]["gorev"]["description"]
    and "Sports ekranı" in ad[1]["canli_hedef"])
try:
    SA.ekran_gorevleri([99])
    chk("geçerli ekran yoksa ValueError", False)
except ValueError:
    chk("geçerli ekran yoksa ValueError", True)

print("5) app")
import app as A  # noqa: E402
A._kimlik_tam_mi = lambda *a, **k: True
c = A.app.test_client()
H = {"Origin": "http://localhost"}
chk("ekran-gorevleri secilen yok → 400", c.post("/api/sohbet/ekran-gorevleri", json={}, headers=H).status_code == 400)
chk("mesaj gözlem: boş metin → 400", c.post("/api/sohbet/mesaj", json={"metin": "", "gozlem": True}, headers=H).status_code == 400)
A._jira_baglanti_eksik = lambda: "Jira bağlı değil"
A._gorev_is_calistir = lambda job_id: None   # işi çalıştırma (test)
r = c.post("/api/jira/gorev/is/baslat", json={"adimlar": ad}, headers=H).get_json()
chk("tüm adımlar görev dict'li → Jira bağlantısı şart değil, canli_hedef taşındı", r.get("ok")
    and A._gorev_isler[r["job"]]["adimlar"][0].get("canli_hedef", "").startswith("Sport Basic Data"), r)
chk("görev dict'siz adım → Jira kontrolü", c.post("/api/jira/gorev/is/baslat", json={"adimlar": [{"key": "MBSTRADE-1"}]}, headers=H).status_code == 400)
cagri = []
A._ornek_yakala_md = lambda *a, **k: cagri.append(a)
import skills.gorev_deposu as GD  # noqa: E402
GD.kaydet = lambda *a, **k: cagri.append(("depo", a))
A._gorev_egitim_topla("EKRAN-1", "Sports", "", "analiz", {"markdown": "x" * 500})
chk("sentetik EKRAN- eğitim/depoya girmez", cagri == [])
from skills import jira_gorevleri as JG  # noqa: E402
src = Path(JG.__file__).read_text(encoding="utf-8")
chk("yeni task: sentetik kaynak anahtarı bağ kurmaz", 'if kaynak_key and not _ID_DESENI.match(kaynak_key):' in src)
chk("oturum özeti giris + ekranlar alanları", {"giris", "ekranlar"} <= set(A._sohbet_ozet({"mesajlar": []}).keys()))

print()
if _hata:
    print(f"SOHBET EKRAN TESTLERİ BAŞARISIZ ({_hata} hata)")
    sys.exit(1)
print("SOHBET EKRAN TESTLERİ GEÇTİ")
