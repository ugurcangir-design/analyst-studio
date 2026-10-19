"""Kabul Kontrolü — offline, 0 token (AI enjekte, Jira MOCK).

Kapsam:
  1. Liste çıkarımı: normalize (id/tur/denenebilir), ≤25, boş madde atılır, bozuk JSON → []
  2. Karar: ≥1 eksik → geri · hepsi doğrulandı → teste_hazir · doğrulandı+doğrulanamadı → kısmi ·
     agent sonuç bildirmedi → dogrulanamadi (tahmin yok) · ekran dışı madde denenmez
  3. Canlı hedef yoksa hata fırlatmaz, net neden
  4. Rapor markdown: sonuç etiketi, tablo, geri dönecek maddeler, yazma işlemleri, durum notu
  5. Köprü: `kontrol` + eş anlamlılar eşlenir, yardım metninde var · app iş modu + yorum ucu doğrulama
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("BILDIRIM", "false")

from skills import kabul_kontrolu as KK  # noqa: E402

_hata = 0


def chk(ad, kosul, ek=""):
    global _hata
    if not kosul:
        _hata += 1
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if ek and not kosul else ""))


def _yasak(*a, **k):
    raise AssertionError("Gerçek AI çağrısı yapıldı!")


KK._api_cagri = _yasak
_ORJ_CANLI_HEDEF = KK._canli_hedef   # bölüm 6 gerçek fonksiyonu test eder
_ORJ_LISTE = KK.kabul_listesi_cikar
GOREV = {"key": "MBSTRADE-1", "summary": "Kategori ekleme", "description": "## 11. Kabul Kriterleri\nAC-1 Name boş → hata\nAC-2 Save → POST /api/categories 201"}

print("1) liste çıkarımı")
LISTE = ('<kabul_listesi>[{"id":"K-01","tur":"validasyon","madde":"Name boş → hata","nasil":"Name boş, Save","beklenen":"\'Kategori adı zorunludur\'","ref":"AC-1"},'
         '{"id":"K-02","tur":"servis","madde":"Save → POST /api/categories","beklenen":"201","ref":"AC-2","denenebilir":true},'
         '{"id":"K-03","tur":"veri","madde":"Gece job\'u kategoriyi senkronlar","denenebilir":false},'
         '{"madde":""},"çöp"]</kabul_listesi>')
maddeler = KK.kabul_listesi_cikar(GOREV, _ai=lambda s, m: LISTE)
chk("3 geçerli madde, boş/çöp atıldı", [m["id"] for m in maddeler] == ["K-01", "K-02", "K-03"], maddeler)
chk("denenebilir bayrağı", maddeler[2]["denenebilir"] is False and maddeler[0]["denenebilir"] is True)
chk("bozuk JSON → []", KK.kabul_listesi_cikar(GOREV, _ai=lambda s, m: "<kabul_listesi>yok</kabul_listesi>") == [])
cok = "<kabul_listesi>[" + ",".join(f'{{"id":"K-{i:02d}","madde":"m{i}"}}' for i in range(40)) + "]</kabul_listesi>"
chk("en fazla 25", len(KK.kabul_listesi_cikar(GOREV, _ai=lambda s, m: cok)) == 25)

print("2) karar mantığı")
KK._canli_hedef = lambda g, t="": "### CANLI GÖREV (mock)"
yakala = {}


def ai_sonuc(js):
    def f(s, m):
        yakala["metin"] = "\n".join(p.get("text", "") for p in m[0]["content"])
        return f"<kabul_sonuc>{js}</kabul_sonuc>"
    return f


r = KK.canli_dogrula(GOREV, maddeler, _ai=ai_sonuc(
    '{"maddeler":[{"id":"K-01","durum":"dogrulandi","gozlem":"mesaj çıktı","kanit":"[K: Canlı UI:/categories]"},'
    '{"id":"K-02","durum":"eksik","gozlem":"POST 500 döndü","kanit":"[K: Network:POST /api/categories → 500]"}],'
    '"yazma_islemleri":["AI-TEST Kat 1 oluşturuldu"],"genel_not":"n"}'))
chk("bir eksik → GERİ", r["sonuc"] == "geri" and r["sayim"] == {"dogrulandi": 1, "eksik": 1, "dogrulanamadi": 0, "ekran_disi": 1}, r["sayim"])
chk("ekran dışı madde denenmedi (talimatta yok)", "K-03" not in yakala["metin"] and "K-02" in yakala["metin"])
chk("talimat: AI-TEST + doğrulama görevi + çıktı biçimi", "AI-TEST" in yakala["metin"] and "KABUL KONTROLÜ GÖREVİ" in yakala["metin"]
    and "<kabul_sonuc>" in yakala["metin"])
r = KK.canli_dogrula(GOREV, maddeler, _ai=ai_sonuc(
    '{"maddeler":[{"id":"K-01","durum":"dogrulandi","kanit":"x"},{"id":"K-02","durum":"dogrulandi","kanit":"y"}]}'))
chk("hepsi doğrulandı → TESTE HAZIR", r["sonuc"] == "teste_hazir")
r = KK.canli_dogrula(GOREV, maddeler, _ai=ai_sonuc('{"maddeler":[{"id":"K-01","durum":"dogrulandi","kanit":"x"}]}'))
chk("agent K-02 için sonuç bildirmedi → doğrulanamadı (tahmin yok) → kısmi", r["sonuc"] == "teste_hazir_kismi"
    and r["maddeler"][1]["durum"] == "dogrulanamadi" and "bildirmedi" in r["maddeler"][1]["neden"], r["maddeler"][1])
r = KK.canli_dogrula(GOREV, maddeler, _ai=ai_sonuc('{"maddeler":[{"id":"K-01","durum":"belki"},{"id":"K-02","durum":"dogrulanamadi","neden":"ekran yok"}]}'))
chk("geçersiz durum → doğrulanamadı; hiç doğrulanan yok → DOĞRULANAMADI", r["sonuc"] == "dogrulanamadi"
    and r["maddeler"][0]["durum"] == "dogrulanamadi")
r = KK.canli_dogrula(GOREV, maddeler, _ai=lambda s, m: "bozuk çıktı")
chk("bozuk agent çıktısı → tümü doğrulanamadı, hata yok", r["sonuc"] == "dogrulanamadi" and r["sayim"]["dogrulanamadi"] == 2)

print("3) canlı hedef yok")
KK._canli_hedef = lambda g, t="": None
r = KK.canli_dogrula(GOREV, maddeler, _ai=_yasak)
chk("AI çağrılmaz, net neden", r["sonuc"] == "dogrulanamadi" and "hedefi tanımlı değil" in r["maddeler"][0]["neden"], r["maddeler"][0])

print("4) rapor")
KK._canli_hedef = lambda g, t="": "mock"
r = KK.canli_dogrula(GOREV, maddeler, _ai=ai_sonuc(
    '{"maddeler":[{"id":"K-01","durum":"dogrulandi","gozlem":"ok","kanit":"[K: Canlı UI:/c]"},{"id":"K-02","durum":"eksik","gozlem":"500"}],'
    '"yazma_islemleri":["AI-TEST Kat 1"],"gezilemeyen":["Rapor ekranı — menüde yok"]}'))
md = KK.rapor_md(GOREV, r)
chk("rapor: etiket + tablo + geri maddeleri + yazma + gezilemeyen + durum notu",
    "GELİŞTİRMEYE GERİ" in md and "| AC-1 | K-01 ·" in md and "### Geliştirmeye dönecek maddeler" in md and "**K-02**" in md
    and "AI-TEST Kat 1" in md and "Rapor ekranı" in md and "Durum değiştirilmedi" in md, md[:300])
chk("ekran dışı madde raporda ◻", "◻ ekran disi" in md or "◻" in md)
KK.kabul_listesi_cikar = lambda g, _ai=None, talimat="": []
t = KK.kabul_kontrolu(GOREV)
chk("madde çıkmazsa DOĞRULANAMADI + açıklama", t["sonuc"] == "dogrulanamadi" and "çıkarılamadı" in t["markdown"])

print("5) köprü + app")
from skills import jira_kopru as JK  # noqa: E402
for k in ("kontrol", "kabul", "doğrula", "verify"):
    chk(f"'{k}' → kontrol", (JK._komut_coz(f"/analyst_agent {k}", "/analyst_agent") or ("",))[0] == "kontrol")
chk("yardım metninde kontrol", "kontrol" in JK._yardim_metni("/analyst_agent") and "Kabul Kontrolü" in JK._yardim_metni("/analyst_agent"))
JK.gorev_getir = lambda key: None
chk("görev okunamazsa net mesaj", "okunamadı" in JK._kontrol_islet("X-1"))
import app as A  # noqa: E402
src = Path(A.__file__).read_text(encoding="utf-8")
chk("app: iş modu kabul-kontrol + eğitim toplamaz", 'mode == "kabul-kontrol"' in src and 'if mode != "kabul-kontrol":' in src)
c = A.app.test_client()
A._kimlik_tam_mi = lambda *a, **k: True
chk("kabul-yorum: eksik gövde 400", c.post("/api/jira/gorev/kabul-yorum", json={"key": "X-1"}, headers={"Origin": "http://localhost"}).status_code == 400)

print("6) analist formatı — kriter bazlı rapor + talimat + ilgili task + köprü arg")
GOREV2 = {"key": "MBSTRADE-10", "summary": "Closed Combination Groups", "description": "## 11. Kabul Kriterleri\nAC-1 …\nAC-2 …\nAC-3 …",
          "baglantililar": [{"key": "MBSTRADE-11", "summary": "FE ekranı", "katman": "fe", "iliski": "relates to"}]}
M2 = KK._liste_normalize([
    {"id": "K-01", "tur": "servis", "madde": "Silme 409", "ref": "AC-1"},
    {"id": "K-02", "tur": "servis", "madde": "Atama kaldır", "ref": "AC-1"},
    {"id": "K-03", "tur": "veri", "madde": "sport alanı dolu", "ref": "§5 AC-2"},
    {"id": "K-04", "tur": "rol", "madde": "yetkisiz kullanıcı", "ref": "AC-3", "denenebilir": False},
    {"id": "K-05", "tur": "buton", "madde": "ref'siz madde"},
])
KK._canli_hedef = lambda g, t="": "mock"
r = KK.canli_dogrula(GOREV2, M2, talimat="https://dev-ornek.local/app/groups — BE kriterlerini endpoint'ten doğrula", _ai=ai_sonuc(
    '{"maddeler":[{"id":"K-01","durum":"dogrulandi","kanit":"[K: Network:DELETE /g/1 → 409]"},{"id":"K-02","durum":"dogrulandi","kanit":"x"},'
    '{"id":"K-03","durum":"dogrulanamadi","neden":"detay servisi yanıtı görülemedi"},{"id":"K-05","durum":"dogrulandi","kanit":"y"}],'
    '"bulgular":["Market atanmış grubun silinmesi HTTP 409 ile engelleniyor"],"acik_konular":["Grup detay yanıtında sport alanı","Yetki davranışı"],'
    '"genel_not":"Kapsamın büyük bölümü doğrulandı."}'))
kr = {k["kriter"]: k["durum"] for k in r["kriterler"]}
chk("kriter toplama: AC-1 (2 madde ✓) dogrulandi · AC-2 (§5 AC-2) dogrulanamadi · AC-3 ekran dışı · ref'siz kendi kriteri",
    kr == {"AC-1": "dogrulandi", "AC-2": "dogrulanamadi", "AC-3": "ekran_disi", "K-05": "dogrulandi"}, kr)
chk("kriter sayımı", r["kriter_sayim"] == {"dogrulandi": 2, "eksik": 0, "dogrulanamadi": 1, "ekran_disi": 1}, r["kriter_sayim"])
chk("bulgular + açık konular normalize", r["bulgular"] == ["Market atanmış grubun silinmesi HTTP 409 ile engelleniyor"] and len(r["acik_konular"]) == 2)
chk("talimat: kontrol talimatına + çıktı biçimine girer (BE endpoint kuralı, GET/POST/PUT/DELETE, TEK çıktı)",
    "ANALİST TALİMATI" in yakala["metin"] and "BE kriterlerini endpoint'ten" in yakala["metin"] and "GET/POST/PUT/DELETE" in yakala["metin"]
    and "TEK çıktı" in yakala["metin"] and '"bulgular"' in yakala["metin"] and '"acik_konular"' in yakala["metin"])
md = KK.rapor_md(GOREV2, r, ortam="DEV (dev-ornek.local)")
chk("rapor başlık bloğu: Task · Konu · Ortam · İlgili task (FE)", "**Task:** MBSTRADE-10" in md and "**Ortam:** DEV (dev-ornek.local)" in md
    and "MBSTRADE-11 (FE)" in md)
chk("Doğrulama Sonucu kriter sayıları", "- Toplam kabul kriteri: 4" in md and "- Karşılanan: 2" in md and "- Doğrulanamayan: 1 (AC-2)" in md
    and "- Netleştirilmesi gereken konu: 2" in md, md[:600])
chk("Genel değerlendirme + Öne çıkan bulgular + Netleştirilmesi gereken konular", "**Genel değerlendirme:** Kapsamın" in md
    and "### Öne çıkan bulgular" in md and "HTTP 409" in md and "### Netleştirilmesi gereken konular" in md)
chk("Sonuç cümlesi: karşılanan + doğrulanamayan kapsam uyarısı", "**Sonuç:** 2 kabul kriteri karşılanmıştır. AC-2 ile doğrulanamayan senaryolar tamamlanmadan tüm kapsamın doğrulandığı kabul edilmemelidir." in md, md[-400:])
chk("kriter tablosu: kriter sütunu", "| AC-2 | K-03 · sport alanı dolu | ⚠" in md)
# talimat URL → doğrudan ekran; yoksa bağlam filtresi base
KK.load_context_filter = lambda: {"live_app_gorev": {"target_url": "https://uat-ornek.local/app/x/y"}}
chk("_hedef_url: talimat URL'i öncelikli, yoksa live_app_gorev", KK._hedef_url("bak: https://dev-ornek.local/app/groups.") == "https://dev-ornek.local/app/groups"
    and KK._hedef_url("") == "https://uat-ornek.local/app/x/y")
chk("_ortam_adi: DEV/UAT sınıfı + host", KK._ortam_adi("https://dev-ornek.local/a") == "DEV (dev-ornek.local)" and KK._ortam_adi("https://uat-ornek.local/a").startswith("UAT"))
yak2: dict = {}
KK.canli_uygulama_baglami_hazirla = lambda **kw: (yak2.update(kw) or "CANLI")
_ORJ_CANLI_HEDEF(GOREV2, "https://dev-ornek.local/app/groups odak: silme")
chk("talimat URL'i varsa base_url_override = o ekran; hedef tarifi ilgili task + talimat içerir",
    yak2.get("base_url_override") == "https://dev-ornek.local/app/groups" and "MBSTRADE-11" in yak2.get("hedef_tarif", "")
    and "Analist talimatı: https://dev-ornek.local/app/groups odak: silme" in yak2.get("hedef_tarif", ""), yak2)
_ORJ_CANLI_HEDEF(GOREV2, "")
chk("talimat yoksa bağlam filtresi ANA adresi (base)", yak2.get("base_url_override") == "https://uat-ornek.local")
# liste çıkarımı: ilgili task + talimat prompta girer; AC birincil kuralı sistemde
yak3: dict = {}
_ORJ_LISTE(GOREV2, _ai=lambda s, m: (yak3.update({"s": s, "m": "\n".join(p["text"] for p in m[0]["content"])}) or "<kabul_listesi>[]</kabul_listesi>"),
                       talimat="https://dev-ornek.local/app/groups")
chk("liste promptu: ilgili task + analist talimatı + AC birincil + BE endpoint kuralı", "MBSTRADE-11" in yak3["m"] and "Analist talimatı" in yak3["m"]
    and "KABUL KRİTERLERİ BİRİNCİLDİR" in yak3["s"] and "ENDPOINT üzerinden" in yak3["s"])
chk("köprü: kontrol <talimat> argümanı iletilir", "_kontrol_islet(key, arg)" in Path(JK.__file__).read_text(encoding="utf-8"))
src_app = Path(A.__file__).read_text(encoding="utf-8")
chk("app: talimat + kriter_sayim/ortam iş sonucunda", 'kabul_kontrolu(gorev, talimat=adim.get("talimat", ""))' in src_app and '"kriter_sayim": r.get("kriter_sayim"' in src_app)

print("7) listeden doğrudan Kabul Kontrolü (analiz üretmeden)")
ui = Path(A.__file__).parent.joinpath("templates/index.html").read_text(encoding="utf-8")
chk("kartta 'Kabul Kontrolü' düğmesi (ANALIZ CHECK statüsünde vurgulu) + jgKabulKontrolBaslat mode kabul-kontrol, markdown boş",
    "jgKabulKontrolBaslat(" in ui and "_jgKabulDurumuMu(g.status)" in ui and "mode: 'kabul-kontrol', markdown: '', acik_sorular: '', gorev: g, talimat" in ui)
chk("rapor-tek görünüm: kabulOnly → başlık 'Kabul Kontrolü', editörde rapor, Jira yazımı/eğitim/düzelt kapalı",
    "kabulOnly: !!(rs.kabul" in ui and "'Kabul Kontrolü — ' : 'Teknik Analiz — '" in ui and "_kabulOnly ? (s.kabul.markdown || '')" in ui
    and "_sentetik || _kabulOnly" in ui and "Kabul kontrolü raporu eğitim örneği değildir" in ui)

print()
if _hata:
    print(f"KABUL KONTROLÜ TESTLERİ BAŞARISIZ ({_hata} hata)")
    sys.exit(1)
print("KABUL KONTROLÜ TESTLERİ GEÇTİ")
