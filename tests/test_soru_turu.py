"""Açık soru TÜRÜ + cevap sürekliliği (Emin Kaleli geri bildirimi, owner 2026-11-06). Offline / 0 token."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("TELEMETRI_SINK", "off")

from skills import soru_turu as ST  # noqa: E402
from skills import sorular as SO  # noqa: E402
from skills import teknik_analiz as TA  # noqa: E402
from skills import base as B  # noqa: E402

hatalar = []


def chk(ad, kosul, ek=""):
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f" — {ek}" if ek and not kosul else ""))
    if not kosul:
        hatalar.append(ad)


print("1) tür belirleme")
chk("teknik: hangi serviste uygulanıyor", ST.tur_belirle("Sıralama hangi backend servisinde uygulanıyor?") == "teknik_arastirma")
chk("teknik: repository/index/collation/cache", all(ST.tur_belirle(x) == "teknik_arastirma" for x in
    ("Repository metodu hangisi?", "DB index'i var mı?", "Kolonun collation ayarı nedir?", "Cache süresi ne kadar?")))
chk("teknik: API parametresi", ST.tur_belirle("Liste ucu sortBy parametresi var mı, destekliyor mu?") == "teknik_arastirma")
chk("iş kararı: ürün niyeti teknik kelime içerse de", ST.tur_belirle("externalId'ye metin değer gelirse sıralama nasıl olmalı, ürün ne istiyor?") == "is_karari")
chk("iş kararı: varsayılan", ST.tur_belirle("Remove Sorting sonrası varsayılan sıra ne olmalı?") == "is_karari")
chk("doğrulanamadı", ST.tur_belirle("DB index'i arayüzden doğrulanamadı") == "dogrulanamadi")
chk("açık Tür satırı kazanır", ST.tur_belirle("### Q-T-001: x\n- Tür: İş Kararı\n- Soru: hangi serviste?") == "is_karari"
    and ST.tur_belirle({"tur": "Teknik Araştırma", "soru": "olmalı mı"}) == "teknik_arastirma")

MD = """## Açık Sorular

### Q-T-001: Sıralama katmanı
- Öncelik: Kritik
- Zorunlu: Evet
- Soru: Provider ID sıralaması BFF tarafında mı backend sorgusunda mı uygulanıyor?

### Q-T-002: Metin değer
- Öncelik: Yüksek
- Zorunlu: Evet
- Soru: externalId'ye metin değer gelirse sıralama nasıl olmalı, ürün ne istiyor?

### Q-T-003: Sayfalama
- Öncelik: Yüksek
- Zorunlu: Evet
- Soru: Sayfalama ile sıralama birlikte nasıl davranmalı, sunucu tarafında tüm kayıtlar mı sıralanmalı?

### Q-T-004: İkincil sıralama
- Öncelik: Orta
- Zorunlu: Evet
- Soru: Eşit Provider ID'lerde ikincil sıralama hangi alana göre olmalı?

## Başka bölüm
metin
"""
print("2) etiketleme + zorunlu normalize")
e = ST.md_tur_etiketle(MD)
chk("her bloğa Tür satırı, başka bölüm dokunulmadı", e.count("- Tür:") == 4 and "## Başka bölüm\nmetin" in e)
chk("sayılar", ST.tur_sayilari(e) == {"is_karari": 3, "teknik_arastirma": 1, "dogrulanamadi": 0}, ST.tur_sayilari(e))
z = ST.zorunlu_normalize(e)
chk("teknik bloğun Zorunlu'su silindi, iş kararlarınınki kaldı", z.count("Zorunlu: Evet") == 3 and "Q-T-001" in z)
z3 = ST.zorunlu_normalize(e, tavan=2)
chk("tavan=2 → en yüksek öncelikli 2 zorunlu kalır (Orta düşer)", z3.count("Zorunlu: Evet") == 2 and
    "### Q-T-004" in z3 and z3.split("### Q-T-004")[1].count("Zorunlu: Evet") == 0)
chk("idempotent", ST.md_tur_etiketle(e) == e)

print("3) cevaplanan eleme")
cev = [{"id": "Q-003", "soru": "Sayfalama ile sıralama birlikte nasıl davranmalı? Sunucu tarafında tüm kayıtlar sıralanır mı?", "cevap": "sunucu tarafı tam sıralama"},
       {"id": "Q-005", "soru": "İkincil sıralama hangi alana göre?", "cevap": "ID artan"}]
out, elenen = ST.cevaplananlari_ele(e, cev)
chk("2 tekrar soru elendi, bölüm notu eklendi", {x["id"] for x in elenen} == {"Q-T-003", "Q-T-004"}
    and "### Q-T-003" not in out and "Önceki aşamada cevaplanmış" in out and "Q-T-002" in out, elenen)
chk("ilgisiz cevap elemez", ST.cevaplananlari_ele(e, [{"id": "Q-9", "soru": "Jira revizyon stratejisi ne?", "cevap": "x"}])[1] == [])

print("4) sorular.py parse + istatistik")
tmp = Path(tempfile.mkdtemp())
(tmp / "acik-sorular.md").write_text(z, encoding="utf-8")
p = SO.parse_md_sorular(tmp / "acik-sorular.md")
chk("parse: tur alanı", [q["tur"] for q in p] == ["teknik_arastirma", "is_karari", "is_karari", "is_karari"])
for q in p:
    q["durum"] = "acik"
ist = SO.istatistik_hesapla(p)
chk("istatistik: zorunlu/kritik yalnız iş kararı; teknik ayrı sayılır", ist["zorunlu_acik"] == 3 and ist["kritik_acik"] == 0
    and ist["teknik_acik"] == 1 and ist["is_karari_acik"] == 3, ist)
chk("parse: Tür satırı yoksa kalıptan", SO.parse_md_sorular(Path(tempfile.mkdtemp()) / "x.md") == [] and
    SO._tur({"soru": "hangi repository?"}) == "teknik_arastirma")

print("5) cevaplanan_sorular (defter)")
SO.SORULAR_DOSYA = tmp / "sorular.json"
SO.sorular_kaydet({"sorular": [
    {"id": "Q-003", "kaynak_dosya": "surec-analizi.md", "soru": "Sayfalama ile sıralama birlikte nasıl davranmalı?", "durum": "cevaplandi",
     "cevap": "sunucu tarafı", "guncellendi_at": "2026-11-06T10:00:00"},
    {"id": "Q-004", "kaynak_dosya": "surec-analizi.md", "soru": "eski", "durum": "cevaplandi", "cevap": "eski", "guncellendi_at": "2026-01-01T10:00:00"},
    {"id": "Q-005", "kaynak_dosya": "surec-analizi.md", "soru": "açık", "durum": "acik"}]})
import datetime as _dt  # noqa: E402
esik = _dt.datetime(2026, 11, 6, 9, 0).timestamp()
c = SO.cevaplanan_sorular(esik)
chk("yalnız bu oturumun cevaplananları", [x["id"] for x in c] == ["Q-003"] and "Q-003" in SO.cevaplanan_sorular_metni(esik))

print("6) teknik analiz: sonradan işleme + promptlar")
son = TA.sorulari_sonradan_isle(MD, c, bug_modu=True)
chk("teknik: tür + eleme + bug tavanı", "- Tür:" in son and "### Q-T-003" not in son and son.count("Zorunlu: Evet") <= 3)
chk("teknik soru promptu Tür kuralı", "Tür:" in TA._acik_sorular_prompt_olustur() and "CEVAPLADIĞI SORULAR" in TA._acik_sorular_prompt_olustur())
chk("şablonlar Tür satırı taşır", "- Tür:" in B.prompt_yukle("teknik_analiz_sorular") and "Açık Soru TÜRÜ" in B._BUTUNLUK_KURALLARI)
chk("cevaplanan bloğu", "KESİN BİLGİ" in TA._cevaplanan_blok(c) and TA._cevaplanan_blok([]) == "")

print(f"\n{'SORU TÜRÜ TESTLERİ GEÇTİ' if not hatalar else 'HATA: ' + ', '.join(hatalar)}")
sys.exit(1 if hatalar else 0)
