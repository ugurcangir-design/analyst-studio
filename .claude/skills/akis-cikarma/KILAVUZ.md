# Akış Çıkarma — Basit Kılavuz (analistler için)

Bu, `akis-cikarma` skill'ini nasıl kullanacağını, geliştireceğini ve paylaşacağını anlatan kısa rehberdir.
Teknik detay `SKILL.md`'de; burada **sade** anlatım var.

---

## 1) Bu skill ne işe yarar? (amaç)
Bir uygulamayı **ekran ekran gezip** kullanıcı akışlarını (giriş, kupon oluşturma, iade, rapor…) çıkarır ve
her akışı **adım tablosu + akış diyagramı** olarak **Confluence'a** yazar. Amaç: analistin uygulamayı elle
tek tek ekran yazmak yerine, Claude'un tarayıcıyı sürerek akışları hızlı ve tutarlı dökmesini sağlamak.

- **Claude ne yapar:** tarayıcıyı sürer, ekranı okur, alanları/butonları/validasyonu/ağ çağrılarını yakalar,
  diyagram + doküman üretir, Confluence'a yayınlar.
- **Sen (analist) ne yaparsın:** hangi akış olduğunu söylersin; **parola/OTP/kart gibi hassas girişleri KENDİN
  yaparsın** (Claude bunları asla yazmaz); belirsiz yerde yön verirsin; çıktıyı onaylarsın.

## 2) Nerede ve nasıl başlatılır? (kullanım)
- **Yer:** Claude Desktop → **Code** sekmesi (normal chat DEĞİL). `brd-analyst-agent-v2` klasörünü aç.
- **Ön koşul:** **Claude in Chrome** eklentisi bağlı; hedef uygulamada Chrome'da **girişli** ol.
- **Başlat:** sohbete şunu yaz →
  > `sky-panel akışlarını çıkaralım, URL: https://uat-sky-panel.sanstech.dev`

  (ya da `/akis-cikarma`). Skill devreye girer, ilerlemeye başlar.
- **Akış:** Claude gezer → hassas adımda "sen gir" der, "tamam" deyince devam → akışı diyagrama döker →
  onayınla → Confluence'a yazar → sıradaki akış.

## 3) Confluence space bilgisini ne zaman veririm?
- **Yayınlamaya geldiğinde.** Claude ilk yayından önce sana sorar: *"Hangi Confluence space + hangi ana (parent)
  sayfa?"* — o an verirsin. Örn:
  > `space: MBSFLOW, parent sayfa: <sayfa URL'i ya da id>`
- Space henüz belli değilse sorun yok: akışları çıkarmaya devam edersin, Claude **taslak** olarak tutar; space
  netleşince topluca yayınlar. **Yapı:** bir **ana (index) sayfa** + her akış onun **alt sayfası**.
- İki analist **aynı space/parent'ı** kullanır. Çakışma olmaz çünkü her akış ayrı sayfadır ve başlıklar
  benzersizdir (`Uygulama - Modül - Akış`). (Detay: SKILL.md §5.)

## 4) Uzun akışları çıkarabilir mi?
**Evet** — ama uzun akışı **parçalara böl**:
- Çok uzun bir akış (ör. 40 adım) tek sayfada boğucu olur → **mantıklı alt-akışlara** böl (her biri ayrı sayfa),
  birbirine link ver. Diyagramlar da küçük kalır, okunur.
- Claude her akışı **bitince hemen yayınlar** (sona saklamaz) → seans uzarsa bile önceki akışlar kaybolmaz.
- Çok uzun bir gezinme tek oturuma sığmazsa: akışı **bölüp** birden fazla seansta çıkar. "Kaldığımız akıştan
  devam" diyerek sürdürebilirsin.
- İpucu: uygulamanın **tamamını tek seferde** değil, **akış akış** çıkar (1 haftalık plan da böyle: önce
  envanter/backlog, sonra akışları teker teker).

## 5) Skill'i nasıl geliştiririm? (format/kural değiştirme)
İki yol — ikisi de kolay:
- **Claude'a söyle (en hızlı):** *"akış şablonuna 'Rol/Yetki' kolonu ekle"* ya da *"diyagramda kararları farklı
  göster"* → Claude `sablon-akis.md` / `SKILL.md`'yi düzenler ve **commit + push** eder.
- **Kendin düzenle:** `.claude/skills/akis-cikarma/` içindeki dosyaları aç, düzenle, kaydet.
- Bir adım takıldıysa oraya **kural** ekle (ör. "şu ekranda önce Filtre'yi aç, sonra tabloyu oku").

## 6) Geliştirmeyi diğerlerine nasıl aktarırım? (paylaşım)
- Değişiklik **git ile paylaşılır** (tek kaynak: `.claude/skills/akis-cikarma/`).
- Sen (ya da Claude) **commit + push** edersin →
  `git add .claude/skills/akis-cikarma && git commit -m "akis-cikarma: <değişiklik>" && git push`
- Diğer analist **`git pull`** yapınca (ya da ürün "Güncelle"/AUTO_UPDATE çalışınca) yeni sürümü alır.
- **Not:** açık bir seansta anında değişmez — yeni sürüm **bir sonraki Code seansında** geçerli olur.
- Aynı anda ikiniz aynı dosyayı değiştirirseniz git birleştirir (küçük dosya, nadir); büyük değişiklikten önce
  diğerine kısa haber + `git pull` iyi olur.

## 7) Sık sorulanlar
- **GitHub'dan indirip kopyalayacak mıyım?** Hayır — klasörün zaten var, `git pull` ile iner.
- **Chat mi Code mu?** Code. (Skill + tarayıcı sürme Code özelliğidir.)
- **Parolayı Claude girer mi?** Hayır — parola/OTP/kart hep sen. Claude hassas veriyi dokümana da taşımaz.
- **Uygulama VPN'de mi?** Kendi Chrome'unda erişebiliyorsan Claude de oradan sürer (Claude in Chrome senin
  tarayıcını kullanır).
- **Yanlış giderse?** Claude'a "dur, şu adıma dön" de; ya da ekranı yeniden okut ("read_page").
