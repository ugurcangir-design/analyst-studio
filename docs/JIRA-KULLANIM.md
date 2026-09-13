# Jira Köprüsü — Hızlı Kullanım & SSS (Ekip Testi Tek-Sayfa)

> Jira'yı web-chat gibi kullan: bir task'ın **yorumuna** `/analyst_agent <komut>` yaz, agent
> analiz edip sonucu Jira'ya geri yazsın. Bu sayfa **ekip testi** için hızlı referanstır.
> Tam kullanıcı kılavuzu: uygulama içi **?** → "18. Jira Köprüsü". Tasarım/mimari:
> `docs/KOPRU-VE-BILDIRIMLER.md` · `docs/MIMARI.md`.

---

## 30 saniyede model (ÖNEMLİ)

- **Her analist KENDİ agent'ını kendi bilgisayarında çalıştırır** (kendi Jira hesabıyla).
- **Bir agent yalnız KENDİ sahibinin komutlarını işler.** Başkasının / agent'ı olmayan birinin
  komutu senin için **görünmez**dir.
- Agent'ı olmayan biri komut yazarsa → **hiçbir şey olmaz**, yorum Jira'da öylece kalır (tasarım).

---

## Kurulum — analist HİÇBİR ŞEY yazmaz

Jira Köprüsü **güncelleme (Güncelle/pull) ile açık gelir** — `.env` düzenlemenize gerek yok.
Varsayılan: köprü **açık**, proje **MBSTRADE**, yetki **kendi Jira hesabınıza** kilitli (self-scope).

1. **Güncelleme → Yeniden Başlat** (varsa güncel sürümü çeker).
2. Jira'ya OAuth ile bağlan (Ayarlar → Atlassian) — zaten bağlıysanız atlayın.
3. Jira Köprüsü ekranında **"Jira bağlı · son tarama HH:MM"** yazısını görün → hazırsınız.

> **Ayar değiştirmek (opsiyonel, owner):** proje eklemek/çıkarmak veya köprüyü kapatmak için
> `.env` DEĞİL, `reference/jira_kopru.json` dosyasını düzenleyip Yeniden Başlat. (Bu dosya güncelleme
> ile gelir, git'te izlenmez.) `yazar_allowlist` boş kalırsa agent kendi Jira hesabınıza kilitlenir →
> yalnız **sizin** komutlarınız işlenir; elle accountId listesi yalnız tek merkezi agent tüm ekibe
> hizmet ettiğinde gerekir.

---

## Komutlar — hangisi ne işe yarar

Bir Jira task'ının **yorum** satırına yaz:

| Komut | Ne yapar |
|---|---|
| `/analyst_agent analiz` | Task'ı teknik analiz eder, sonucu **task açıklamasına (gövde)** yazar (orijinal talep korunur); **açık sorular ayrı yorum** olarak gelir. |
| `/analyst_agent analiz <talimat>` | Talimatlı analiz — örn. `analiz sadece BE tarafını değerlendir`. |
| `/analyst_agent cevap <cevaplarınız>` | Açık sorulara cevap ver → analiz cevaplara göre **yeniden üretilir**, sorular yakınsar (azalır), gövde güncellenir. |
| `/analyst_agent düzelt <talimat>` | Yalnız ilgili kısmı düzeltir (diğer bölümler korunur). |
| `/analyst_agent güncelle` | Son analizi gövdeye yeniden yazar (taze ise 0-token). |
| `/analyst_agent ilişkili-aç` | İlişkili YENİ task **önerir (taslak)** — henüz açmaz. |
| `/analyst_agent onayla` | Bekleyen taslağı (ilişkili task) **uygular** → Jira'da açar + bağlar. |
| `/analyst_agent iptal` | Bekleyen taslağı iptal eder. |
| `/analyst_agent yardım` | Komut listesini yorum olarak yazar. (`/analyst_agent` tek başına da yardım verir.) |

> Türkçe/İngilizce eşanlamlar çalışır: `analyze`→analiz, `cevapla/yanıt`→cevap, `fix/revize`→düzelt,
> `approve`→onayla, `yardım/help/?`→yardım.

---

## Adım adım akış — hangi adımda ne olur

1. **Yorum yaz:** task'a `/analyst_agent analiz`.
2. **Agent tarar:** ~60 sn'de bir kendi agent'ın Jira'yı tarar (webhook yok, polling). Komutu bulur.
3. **Analiz üretir:** CLI + (varsa) canlı uygulama gözlemi + task anahtar kelimeleriyle RAG. Birkaç dakika sürebilir.
4. **Gövdeye yazar:** sonuç task **açıklamasına** yazılır — `## 📌 Orijinal Talep` (senin talebin korunur) + `## 🤖 Teknik Analiz`.
5. **Açık sorular:** ayrı bir **yorum** olarak listelenir (Q-T-001…), her biri önem + beklenen yanıt ile.
6. **Cevapla:** `/analyst_agent cevap Q-T-001: … Q-T-002: …` → analiz güncellenir, cevaplanan sorular düşer.
7. **İlişkili task (opsiyonel):** `/analyst_agent ilişkili-aç` → öneri taslağı → `/analyst_agent onayla` → gerçek task açılır + bağlanır.
8. **Bildirim:** analiz bitince kendi bilgisayarında masaüstü bildirimi alırsın (aşağı bak).

> Alternatif: aynı işi uygulama içi **Jira Köprüsü** ekranından da yapabilirsin (aynı beyin) —
> açık soruları oradan tek tek cevaplayıp "Cevapla & Devam Et" diyebilirsin.

---

## Bildirimler (kendi bilgisayarında)

- **Süreç/teknik analiz tamamlandı** → *«doküman» süreç analizi tamamlandı — N açık soru. Cevaplayıp devam edebilir veya teknik analize geçebilirsiniz.*
- **Jira bağlantısı koparsa** → *Jira köprüsü — bağlantı sorunu…* (Jira'ya yazamadığımızda).
- **Agent kapalıyken komut girdiysen** → agent açılınca *çevrimdışıyken N komutun işlendi.*
- Kapatmak için `.env` `BILDIRIM=false`. Bildirimler **yereldir** (veri makineden çıkmaz).

---

## SSS — "neden yanıt gelmedi?"

**S: Komut yazdım, hiçbir şey olmadı. Neden?**
En olası sebepler:
1. **Agent'ın açık değil** → hiçbir şey işlenmez (kapalı program yanıt veremez). Aç + Yeniden Başlat.
2. **Komut senin hesabından değil** (veya self-scope başkasının komutu) → tasarım gereği sessiz.
3. **Proje `JIRA_KOPRU_PROJELER`'de değil** → taranmaz.
4. **Yorum çok eski** (tarama penceresi dışında) → işlenmez. Yeni bir yorum yaz.
5. **Jira bağlantısı kopuk** → masaüstü bildirimi gelir; Jira Köprüsü ekranında "⚠ bağlantı yok" görürsün.

**S: Başkasının komutu benim agent'ımı tetikler mi?** Hayır — agent yalnız kendi sahibinin komutlarını işler.

**S: Agent'ı olmayan biri komut yazarsa ne olur?** Hiçbir şey — yorum düz bir Jira girdisi olarak kalır, kimseye mesaj gitmez.

**S: Yanıt kimin adına görünüyor?** Agent'ın bağlı olduğu Jira hesabı adına (yani senin). Bu yüzden başka analistlerin senin task'ına yazdığı komutları sen değil, onların kendi agent'ı işler.

**S: "Bilinmeyen komut" aldım.** Komut yanlış yazılmış → `/analyst_agent yardım` ile listeye bak.

**S: Analiz açık soru üretti, hepsini cevaplamak zorunda mıyım?** Hayır — cevaplamadıkların açık kalır; `cevap` ile istediğin kadarını cevaplarsın, analiz yakınsar.

**S: Agent kapalıyken girdiğim komutlar kaybolur mu?** Agent açılışta son pencereyi tarar (catch-up) → pencere içindekiler işlenir + bildirim gelir. Çok eski (pencere dışı) komutlar kaçar; yeni bir yorum yaz.

**S: Analiz task açıklamasını eziyor mu?** Hayır — orijinal talebin `## 📌 Orijinal Talep` altında korunur; analiz altına eklenir.

---

## Güvenlik notları (ekip)

- Yalnız **kendi** komutların işlenir (`accountId` ile; görünen ad taklidi işe yaramaz).
- Yeni task açma **yalnız `onayla` sonrası** olur (kendiliğinden task açılmaz).
- Bildirimler ve analiz verisi **yereldir**; analiz sırasında yalnız Claude API çağrıları dışarı gider.
