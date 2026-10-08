"""Değişiklik Etkisi + Süreç/Ekran Bütünlüğü + Zorunlu Soru — offline, 0 token (AI MOCK).

Kapsam:
  1. Sinyal tespiti (zorunluluk/silme/kaldırma/pasif/güncelleme) + negatif
  2. Değişen öğe adayları (tırnaklı ad, 'X alanı', camelCase)
  3. Tüketici taraması (geçici referans dizini: Swagger $ref alanı, Confluence, Jira) + aday dağılımı
  4. Prompt bloğu (hedefe göre yerleşim, hata modunda tablo yok, sinyalsizse boş)
  5. Akış bütünlük denetimi (akışa bağlanmamış dal/ekran/kural, tanımsız referans)
  6. Zorunlu soru parse + istatistik; few-shot temizliği
  7. prompt_yukle bütünlük kuralları (override'da da)
  8. Motor bağlantısı: süreç / teknik / görev analizi bloğu prompta koyuyor (AI MOCK)
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("BILDIRIM", "false")

from skills import degisiklik_etkisi as DE  # noqa: E402
from skills import base  # noqa: E402

_hata = 0


def chk(ad, kosul, ek=""):
    global _hata
    if not kosul:
        _hata += 1
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if ek and not kosul else ""))


METIN = ('Oyuncu ekleme ekranında "Doğum Tarihi" alanı artık zorunlu olmayacak. '
         "Pasif kategoriler silinebilecek. Ekrandaki taxNumber alanı kaldırılacak. "
         "Kategori kaydı İSTEĞE BAĞLI hale getirilecek. Kayıt pasife alınabilir.")

print("1) sinyaller")
tipler = {s["tip"] for s in DE.sinyaller(METIN)}
for t in ("zorunluluk", "silme", "kaldirma", "pasif"):
    chk(f"{t} yakalandı", t in tipler, tipler)
chk("nötr metinde sinyal yok", DE.sinyaller("Kullanıcı listeyi görüntüler ve filtreler.") == [])
chk("güncelleme yakalandı", any(s["tip"] == "guncelleme" for s in DE.sinyaller("Limit değeri güncellenecek.")))

print("2) adaylar")
ad = DE.degisen_adaylari(METIN)
chk("tırnaklı ad", "Doğum Tarihi" in ad, ad)
chk("camelCase", "taxNumber" in ad, ad)
chk("durak kelime yok", not any(a.lower() in ("bu", "ilgili", "ekrandaki") for a in ad), ad)

print("3) tüketici taraması (geçici referans dizini)")
ref = Path(tempfile.mkdtemp())
(ref / "services").mkdir()
(ref / "confluence").mkdir()
(ref / "jira").mkdir()
(ref / "services" / "musteri-bff.json").write_text(json.dumps({
    "openapi": "3.0.0",
    "paths": {
        "/musteri/{id}": {"get": {"summary": "Müşteri detay",
                                  "responses": {"200": {"content": {"application/json": {
                                      "schema": {"$ref": "#/components/schemas/Musteri"}}}}}}},
        "/rapor": {"get": {"parameters": [{"name": "tax_number", "in": "query"}], "responses": {}}},
        "/diger": {"get": {"responses": {}}},
    },
    "components": {"schemas": {"Musteri": {"properties": {"taxNumber": {"type": "string"},
                                                          "adres": {"$ref": "#/components/schemas/Adres"}}},
                               "Adres": {"properties": {"il": {"type": "string"}}}}},
}), encoding="utf-8")
(ref / "confluence" / "Fatura-Ekrani.md").write_text("# Fatura\nDoğum Tarihi bilgisi faturada basılır.\n", encoding="utf-8")
for i in range(6):
    (ref / "confluence" / f"bos-{i}.md").write_text("ilgisiz içerik", encoding="utf-8")
(ref / "jira" / "PRJ.json").write_text(json.dumps([
    {"key": "PRJ-7", "summary": "Doğum Tarihi raporu", "description": "", "status": "Done"},
    {"key": "PRJ-8", "summary": "başka", "description": "", "status": "Done"},
] + [{"key": f"PRJ-{i}", "summary": "x", "description": ""} for i in range(10, 30)]), encoding="utf-8")
tk = DE.tuketici_tara(["Doğum Tarihi", "taxNumber"], ref)
nereler = {(t["kaynak"], t["nerede"]) for t in tk}
chk("Swagger yanıt alanı ($ref çözümü)", ("Swagger:musteri-bff.json", "GET /musteri/{id}") in nereler, nereler)
chk("Swagger parametre (tax_number ~ taxNumber)", ("Swagger:musteri-bff.json", "GET /rapor") in nereler, nereler)
chk("ilgisiz endpoint yok", not any(n == "GET /diger" for _, n in nereler))
chk("Confluence sayfası", any(t["kaynak"] == "Confluence:Fatura-Ekrani" for t in tk), tk)
chk("Jira task", any(t["kaynak"] == "Jira:PRJ-7" for t in tk), tk)
# Dağılım: çok isabetli tek aday bütçeyi tekeline almaz
DE._MAX_TUKETICI, _eski = 3, DE._MAX_TUKETICI
tk2 = DE.tuketici_tara(["Doğum Tarihi", "taxNumber"], ref)
DE._MAX_TUKETICI = _eski
chk("adaylar arasında sırayla dağıtım", {t["aday"] for t in tk2} == {"Doğum Tarihi", "taxNumber"}, tk2)

print("4) prompt bloğu")
b = DE.degisiklik_blogu(METIN, "surec", ref)
chk("başlık + tablo + tüketiciler", "DEĞİŞİKLİK ETKİSİ" in b and "| Değişen Öğe |" in b and "Olası Tüketiciler" in b)
chk("süreçte AYRI bölüm açtırmaz (mevcut Etki Analizi'ne)", "AYRI bölüm AÇMA" in b and "Etki Analizi" in b)
bg = DE.degisiklik_blogu("Limit değeri güncellenecek.", "surec", ref)
chk("yalnız güncelleme → kompakt (tablo yok)", bg and "| Değişen Öğe |" not in bg and "tablo AÇMA" in bg, bg[:200])
chk("zorunlu soru kuralı", "Zorunlu: Evet" in b)
chk("teknik yerleşimi (§4 DB)", "§4" in DE.degisiklik_blogu(METIN, "teknik", ref))
bh = DE.degisiklik_blogu(METIN, "gorev_hata", ref)
chk("hata modunda tablo yok + Etki maddesi", "| Değişen Öğe |" not in bh and "Etki:" in bh)
chk("sinyalsiz → boş", DE.degisiklik_blogu("Liste ekranı açılır.", "surec", ref) == "")

print("5) akış bütünlük denetimi")
analiz = ("### İş Gereksinimleri\n| BR-001 | x | y |\n| BR-002 | x | y |\n| BR-003 | x | y |\n\n"
          "### Ekranlar\n**EK-001** · Bağlı adım: PA-001\n**EK-002** · yeni ekran\n\n"
          "### Süreç Adımları\n**PA-001:** kaydet · Bağlı kural: BR-001 → AF-001\n"
          "**PA-002:** onay · kurallar BR-002–BR-003 · → EF-009\n"
          "**AF-001:** iptal\n**AF-002:** hiçbir yerden bağlanmayan dal\n**EF-001:** hata\n\n"
          "### Açık Sorular\n### Q-001: x\n- Bağlı ID: AF-002, EF-001, EK-002\n")
d = base.akis_butunluk_denetimi(analiz)
chk("bağlanmamış AF-002 / EF-001 / EK-002", all(f"| {i} |" in d for i in ("AF-002", "EF-001", "EK-002")), d)
chk("Açık Sorular'daki atıf akışa bağlamış sayılmaz", "| AF-002 |" in d)
chk("tanımsız referans EF-009", "| EF-009 |" in d and "tanımı yok" in d)
chk("bağlı öğeler raporlanmaz (AF-001, EK-001, BR-001)", not any(f"| {i} |" in d for i in ("AF-001", "EK-001", "BR-001")), d)
chk("aralık (BR-002–BR-003) referans sayılır", "| BR-003 |" not in d and "| BR-002 |" not in d, d)
chk("temiz akışta boş", base.akis_butunluk_denetimi("**PA-001:** x → AF-001\n**AF-001:** y\n") == "")
chk("ID yoksa boş", base.akis_butunluk_denetimi("düz metin") == "")

print("6) zorunlu soru parse + istatistik + few-shot temizliği")
from skills import sorular as SQ  # noqa: E402
qmd = Path(tempfile.mkdtemp()) / "acik-sorular.md"
qmd.write_text("## Açık Sorular\n\n### Q-T-001: Boş değer raporda\n- Öncelik: Kritik\n- Zorunlu: Evet\n"
               "- Soru: Rapor boş değeri nasıl gösterir?\n\n### Q-T-002: Renk\n- Öncelik: Düşük\n- Soru: Renk?\n",
               encoding="utf-8")
ps = {s["id"]: s for s in SQ.parse_md_sorular(qmd)}
chk("Zorunlu: Evet → True", ps.get("Q-T-001", {}).get("zorunlu") is True, ps)
chk("alan yok → False", ps.get("Q-T-002", {}).get("zorunlu") is False)
chk("varyantlar", SQ.zorunlu_mu("**Evet** (veri kaybı)") and SQ.zorunlu_mu("Yes") and not SQ.zorunlu_mu("Hayır"))
ist = SQ.istatistik_hesapla([dict(ps["Q-T-001"], durum="acik"), dict(ps["Q-T-002"], durum="acik"),
                             dict(ps["Q-T-001"], durum="cevaplandi")])
chk("zorunlu_acik yalnız açık olanı sayar", ist.get("zorunlu_acik") == 1, ist)
from skills import ornek_havuzu as OH  # noqa: E402
tem = OH._temizle("## Çözüm\nyap\n\n## ❗ Cevap Bekleyen Zorunlu Sorular\n- **Q-T-1:** x\n\n## Kabul\nAC-1\n")
chk("few-shot'tan zorunlu soru bölümü çıkarıldı", "Cevap Bekleyen" not in tem and "## Kabul" in tem, tem)

print("7) prompt_yukle — bütünlük kuralları")
for sid in ("surec_analizi", "teknik_analiz_bolumler", "gorev_teknik_analiz"):
    _p = base.prompt_yukle(sid)
    chk(f"{sid} içeriyor", "Süreç ve Ekran Bütünlüğü" in _p and "Zorunlu Açık Soru" in _p)
chk("analizi büyütme ilkesi + kontrol listesi yasağı", "BÜYÜTMEK değil" in base._BUTUNLUK_KURALLARI
    and "ayrı bölüm" in base._BUTUNLUK_KURALLARI)
chk("ilgisiz skill içermiyor", "Süreç ve Ekran Bütünlüğü" not in base.prompt_yukle("test_senaryolari"))
_eski_pp = base.PROMPTS_PATH
base.PROMPTS_PATH = Path(tempfile.mkdtemp()) / "prompts.json"
base.PROMPTS_PATH.write_text(json.dumps({"gorev_teknik_analiz": "OZEL PROMPT"}), encoding="utf-8")
p_ov = base.prompt_yukle("gorev_teknik_analiz")
base.PROMPTS_PATH = _eski_pp
chk("prompts.json override'ında da korunur", p_ov.startswith("OZEL PROMPT") and "Süreç ve Ekran Bütünlüğü" in p_ov)

print("8) motor bağlantısı (AI MOCK)")
from skills import surec_analizi as SA  # noqa: E402
from skills import teknik_analiz as TA  # noqa: E402
from skills import jira_gorevleri as JG  # noqa: E402
yakala: dict = {}


def _sahte_api(sistem, mesajlar, *a, **k):
    yakala["sistem"] = sistem
    yakala["metin"] = "\n".join(p.get("text", "") for p in mesajlar[0]["content"] if isinstance(p, dict))
    return ("<teknik_analiz>## 1. Amaç\nx\n</teknik_analiz>" if "teknik" in yakala.get("mod", "")
            else "### İş Gereksinimleri\n| BR-001 | x |\n**AF-001:** bağlanmamış dal\n")


kaydedilen: dict = {}
SA._api_cagri = _sahte_api
SA.referans_dosyalari_hazirla = lambda *a, **k: []
SA.canli_uygulama_baglami_hazirla = lambda *a, **k: ""
SA._kaydet = lambda ad, icerik: kaydedilen.update({ad: icerik}) or Path(ad)
SA.yonetici_ozeti_olustur = lambda *a, **k: ""
SA.surec_analizi_yap(icerik_override=[{"type": "text", "text": METIN}], ozel_atla=True)
chk("süreç: blok prompta girdi", "DEĞİŞİKLİK ETKİSİ" in yakala.get("metin", ""))
chk("süreç: bütünlük kuralları sistemde", "Süreç ve Ekran Bütünlüğü" in yakala.get("sistem", ""))
chk("süreç: akış bütünlük denetimi eklendi", "Akış Bütünlük Denetimi" in kaydedilen.get("surec-analizi.md", ""))
yakala.clear()
SA.surec_analizi_yap(icerik_override=[{"type": "text", "text": "Liste ekranı açılır."}], ozel_atla=True)
chk("süreç: sinyalsiz girdide blok yok", "DEĞİŞİKLİK ETKİSİ" not in yakala.get("metin", "x"))

# Teknik: yalnız Aşama-1 mesajını yakala, sonra dur (sonraki adımlar kapsam dışı)
class _Dur(Exception):
    pass


def _teknik_sahte(sistem, mesajlar, **k):
    yakala["sistem"] = sistem
    yakala["metin"] = "\n".join(p.get("text", "") for p in mesajlar[0]["content"] if isinstance(p, dict))
    raise _Dur()


_tmp_out = Path(tempfile.mkdtemp())
(_tmp_out / "surec-analizi.md").write_text("## Süreç\n" + METIN, encoding="utf-8")
TA.OUTPUT_DIR = _tmp_out
TA.referans_dosyalari_hazirla = lambda *a, **k: []
TA.canli_uygulama_baglami_hazirla = lambda *a, **k: ""
TA.mockup_oku_kontekst = lambda *a, **k: ""
TA._teknik_uret_tam = _teknik_sahte
yakala.clear()
try:
    TA.teknik_analiz_yap(ozel_atla=True)
except _Dur:
    pass
chk("teknik: blok prompta girdi (§4 yerleşimi)", "DEĞİŞİKLİK ETKİSİ" in yakala.get("metin", "")
    and "§4" in yakala.get("metin", ""))
chk("teknik: zorunlu soru kuralı açık soru adımında", "Zorunlu: Evet" in TA._acik_sorular_prompt_olustur())

JG._api_cagri = _sahte_api
JG.referans_dosyalari_hazirla = lambda *a, **k: []
JG.canli_uygulama_baglami_hazirla = lambda *a, **k: ""
JG._gorev_acik_sorular_uret = lambda *a, **k: ""
JG.load_context_filter = lambda *a, **k: {}
yakala.clear()
yakala["mod"] = "teknik"
JG.gorev_analiz_et({"key": "PRJ-1", "summary": "Doğum tarihi zorunluluğu kaldırılsın",
                    "description": '"Doğum Tarihi" alanı zorunlu olmayacak.', "issuetype": "Story"})
chk("görev: blok + tablo prompta girdi", "DEĞİŞİKLİK ETKİSİ" in yakala.get("metin", "")
    and "| Değişen Öğe |" in yakala.get("metin", ""))
yakala.clear()
yakala["mod"] = "teknik"
JG.gorev_analiz_et({"key": "PRJ-2", "summary": "Hata: kayıt silinemiyor",
                    "description": "Kategori silinmek istendiğinde hata veriyor.", "issuetype": "Bug"})
chk("görev (bug): kısa Etki modu, tablo yok", "Etki:" in yakala.get("metin", "")
    and "| Değişen Öğe |" not in yakala.get("metin", ""))

print()
if _hata:
    print(f"DEĞİŞİKLİK ETKİSİ TESTLERİ BAŞARISIZ ({_hata} hata)")
    sys.exit(1)
print("DEĞİŞİKLİK ETKİSİ TESTLERİ GEÇTİ")
