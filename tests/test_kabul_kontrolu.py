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
KK._canli_hedef = lambda g: "### CANLI GÖREV (mock)"
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
KK._canli_hedef = lambda g: None
r = KK.canli_dogrula(GOREV, maddeler, _ai=_yasak)
chk("AI çağrılmaz, net neden", r["sonuc"] == "dogrulanamadi" and "hedefi tanımlı değil" in r["maddeler"][0]["neden"], r["maddeler"][0])

print("4) rapor")
KK._canli_hedef = lambda g: "mock"
r = KK.canli_dogrula(GOREV, maddeler, _ai=ai_sonuc(
    '{"maddeler":[{"id":"K-01","durum":"dogrulandi","gozlem":"ok","kanit":"[K: Canlı UI:/c]"},{"id":"K-02","durum":"eksik","gozlem":"500"}],'
    '"yazma_islemleri":["AI-TEST Kat 1"],"gezilemeyen":["Rapor ekranı — menüde yok"]}'))
md = KK.rapor_md(GOREV, r)
chk("rapor: etiket + tablo + geri maddeleri + yazma + gezilemeyen + durum notu",
    "GELİŞTİRMEYE GERİ" in md and "| K-01 |" in md and "### Geliştirmeye dönecek maddeler" in md and "**K-02**" in md
    and "AI-TEST Kat 1" in md and "Rapor ekranı" in md and "Durum değiştirilmedi" in md, md[:300])
chk("ekran dışı madde raporda ◻", "◻ ekran disi" in md or "◻" in md)
KK.kabul_listesi_cikar = lambda g, _ai=None: []
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

print()
if _hata:
    print(f"KABUL KONTROLÜ TESTLERİ BAŞARISIZ ({_hata} hata)")
    sys.exit(1)
print("KABUL KONTROLÜ TESTLERİ GEÇTİ")
