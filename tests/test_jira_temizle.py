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

print("3) tüm Jira yazım yolları tek kapıdan")
jg = Path(B.__file__).parent.joinpath("jira_gorevleri.py").read_text(encoding="utf-8")
jk = Path(B.__file__).parent.joinpath("jira_kopru.py").read_text(encoding="utf-8")
chk("gorev_jiraya_yaz / fe-be-olustur / _analiz_adf → jira_icin_temizle", jg.count("jira_icin_temizle(") >= 3)
chk("köprü gövde yazımı → jira_icin_temizle", "temiz = jira_icin_temizle(analiz_md)" in jk)
chk("prompt: Jira task dili kuralı", "JİRA TASK DİLİ" in B.VARSAYILAN_PROMPTLAR["gorev_teknik_analiz"]["icerik"]
    and "KAYNAK ALINTISI YAZMA" in B.VARSAYILAN_PROMPTLAR["gorev_teknik_analiz"]["icerik"])

print()
if _hata:
    print(f"JIRA TEMİZLİK TESTLERİ BAŞARISIZ ({_hata} hata)")
    sys.exit(1)
print("JIRA TEMİZLİK TESTLERİ GEÇTİ")
