"""Akış Kapatma (Faz 3) — offline, 0 token (tespit + düzeltme AI'ı ENJEKTE edilir).

Kapsam:
  1. Çekirdek: düzeltme yalnız hedef bölümü değiştirir · aynı bölümün boşlukları tek çağrı
  2. Korumalar: başlık değişimi / kısalma / fazla büyüme / bölüm bulunamadı → reddedilir, soruya döner
  3. Soru blokları: numara devamı (Q ve Q-T ayrı) · Zorunlu satırı · sorular.py ile parse
  4. Analize ekleme: Açık Sorular sonuna, otomatik denetim bölümlerinden ÖNCE
  5. Dosya akışı: süreç (sorular analizde) + teknik (acik-sorular.md) · tek revizyon → Geri Al · rapor
  6. Kapatma anahtarı (AKIS_KAPATMA=false) · JSON dayanıklılığı · Task (bellek içi)
  7. Motor bağlantısı: süreç/teknik akış kapatmayı çağırır, özel promptta çağırmaz
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("BILDIRIM", "false")
os.environ.pop("AKIS_KAPATMA", None)
os.environ["HIZLI_MOD"] = "false"

from skills import akis_kapatma as AK  # noqa: E402
from skills import revizyon as RV  # noqa: E402

_hata = 0


def chk(ad, kosul, ek=""):
    global _hata
    if not kosul:
        _hata += 1
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if ek and not kosul else ""))


# Gerçek AI'a ASLA gidilmesin — enjekte edilmeyen bir yol çağırırsa test patlasın
def _yasak(*a, **k):
    raise AssertionError("Gerçek AI çağrısı yapıldı!")


AK._api_cagri = _yasak

ANALIZ = """# ÖDEME

### Ekranlar
**EK-001** · Bağlı adım: PA-001
Alanlar: Tutar (zorunlu)

**EK-002** · Bağlı adım: —
İade ekranı.

### Süreç Adımları
**PA-001:** Kullanıcı tutarı girer ve Öde'ye basar → PA-002
**PA-002:** Sistem ödemeyi alır.

### Açık Sorular / Karar Bekleyen Konular

### Q-001: Para birimi
- Öncelik: Orta
- Soru: Hangi para birimi?

---

## 🔗 Akış Bütünlük Denetimi
| EK-002 | Ekran | bağlı değil |
"""


def tespit_sabit(liste):
    return lambda analiz, kaynak, ek, tip: AK._normalize(liste)


cagrilar: list = []


def duzelt_ekle(satir):
    def f(talimatlar, bolum):
        cagrilar.append(talimatlar)
        return bolum.rstrip("\n") + "\n" + satir + "\n"
    return f


print("1) çekirdek düzeltme")
cagrilar.clear()
s = AK.akis_kapat(ANALIZ, tespit_fn := None, _tespit_fn=tespit_sabit([
    {"hedef": "PA-002", "tur": "giris_cikis", "bosluk": "Ödeme sonrası ekran durumu tanımsız",
     "kapatma": "duzelt", "talimat": "PA-002 sonuna: başarı mesajı + sipariş ekranına yönlendirme (kaynak §3)"},
    {"hedef": "PA-001", "tur": "karar_dali", "bosluk": "Tutar boşsa ne olur",
     "kapatma": "duzelt", "talimat": "PA-001'e: tutar boşsa Öde pasif"},
]), _duzelt_fn=duzelt_ekle("**AF-009:** eklenen satır"))
md = s["markdown"]
chk("aynı bölümün iki boşluğu TEK çağrı", len(cagrilar) == 1 and "PA-002" in cagrilar[0] and "PA-001" in cagrilar[0], cagrilar)
chk("yalnız Süreç Adımları bölümü değişti", md.count("AF-009") == 1
    and md.index("AF-009") > md.index("**PA-002:**") and md.index("AF-009") < md.index("### Açık Sorular"))
chk("diğer bölümler aynen", md.split("### Süreç Adımları")[0] == ANALIZ.split("### Süreç Adımları")[0])
chk("rapor: 2 boşluk 2 kapatıldı 0 soru", (s["rapor"]["bosluk"], s["rapor"]["kapatilan"], s["rapor"]["soru"]) == (2, 2, 0), s["rapor"])

print("2) korumalar")
for ad, cikti, beklenen in [
    ("başlık değişti", lambda t, b: "### Başka Başlık\nx\n", "başlık değişti"),
    ("kısalma", lambda t, b: b.splitlines()[0] + "\n", "bölüm kısaldı"),
    ("fazla büyüme", lambda t, b: b + "\n" + "uzun satır " * 400, "fazla büyüdü"),
]:
    s = AK.akis_kapat(ANALIZ, _tespit_fn=tespit_sabit([
        {"hedef": "PA-002", "tur": "etki", "bosluk": "x", "kapatma": "duzelt", "talimat": "y"}]), _duzelt_fn=cikti)
    chk(f"{ad} → reddedildi, soruya döndü", s["markdown"] == ANALIZ and s["rapor"]["soru"] == 1
        and beklenen in s["rapor"]["detay"][0]["neden"], s["rapor"]["detay"])
s = AK.akis_kapat(ANALIZ, _tespit_fn=tespit_sabit([
    {"hedef": "ZZ-999", "tur": "etki", "bosluk": "x", "kapatma": "duzelt", "talimat": "y"}]), _duzelt_fn=_yasak)
chk("bölüm bulunamadı → soru (AI çağrılmaz)", s["rapor"]["soru"] == 1 and "bulunamadı" in s["rapor"]["detay"][0]["neden"])
s = AK.akis_kapat(ANALIZ, _tespit_fn=tespit_sabit([
    {"hedef": "PA-002", "tur": "etki", "bosluk": "x", "kapatma": "duzelt", "talimat": ""}]), _duzelt_fn=_yasak)
chk("talimatsız düzelt → soru", s["rapor"]["soru"] == 1 and s["rapor"]["kapatilan"] == 0)

print("3) soru blokları")
sorular = AK._normalize([{"hedef": "EK-002", "tur": "ekran_eslesme", "bosluk": "İade ekranı hiçbir adıma bağlı değil",
                          "kapatma": "soru", "soru": "İade ekranına hangi adımdan gelinir?", "zorunlu": True},
                         {"hedef": "Ödeme", "tur": "veri_surekliligi", "bosluk": "Durum geçişi", "kapatma": "soru"}])
bl = AK.soru_bloklari(sorular, "Q", ANALIZ + "\nQ-T-050 teknik")
chk("Q numarası devam eder (Q-T sayılmaz)", "### Q-002:" in bl and "### Q-003:" in bl, bl)
chk("zorunlu + bağlı ID yalnız ID'de", "- Zorunlu: Evet" in bl.split("### Q-003")[0] and "Bağlı ID: EK-002" in bl
    and "Bağlı ID: Ödeme" not in bl)
chk("Q-T öneki ayrı sayılır", "### Q-T-051:" in AK.soru_bloklari(sorular[:1], "Q-T", "Q-T-050 Q-007"))

print("4) analize ekleme")
eklendi = AK.sorulari_analize_ekle(ANALIZ, bl)
chk("Açık Sorular sonuna, denetimden ÖNCE", eklendi.index("### Q-002") > eklendi.index("### Q-001")
    and eklendi.index("### Q-002") < eklendi.index("## 🔗 Akış Bütünlük"))
yok = AK.sorulari_analize_ekle("## Analiz\nmetin\n", bl)
chk("Açık Sorular yoksa başlıkla eklenir", "### Açık Sorular" in yok and yok.index("### Açık Sorular") < yok.index("### Q-002"))
from skills import sorular as SQ  # noqa: E402
_t = Path(tempfile.mkdtemp()) / "surec-analizi.md"
_t.write_text(eklendi, encoding="utf-8")
ps = {q["id"]: q for q in SQ.parse_md_sorular(_t)}
chk("sorular.py parse: zorunlu + kategori", ps.get("Q-002", {}).get("zorunlu") is True
    and "Akış Bütünlüğü" in ps.get("Q-002", {}).get("kategori", ""), ps.get("Q-002"))

print("5) dosya akışı + revizyon + rapor")
tmp = Path(tempfile.mkdtemp())
AK.OUTPUT_DIR = tmp
AK.RAPOR_DOSYA = tmp / ".akis-kapatma.json"
RV.REVIZYON_DIR = tmp / "revizyon"
(tmp / "surec-analizi.md").write_text(ANALIZ, encoding="utf-8")
AK._tespit_ai = tespit_sabit([
    {"hedef": "PA-002", "tur": "giris_cikis", "bosluk": "Sonrası tanımsız", "kapatma": "duzelt", "talimat": "ekle"},
    {"hedef": "EK-002", "tur": "ekran_eslesme", "bosluk": "Bağlı değil", "kapatma": "soru", "soru": "Nereden?",
     "zorunlu": True}])
AK._duzelt_ai = duzelt_ekle("**PA-003:** yönlendirme")
r = AK.dosya_akis_kapat("surec-analizi.md", kaynak="doc", tip="surec")
yeni = (tmp / "surec-analizi.md").read_text(encoding="utf-8")
chk("dosya güncellendi (düzeltme + soru)", "**PA-003:** yönlendirme" in yeni and "### Q-002:" in yeni)
chk("rapor kaydedildi + okunur", AK.rapor_oku("surec-analizi.md")["kapatilan"] == 1 and r["zorunlu"] == 1)
chk("eski oturum raporu taze eşikle gizlenir", AK.rapor_oku("surec-analizi.md", taze_esik=r["ts"] + 10) is None)
oz = RV.oturum_yukle("surec-analizi.md")
chk("tek revizyon (onaylı) + Geri Al ile eski içerik", oz and len(oz["versiyonlar"]) == 2
    and RV.versiyon_icerik("surec-analizi.md", oz["versiyonlar"][0]["id"]) == ANALIZ
    and RV.onayli_icerik("surec-analizi.md") == yeni)

(tmp / "teknik-analiz.md").write_text("## 3. Teknik Gereksinimler\n**T-BE-01:** servis\n", encoding="utf-8")
(tmp / "acik-sorular.md").write_text("Açık soru tespit edilmedi.\n", encoding="utf-8")
AK._tespit_ai = tespit_sabit([{"hedef": "T-BE-01", "tur": "karar_dali", "bosluk": "Hata dalı yok",
                               "kapatma": "soru", "soru": "Servis 500 dönerse?", "zorunlu": True}])
AK.dosya_akis_kapat("teknik-analiz.md", kaynak="süreç", tip="teknik", soru_dosya="acik-sorular.md")
sq = (tmp / "acik-sorular.md").read_text(encoding="utf-8")
chk("teknik: soru acik-sorular.md'ye Q-T ile, 'tespit edilmedi' kalktı",
    "### Q-T-001:" in sq and "tespit edilmedi" not in sq, sq)
chk("teknik: analiz dosyası değişmedi (yalnız soru)",
    (tmp / "teknik-analiz.md").read_text(encoding="utf-8") == "## 3. Teknik Gereksinimler\n**T-BE-01:** servis\n")

print("6) anahtar · JSON · Task")
os.environ["AKIS_KAPATMA"] = "false"
chk("AKIS_KAPATMA=false → None", AK.dosya_akis_kapat("surec-analizi.md") is None and not AK.etkin())
os.environ.pop("AKIS_KAPATMA")
AK._tespit_ai = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("ağ"))
chk("tespit hatası → None, dosya bozulmaz", AK.dosya_akis_kapat("surec-analizi.md") is None
    and (tmp / "surec-analizi.md").read_text(encoding="utf-8") == yeni)
chk("JSON: blok + gürültü", len(AK._json_dizi('ön söz <akis_bosluklari>x [{"bosluk":"a"}] y</akis_bosluklari>')) == 1)
chk("JSON: bozuk → []", AK._json_dizi("<akis_bosluklari>yok</akis_bosluklari>") == [])
chk("normalize: en fazla 8 + boş boşluk atılır",
    len(AK._normalize([{"bosluk": str(i)} for i in range(12)] + [{"bosluk": ""}])) == 8)
AK._tespit_ai = tespit_sabit([{"hedef": "Çözüm", "tur": "karar_dali", "bosluk": "Boş liste", "kapatma": "soru",
                               "soru": "Liste boşsa?"}])
g = AK.gorev_akis_kapat("## Çözüm\nyap\n", "Açık soru tespit edilmedi.", {"key": "PRJ-1", "summary": "s"})
chk("Task: soru Q-T-001 olarak eklenir, rapor döner", "### Q-T-001:" in g["acik_sorular"]
    and "tespit edilmedi" not in g["acik_sorular"] and g["akis_rapor"]["soru"] == 1)

print("7) motor bağlantısı")
from skills import surec_analizi as SA  # noqa: E402
cagri: list = []
AK.dosya_akis_kapat = lambda *a, **k: cagri.append((a, k))
SA._api_cagri = lambda *a, **k: "### Süreç\n**PA-001:** x\n"
SA.referans_dosyalari_hazirla = lambda *a, **k: []
SA.canli_uygulama_baglami_hazirla = lambda *a, **k: ""
SA._kaydet = lambda ad, icerik: Path(ad)
SA.yonetici_ozeti_olustur = lambda *a, **k: ""
SA.surec_analizi_yap(icerik_override=[{"type": "text", "text": "Ödeme ekranı"}], ozel_atla=True)
chk("süreç: akış kapatma çağrıldı (kaynak=girdi)", cagri and cagri[-1][0][0] == "surec-analizi.md"
    and cagri[-1][1].get("kaynak") == "Ödeme ekranı", cagri)
cagri.clear()
SA.ozel_prompt_oku = lambda *a, **k: "ÖZEL PROMPT"
SA.surec_analizi_yap(icerik_override=[{"type": "text", "text": "Ödeme ekranı"}], ozel_atla=False)
chk("süreç: özel promptta akış kapatma ÇAĞRILMAZ", not cagri, cagri)
import skills.teknik_analiz as TA  # noqa: E402
_kaynak = Path(TA.__file__).read_text(encoding="utf-8")
chk("teknik: akış kapatma özel prompt dışında + acik-sorular.md'ye", "if not ozel_teknik:" in _kaynak
    and 'soru_dosya="acik-sorular.md"' in _kaynak)
import app as A  # noqa: E402
chk("app: Task iş modu 'akis-kapat' + pano özeti", 'mode == "akis-kapat"' in Path(A.__file__).read_text(encoding="utf-8")
    and callable(getattr(A, "_akis_kapatma_ozet", None)))

print()
if _hata:
    print(f"AKIŞ KAPATMA TESTLERİ BAŞARISIZ ({_hata} hata)")
    sys.exit(1)
print("AKIŞ KAPATMA TESTLERİ GEÇTİ")
