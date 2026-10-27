"""Jira'ya giden task gövdesi temizliği — `base.jira_icin_temizle` (offline, 0 token).

Owner geri bildirimi: Task analizinde task'a ait olmayan bilgiler Jira'ya gidiyor, elle düzeltiliyor.
Kapsam: HTML yorumu · Yönetici Özeti · kaynak alıntı cümleleri ("Analist notu bunu doğrular: …",
"Confluence: …") · "Confluence'a göre" öneki · meta-gerekçe cümlesi · `[K:]` etiketleri (emoji dahil) ·
boş kalan madde · atlanan bölümler sonrası ardışık numaralama + alt başlık/atıf güncellemesi ·
numarasız başlık korunur · tüm Jira yazım yolları bu fonksiyonu çağırır.
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("BILDIRIM", "false")

from skills import base as B  # noqa: E402

_hata = 0


def chk(ad, kosul, ek=""):
    global _hata
    if not kosul:
        _hata += 1
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if ek and not kosul else ""))


ORNEK = """## 📋 Yönetici Özeti
*(Hızlı tarama için — Jira'ya yazılmaz, düzenlenebilir.)*

- **Kapsam:** 5 bölüm

---
<!-- RAG: 12 referans dosya kullanıldı | bağlam filtresi: yok -->

## 1. Amaç ve Hedefler

- **Ne yapılacak (FE):** Liste ekranında kayıt oluşturulunca liste yeni kaydın id'siyle filtrelenmeli `[K: Jira:PRJ-1]`. Analist notu bunu doğrular: "create sonrası yeni kaydın tek olarak listelenmesi istenmektedir." `[K: Jira:PRJ-1]`
- **Beklenen davranış kaynakta tanımlı:** "Add (Button): liste otomatik yenilenir ve filtre uygulanır." `[K: Confluence:Liste-Ekrani]`
- **Hedef:** filtre otomatik dolsun `[K: 🔍 Türetilmiş]`.

## 2. İş Gereksinimleri

| Bileşen | Kural |
|---|---|
| **Id filtresi** | Confluence'a göre manuel kayıtlar market koşulundan muaftır `[K: Confluence:Liste-Ekrani]`. |

## 3. Teknik Gereksinimler

### 3.1. Mevcut davranış

- Liste `GET /api/items?hasMarket=true` ile açılır `[K: Swagger:items]`.

### 3.3. Kritik nokta

- İstek `hasMarket` olmadan kurulur `[K: 🔍 Türetilmiş]`. Bu yol "servise parametre eklenmeli" yaklaşımına kıyasla en doğrudan çözümdür. (Uç `hasMarket` yokken varsayım uygularsa kayıt düşer; bu varsayımın uygulanıp uygulanmadığı FE'nin kontrolü dışıdır — bkz. Bağımlılık.) `[K: ❓ Belirsiz]`

## 7. Frontend İş Kırılımı

- Liste çağrısı 3.3'teki parametre setiyle yapılır (bkz. 3.3).

## 11. Kabul Kriterleri

- **AC-1:** Create sonrası liste tek kayıt gösterir (`totalElements=1`) `[K: Jira:PRJ-1]`.

## Bağımlılık ve Arayüz (FE↔BE)

1. Create yanıtı `id` döndürmeli `[K: Jira:PRJ-2]`.
"""

print("1) gürültü temizliği")
t = B.jira_icin_temizle(ORNEK)
chk("Yönetici Özeti + HTML yorumu gitti", "Yönetici Özeti" not in t and "<!--" not in t and "RAG:" not in t)
chk("[K:] etiketleri (emoji dahil) gitti", "[K:" not in t and "Türetilmiş" not in t and "Belirsiz" not in t)
chk("'Analist notu bunu doğrular: \"…\"' cümlesi gitti", "Analist notu" not in t and "istenmektedir" not in t)
chk("'kaynakta tanımlı: \"…\"' alıntısı gitti (boş kalan madde de)", "kaynakta tanımlı" not in t and "otomatik yenilenir ve filtre" not in t
    and not re.search(r"^- \*\*Beklenen davranış", t, re.M), t)
chk("'Confluence'a göre' öneki düştü, kural kaldı", "Confluence'a göre" not in t and "anuel kayıtlar market koşulundan muaftır" in t and "Manuel kayıtlar" in t)
chk("meta-gerekçe + kontrol-dışı parantezi gitti, iş cümlesi kaldı", "kıyasla" not in t and "kontrolü dışıdır" not in t
    and "İstek `hasMarket` olmadan kurulur" in t, t)
chk("iş içeriği korundu (endpoint, AC, tablo)", "GET /api/items?hasMarket=true" in t and "AC-1" in t and "| **Id filtresi** |" in t)

print("2) bölüm numaralama")
basliklar = re.findall(r"^## (\d+)\. ", t, re.M)
chk("1,2,3,7,11 → 1,2,3,4,5", basliklar == ["1", "2", "3", "4", "5"], basliklar)
chk("alt başlıklar 3.1/3.3 korunur, 7→4 altında atıf 3.3 kalır (3 değişmedi)", "### 3.1. Mevcut davranış" in t and "(bkz. 3.3)" in t)
chk("numarasız başlık korunur", "## Bağımlılık ve Arayüz (FE↔BE)" in t)
ORNEK2 = "## 1. A\n\n## 4. B\n\n### 4.2. C\n\nbkz. 4.2 ve (4.2) ve bölüm 4.2'de.\n\n## 9. D\n"
t2 = B.jira_icin_temizle(ORNEK2)
chk("4→2 haritası alt başlık + atıflara uygulanır", "## 2. B" in t2 and "### 2.2. C" in t2 and "bkz. 2.2" in t2 and "(2.2)" in t2
    and "bölüm 2.2'de" in t2 and "## 3. D" in t2, t2)
chk("zaten ardışıksa değişmez", B._bolumleri_yeniden_numarala("## 1. A\n## 2. B\n") == "## 1. A\n## 2. B\n")
chk("boş/None güvenli", B.jira_icin_temizle("") == "" and B.jira_icin_temizle(None) is None)

print("2b) parantez / tablo satırı / kod bloğu korumaları")
ORNEK3 = ("## 1. A\n\n- Çağrı `liste()` ile yapılır ( ) ve (  ) artığı gider.\n\n"
          "| Alan | Kural |\n|---|---|\n| x | Bu yol servise parametre ekleme yaklaşımına kıyasla en doğrudan çözümdür. Zorunlu alan. |\n\n"
          "```js\nfoo( )\n```\n\n## 4. B\n\n### 4.1. C\n\n(4.1) ve (1.5 sn) ve (2.0 sürümü)\n")
t3 = B.jira_icin_temizle(ORNEK3)
chk("`liste()` fonksiyon çağrısı korunur; boşluk sonrası içi boş parantez gider", "`liste()`" in t3 and "( )" not in t3.split("```")[0]
    and "(  )" not in t3 and "artığı gider" in t3, t3)
chk("çitli kod bloğu dokunulmaz", "foo( )" in t3)
chk("tablo satırı yaşar: meta cümle hücreden silinir, hücreler/ayraçlar kalır", "| x |" in t3 and "kıyasla" not in t3 and "Zorunlu alan." in t3, t3)
chk("(4.1) gerçek `###` alt başlık → (2.1); (1.5 sn) / (2.0 sürümü) sayıları dokunulmaz",
    "(2.1)" in t3 and "### 2.1. C" in t3 and "(1.5 sn)" in t3 and "(2.0 sürümü)" in t3, t3)

print("3) tüm Jira yazım yolları tek kapıdan")
jg = Path(B.__file__).parent.joinpath("jira_gorevleri.py").read_text(encoding="utf-8")
jk = Path(B.__file__).parent.joinpath("jira_kopru.py").read_text(encoding="utf-8")
chk("gorev_jiraya_yaz / fe-be-olustur / _analiz_adf → jira_icin_temizle", jg.count("jira_icin_temizle(") >= 3)
chk("köprü gövde yazımı → ortak govde_birlestir (jira_gorevleri) → jira_icin_temizle", "govde_birlestir(analiz_md, mevcut_desc)" in jk
    and "temiz = jira_icin_temizle(analiz_md or \"\")" in jg)
chk("prompt: Jira task dili kuralı", "JİRA TASK DİLİ" in B.VARSAYILAN_PROMPTLAR["gorev_teknik_analiz"]["icerik"]
    and "KAYNAK ALINTISI YAZMA" in B.VARSAYILAN_PROMPTLAR["gorev_teknik_analiz"]["icerik"])

# Açık/ZORUNLU sorular Jira gövdesine GİTMEZ (owner kararı 2026-10-21) — "Jira'dan çek" ile geri yüklense de temizlenir
_soru_md = "## 1. Amaç\nX yapılacak.\n\n## 4. Kabul Kriterleri\n- AC-1\n\n## ❗ Cevap Bekleyen Zorunlu Sorular\n- **Q-T-001 — x:** soru?\n- **Q-T-002 — y:** soru?\n"
_st = B.jira_icin_temizle(_soru_md)
chk("ZORUNLU sorular bölümü Jira gövdesinden silinir", "Cevap Bekleyen Zorunlu" not in _st and "Q-T-001" not in _st)
chk("soru temizliğinde iş içeriği korunur (Amaç + Kabul Kriterleri)", "## 1. Amaç" in _st and "Kabul Kriterleri" in _st and "AC-1" in _st)
chk("'## Açık Sorular' bölümü de silinir", "Açık Sorular" not in B.jira_icin_temizle("## 2. İş\nY\n\n## Açık Sorular\n- Q-1: ?\n"))
# Agent iskele artıkları: FE+BE katman göstergesi + tekrarlı 'Kaynak Görev' başlıkları Jira'ya GİTMEZ (owner 2026-10-21)
_isk = "**Bu katmanda iş:** VAR — bir şey\n\n### Kaynak Görev: MBS-1 — BE — özet\n### Kaynak Görev: MBS-1 — BE — özet\n\n## 1. Amaç\nGerçek iş."
_it = B.jira_icin_temizle(_isk)
chk("'Bu katmanda iş' satırı silinir", "Bu katmanda iş" not in _it)
chk("tekrarlı '### Kaynak Görev:' başlıkları silinir, iş kalır", "Kaynak Görev" not in _it and "## 1. Amaç" in _it and "Gerçek iş" in _it)

# Araç-çağrısı iskelesi (owner 2026-10-23: MBSUATEAM-362 FE çıktısında ham <invoke> sızmıştı) — hem doğrudan
# arac_cagri_temizle hem jira_icin_temizle elemeli; gerçek içerik korunmalı, sızıntı yokken metin değişmemeli.
_AC = ("## 3. Teknik Gereksinimler\nAnalistin işaret ettiği fault_catalog bilgisini referanslarda arıyorum, sonra işleyeceğim.\n\n"
       "<invoke name=\"Grep\">\n<parameter name=\"pattern\">fault_catalog</parameter>\n</invoke>\n\nGerçek analiz içeriği.")
_act = B.arac_cagri_temizle(_AC)
chk("arac_cagri_temizle: <invoke>/<parameter> + ajan ara-sözü silinir, içerik kalır",
    "<invoke" not in _act and "<parameter" not in _act and "arıyorum" not in _act
    and "Gerçek analiz içeriği." in _act and "## 3. Teknik Gereksinimler" in _act, _act[:160])
chk("sızıntı yokken metin değişmez (yan etki yok)",
    B.arac_cagri_temizle("## Amaç\nServisi çağırıyor.") == "## Amaç\nServisi çağırıyor.")
chk("jira_icin_temizle de <invoke> eler", "<invoke" not in B.jira_icin_temizle(_AC) and "Gerçek analiz içeriği." in B.jira_icin_temizle(_AC))

# "Gözlem notu: …" meta notu Jira'ya GİTMEZ (owner 2026-10-27) — blockquote + düz paragraf; gerçek içerik korunur.
_gn = "## 1. Amaç\nGerçek.\n\n> Gözlem notu: Bu turda canlı gözlem yapılamadı. Add Role canlıda gözlenmedi. UAT'ta doğrulanmalı.\n\n## 2. Çözüm\nDevam."
_gno = B.jira_icin_temizle(_gn)
chk("Gözlem notu (blockquote) silinir", "Gözlem notu" not in _gno and "Gerçek." in _gno and "Devam." in _gno)
chk("Gözlem notu (düz paragraf + emoji) silinir",
    "Gözlem notu" not in B.jira_icin_temizle("## A\nX.\n\n🔎 Gözlem notu: gözlenemedi, UAT.\n\n## B\nY.") )

# Negatif kapsam-dışı + ortama özgü somut kayıt ID listesi aynı satırdaysa Jira'ya GİTMEZ (owner 2026-10-27);
# ÜÇ koşul da gerekli → meşru ID listesi ya da tek başına negasyon KORUNUR.
_ni = ("## 1. Çözüm\nServisi çağır.\n\n"
       "- **Mevcut yetim kayıtlar:** UAT'taki ID 17/18/19 ve dev'deki id 181/182 bu düzeltmeyle temizlenmez; "
       "bu kayıtlar için test ve dev ortamlarında temizlik işlemi yapılmayacaktır.\n\n## 2. Kabul\nTamam.")
_nit = B.jira_icin_temizle(_ni)
chk("negatif kapsam-dışı + ortam kayıt ID satırı silinir",
    "temizlenmez" not in _nit and "17/18/19" not in _nit and "Servisi çağır." in _nit and "Tamam." in _nit)
# Yalnız ID listesi (negasyon/ortam yok) → KORUNUR; yalnız negasyon (ID yok) → KORUNUR.
chk("tek başına ID listesi korunur",
    "22/23" in B.jira_icin_temizle("## 1. İş\n- Etkilenen kayıtlar: id 22/23 güncellenecek.\n"))
chk("tek başına negatif cümle korunur",
    "yapılmaz" in B.jira_icin_temizle("## 1. İş\n- Bu akışta soft-delete yapılmaz; hard-delete uygulanır.\n"))

print()
if _hata:
    print(f"JIRA TEMİZLİK TESTLERİ BAŞARISIZ ({_hata} hata)")
    sys.exit(1)
print("JIRA TEMİZLİK TESTLERİ GEÇTİ")
