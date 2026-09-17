# MBS Domain Kuralları & Terim Sözlüğü

<!--
════════════════════════════════════════════════════════════════════════════
 BU DOSYA NE İŞE YARAR
════════════════════════════════════════════════════════════════════════════
 Buradaki kurallar HER süreç/teknik/BRD/kapsam/Jira analizine otomatik eklenir
 (skills/base.py → _domain_kurallari_oku). Amaç: agent'ın merkezi bahis (MBS)
 domain'ini tutarlı ve doğru kullanması — terminoloji, iş kuralları, değişmezler.

 KURALLAR:
 • Bu dosya git'te İZLENİR → pull ile tüm ekibe iner. Ortak, paylaşılan bilgidir.
 • PII / sır / parola / bağlantı dizesi / gerçek accountId YAZMA. Yalnız KURAL + TERİM.
 • GERÇEK VERİ (DB tablo dökümü, örnek satır, Kafka payload, endpoint listesi) BURAYA
   DEĞİL → RAG corpus'una gider: reference/confluence/ (El Kitabı) + reference/services/
   (Swagger). Burası "nasıl yorumlanmalı" kuralı; corpus "ham veri".
 • Kısa ve emir kipinde yaz. Her kural tek satır/madde. Model bunu ezbere uygular.

 NASIL AKTİF OLUR:
 • Aşağıdaki "KURALLAR-BASLANGIC" işaretinden SONRAKİ içerik analizlere enjekte edilir.
 • İşaretten öncesi (bu yönerge) yok sayılır. İşaretten sonrası BOŞ/yorum ise hiçbir şey
   eklenmez (güvenli varsayılan) → sen doldurana kadar davranış değişmez.
 • Değişiklik sonrası "Yeniden Başlat" (backend yeniden okusun).

 ÖNERİLEN BÖLÜMLER (aşağıdaki iskeleti doldur):
 1. Terim Sözlüğü (TR/EN)     2. Domain Değişmezleri (invariants)
 3. Süreç/Durum Kuralları     4. Kaynak/İsimlendirme Notları
════════════════════════════════════════════════════════════════════════════
-->

<!-- KURALLAR-BASLANGIC -->

<!--
 Aşağıdaki iskeleti kopyalayıp yorum işaretlerini KALDIRARAK doldur. Örnek biçim:

 ### Terim Sözlüğü
 - **Kupon (coupon):** bir veya çok sayıda seçimden (selection) oluşan bahis birimi.
 - **Selection:** bir marketteki tek bir tercih (ör. "1", "X", "2"); bir orana (odds) bağlıdır.
 - **Sales Open / Sales Closed:** bir event'e bahis kabulünün açık/kapalı olduğu durum.
 - (… kendi terimlerini ekle …)

 ### Domain Değişmezleri (her analizde geçerli kurallar)
 - Sales Closed olan bir event'e yeni kupon kalemi EKLENEMEZ.
 - Settlement idempotent olmalı: aynı event iki kez sonuçlandırılmamalı.
 - (… kendi değişmezlerini ekle …)

 ### Süreç / Durum Kuralları
 - Kupon durum akışı: OPEN → ACCEPTED → SETTLED | VOID | CASHOUT (izinli geçişler).
 - (… ekle …)

 ### Kaynak / İsimlendirme Notları
 - Endpoint'ler için tek doğru kaynak Swagger'dır (reference/services/).
 - (… ekle …)
-->
