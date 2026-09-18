---
name: akis-cikarma
description: Bir uygulamayı Claude in Chrome ile ekran-ekran gezerek kullanıcı akışlarını (flow) çıkarır — adım tablosu + Mermaid diyagram üretir ve Confluence'a yayınlar. Analist bir uygulama URL'i verip "akışlarını çıkaralım / flow analizi / süreç diyagramı" dediğinde kullan.
---

# Akış Çıkarma — İnteraktif Flow Analizi (agent + analist eş-pilot)

Bir hedef uygulamayı **Claude in Chrome** (analistin girişli tarayıcısı) ile adım adım gezerek her
kullanıcı akışını yapılandırılmış **adım tablosu + Mermaid diyagram** olarak çıkarır ve **Confluence**'a
yayımlar. Agent tarayıcıyı sürer ve gözlemler; **analist hassas adımları yapar ve yönlendirir**.

## Analist Hızlı Başlangıç (5 adım — bunu yap)
1. **Claude Code'u aç** (bu araç) ve `brd-analyst-agent-v2` projesinde ol. **Claude in Chrome** eklentisi bağlı olsun.
2. **Chrome'da hedef uygulamada giriş yap** (VPN gerekiyorsa bağlan). Girişli sekme açık kalsın.
3. Claude Code'a yaz: **"<uygulama> akışlarını çıkaralım, URL: <adres>"** (ya da `/akis-cikarma`). Bu skill devreye girer.
4. Claude ekranları gezerken **login/OTP/parola gibi hassas girişleri SEN yaparsın** ("tamam" deyince devam eder);
   belirsiz yerde yön verirsin ("şimdi iade sekmesine geç").
5. Claude her akışı **adım tablosu + Mermaid diyagram** olarak üretir; onaylayınca **Confluence'a yazar**. Sıradaki akışa geç.

> İlk seansta önce **akış envanteri** çıkarılır (uygulamadaki tüm ekran/modüller listelenir), sonra iki analist
> **modül bazlı böler**. Bir şey iyi çalışmazsa bu dosyayı düzenle + commit et (bkz. §7) — herkeste güncellenir.

## 0) Roller ve GÜVENLİK SINIRI (değişmez)
- **Agent (sen):** tarayıcıyı sürer (navigate/oku/tıkla/ekran görüntüsü/network), ekran yapısını + alanları
  + validasyonları + gözlemlenen API çağrılarını çıkarır, diyagram + doküman üretir, Confluence'a yazar.
- **Analist:** URL + hangi akış olduğunu söyler; **parola / OTP / kart / kimlik gibi hassas girişleri KENDİSİ
  yapar** (kendi Chrome'unda zaten girişli olabilir); belirsiz yönlendirmede yön verir; çıktıyı onaylar.
- **SEN ASLA parola/OTP/kart bilgisi YAZMAZSIN.** Böyle bir adıma gelince DUR, ne yapılması gerektiğini
  söyle, analistten yapmasını iste, "tamam" deyince devam et. Ekrandaki hassas değerleri (token, OTP, kart no)
  dokümana/diyagrama **taşıma** — "[kullanıcı adı]", "[OTP]" gibi maskelenmiş yer tutucu kullan.
- Bu bir **yetkili** analiz çalışmasıdır (analist uygulamada hesabı olan kişidir). Yalnız gözlemle; kalıcı/geri
  alınamaz aksiyonları (kaydet/gönder/sil/öde) analist onayı olmadan tetikleme — akışı görmek için gerekiyorsa
  test verisiyle ve analist onayıyla ilerle.

## 1) Hazırlık (her seans başında)
1. **Chrome araçlarını yükle** (deferred → tek çağrıda):
   `ToolSearch("select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__find,mcp__claude-in-chrome__read_network_requests,mcp__claude-in-chrome__form_input,mcp__claude-in-chrome__tabs_create_mcp", 8)`
2. `tabs_context_mcp` ile bağlı sekmeleri gör; analistin hedef uygulamada **girişli** olduğunu doğrula.
   Girişli değilse: giriş + OTP'yi **analist yapsın** (sen bekle), sonra devam.
3. Analistten al: **hedef uygulama adı**, **Confluence space key + parent sayfa** (varsa; yoksa "yeni space
   kurulacak" notu — yayın adımı bunu bekler), bu seansta çıkarılacak **akış(lar)**.

## 2) İlk seans: akış envanteri (backlog)
Uygulama ilk kez ele alınıyorsa önce **hızlı bir tur** at: ana menü/nav'ı `read_page` (accessibility tree) ile
oku, tüm ekran/modülleri listele. Analistle birlikte **akış backlog'u** çıkar (ör. Giriş/OTP, Kayıt, Kupon
Oluşturma, İade, Rapor…). Backlog'u index sayfasına (bkz. §5) yaz; iki analiste **modül bazlı böl** (çakışma
olmaz — herkes kendi alt sayfalarını yayımlar).

## 3) Bir akışı çıkarma döngüsü (her flow için)
Her adımda **küçük ve doğrulanabilir** ilerle:
1. **Git:** `navigate` ile akışın giriş noktasına. Gerekirse `tabs_create_mcp` ile temiz sekme.
2. **Oku:** `read_page` (yapı + alanlar: ad/tip/zorunlu/validasyon + butonlar/linkler) + gerektiğinde
   `computer{action:"screenshot"}` (görsel). Alan adlarını, seçenekleri, hata/validasyon mesajlarını yakala.
3. **Network:** `read_network_requests` ile ekranın/aksiyonun tetiklediği **API çağrılarını** (METHOD + path)
   çıkar. Gövde/parametre gerekiyorsa ilgili isteğin detayına bak. (Hassas header/token'ı dokümana taşıma.)
4. **Etkileşim:**
   - Hassas değilse (ör. filtre, arama, tarih) `form_input`/`computer` ile sen doldur/tıkla.
   - **Hassas ise (parola/OTP/kart)** → DUR, analistten yapmasını iste, "tamam"da devam.
   - Belirsiz yönlendirme → analistten yön iste.
5. **Kaydet (bellekte):** her adımı şu satırla not al: `adım · ekran · aksiyon · giriş alanları · sistem yanıtı
   · API · sonraki`. Dallanmaları (OTP başarılı/başarısız, validasyon hatası) ayrıca işaretle.
6. Akış bitince **dokümanı üret** (§4 şablon) + **Mermaid diyagram**. Analiste ÖZETLE göster, onay al.
7. Onaylanınca **Confluence'a yayınla** (§5).

## 4) Çıktı şablonu (her akış = bir sayfa)
`sablon-akis.md` dosyasını temel al. Zorunlu bölümler: Künye (uygulama/akış/rol/ortam/tarih) · Ön koşullar ·
**Adım Tablosu** (adım·ekran·aksiyon·alanlar·sistem yanıtı·API·sonraki) · **Karar/Dallanmalar** ·
**Mermaid akış diyagramı** (`flowchart TD`; ekran=düğüm, karar=eşkenar dörtgen, adım ID'leri) · Gözlemlenen
API'ler · Açık sorular/uç durumlar. **Kanıt işareti** kullan: ✅ canlı gözlendi · ⚠️ çıkarım · ❓ belirsiz.
Kaynağı `[K: Canlı UI:<route>]` / `[K: Network:<METHOD> <path>]` ile işaretle. Hassas veri = maskeli.

## 5) Confluence'a yayınlama + birleştirme
**Yapı:** bir **index (ana) sayfa** ("[Uygulama] Akış Analizi") + **her akış = index'in ALT sayfası**.
Şablon: `sablon-index.md`. **İki analist aynı space/parent'ı kullanır.**

**Yayın yolu (biri):**
- **A. Atlassian MCP (tercih):** `createConfluencePage` / `updateConfluencePage` (parent = index sayfa id).
- **B. Ürün endpoint'i:** dokümanı `output/<akis-adi>.md`'ye yaz →
  `curl -s -X POST http://localhost:5003/api/confluence/publish -H "Content-Type: application/json" -d '{"dosya":"<akis-adi>.md","space_key":"<KEY>","parent_id":"<INDEX_ID>","title":"<Başlık>"}'`
- **C. Elle:** markdown/storage çıktısını analiste ver, yapıştırsın.

### ÇAKIŞMA & SIRA KONTROLÜ (iki analist paralel — KRİTİK)
- **Her akış AYRI sayfadır** → farklı sayfalara paralel yayın **çakışmaz**; sıra önemsiz. Bunu garanti etmek için:
  **modül bazlı bölüşüm** + **benzersiz başlık konvansiyonu** `"<Uygulama> - <Modül> - <Akış>"` (iki analist aynı
  başlığı üretmez → Confluence'ın "aynı space'te aynı başlık" reddi de tetiklenmez).
- **Confluence'ın kendi kilidi:** her sayfanın **sürüm numarası** var; aynı sayfaya eşzamanlı iki güncelleme →
  ikincisi **409 (stale version)** alır, **sessiz üzerine yazma OLMAZ**. Kural: güncellemeden önce **güncel sürümü
  OKU → yaz; 409 alırsan yeniden oku + kendi değişikliğini merge et + tekrar dene** (blind overwrite yapma).
- **Index tek çekişme noktasıdır** → ikisinden birini uygula:
  1. **(Tercih) Index elle düzenlenmez:** alt sayfaları Confluence'ın **"Children Display" makrosu** ile
     otomatik-listele → yeni akış sayfası açılınca index kendiliğinden gösterir → **sıfır çakışma**.
  2. Elle durum tablosu şartsa: index'i **tek kişi** (owner ya da atanan) günceller, ya da yukarıdaki
     **409-oku-merge-tekrar-dene** döngüsünü uygula.
- **"Hangi sıra?"** yanıtı: ayrı akış sayfalarında sıra yok (bağımsız); index'te ya makro (sırasız/otomatik) ya
  da sürüm-kontrollü sıralı yazım (ilk yazan v.N+1, ikinci 409 → merge → v.N+2). Kimse kimsenin yazımını EZMEZ.

### DİYAGRAM CONFLUENCE'TA GÖRÜNÜR OLMALI (ham mermaid render OLMAZ)
Confluence eklenti yoksa ```mermaid'i **render etmez**. Bu yüzden her diyagramı **İKİ biçimde** koy:
1. **Görsel (zorunlu):** mermaid'i **PNG/SVG'ye çevir** → sayfaya **ek (attachment)** yükle + `<ac:image>` ile göm.
   Render: yerelde `@mermaid-js/mermaid-cli` (`mmdc -i x.mmd -o x.png`) VARSA onunla; yoksa mermaid.js'li bir HTML'i
   tarayıcıda render edip **screenshot**. **DIŞ servise (mermaid.ink vb.) gönderme** — şirket ekran adları dışarı çıkmasın.
2. **Kaynak (düzenlenebilir):** mermaid metnini bir **kod bloğu / expand** içinde de bırak (sonraki güncellemede düzenlenebilsin).
- Confluence'ta **Mermaid/PlantUML makrosu** KURULUYSA: mermaid metnini o makroya koy → görsele gerek kalmaz (önce öğren).

## 6) İki analist + birleştirme
- Backlog modül bazlı bölünür; herkes kendi alt sayfalarını yayımlar → **çakışma yok**.
- Haftalık: index'te durum takibi; gün sonunda kısa "hangi akışlar bitti" özeti index'e.
- Kapanışta: tutarlılık turu (aynı terim/kanonik ad), varsa **uçtan-uca birleşik diyagram** (akışları bağlayan).

## 7) Bu skill'i GELİŞTİRME — ORTAK, tek kaynak (analistler için)
Bu klasör (`.claude/skills/akis-cikarma/`) **git'te tek kaynaktır** → her analistte AYNI skill geçerlidir.
Format/şablon **hızlı** değiştirilebilir ve **herkese yayılır**:
- Analist Claude'a der: *"akış şablonuna şu kolonu ekle / diyagramı şöyle yap"* → **Claude** `SKILL.md` veya
  `sablon-akis.md`/`sablon-index.md`'yi düzenler → **commit + push** eder (bir cümlede olur).
- **Diğer analiste geçmesi:** ürünün **AUTO_UPDATE**'i `origin/main`'i çeker (ya da analist `git pull` yapar) →
  **sonraki Claude Code seansında** yeni format geçerli olur. (Açık bir seansta anında değil — yeni seans/pull gerekir.)
- **Çakışmayı önle (iki editör):** format değişiklikleri tek dosyada toplansın (`sablon-akis.md`); büyük değişiklikten
  önce diğer analiste kısa haber + `git pull`. Küçük dosya olduğundan git merge nadiren ve kolay çözülür.
- Böylece "seninle hızlı düzenle" = Claude'a söyle → o düzenler+push eder; "diğer analistte geçerli" = pull/AUTO_UPDATE.

## Notlar
- Uygulama iç ağ/VPN'deyse yalnız analistin makinesinden erişilir (Claude in Chrome bunu kullanır).
- Adım adım ilerle; her tur öncesi `read_page` ile GÜNCEL ekranı doğrula (bayat koordinata tıklama).
- 1 haftalık hedef: envanter (gün 0) → çıkarma (gün 1-4) → birleştirme/tutarlılık (gün 5) + tampon.
