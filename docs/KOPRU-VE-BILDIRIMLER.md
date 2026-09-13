# Jira Köprüsü Yetki Davranışı & Bildirimler — Tasarım ve Uygulama Planı

> **Durum: TASARIM / PLAN — henüz UYGULANMADI.** Bu doküman ekip testi öncesi hedeflenen
> davranışı ve maddelenmiş yapılacakları tanımlar. Kod değişikliği ayrı commit'lerle gelecek.
> İlgili modüller: `skills/jira_kopru.py`, `app.py` (`_jira_kopru_dongusu`), `workflow.py`, `templates/index.html`.

---

## 0. Dağıtım modeli (KARAR)

**Her analist KENDİ agent'ını kurar** (per-user). Kendi bilgisayarı, kendi Jira OAuth bağlantısı,
kendi Jira `accountId`'si. Merkezi tek bir sunucu yoktur.

**Temel ilke:** *Bir agent yalnız KENDİ sahibinin komutlarını işler.* Başka herkesin (agent'ı
olmayan veya farklı bir analist) komutu, o agent için **görünmez ve sessizdir**. Bu ilke hem
İstek 1'i (yetkisize sessizlik) hem de çoklu-agent çakışmasını tek hamlede çözer.

---

## 1. Yetki & Sessizlik davranışı  ·  *(İstek 1)*

### Hedef
- Yalnız **agent–Jira entegrasyonu olan** kullanıcı yanıt alır ve işlem yapabilir.
- Entegrasyonu olmayan / farklı bir kullanıcı komutu girerse **hiçbir agent yanıt vermez**;
  yorum Jira'da **düz bir giriş** olarak kalır. Hiçbir hata/red mesajı yazılmaz.

### Kurallar
1. **Kendi kimliğine kilitlen (self-scope).** Agent, allowlist boşsa **fail-closed** kalmaya devam
   eder AMA per-user kurulumda kullanılabilirliği artırmak için: agent açılışta kendi OAuth
   kimliğini (`GET /rest/api/3/myself` → `accountId`) çözüp **etkin allowlist = [kendi accountId]**
   yapar. Böylece analist elle allowlist girmeden yalnız *kendi* komutlarını işler.
   *(Merkezi/çok-kullanıcılı kurulum isteyen owner, `JIRA_KOPRU_YAZAR_ALLOWLIST` ile elle override
   edebilir — o zaman listede olan herkes işlenir.)*
2. **Yetkisiz yazar → tam sessizlik.** Yorum yazarı etkin allowlist'te değilse: komut **sessizce
   atlanır**, Jira'ya **hiçbir yanıt yazılmaz**. *(Mevcut `⛔ '<isim>' bu komutu çalıştırma
   yetkisinde değil` yorumu KALDIRILIR.)* Yorum, işlenen-id kaydına da **eklenmez** — çünkü başka
   bir analistin agent'ı onu (kendi sahibininse) işleyebilmeli.
3. **Çakışma yok.** A'nın agent'ı yalnız A'nın `accountId`'li yorumlarını işler; B'nin agent'ı
   B'ninkileri. Aynı yorum iki agent tarafından işlenmez, çift Jira yanıtı oluşmaz.
4. **Güvenlik korunur.** `accountId`-only eşleşme (displayName taklit edilebilir → yetkiye sokulmaz),
   fail-closed, döngü koruması aynen kalır. Sessizlik sayesinde agent'ın varlığı dışarıya sızmaz.

### Sonuç (gözlemlenen davranış)
| Kim | Ne olur |
|---|---|
| Entegrasyonu olmayan / farklı kullanıcı | **Sessizlik.** Yorum Jira'da kalır, hiçbir agent yanıtlamaz. |
| Analistin **kendi** komutu (agent'ı açık) | Kendi agent'ı işler, yanıt kendi Jira hesabından döner. |
| Analistin komutu ama **kendi agent'ı kapalı** | O an sessizlik → agent açılınca **catch-up** (§2.2). |

---

## 2. Bildirimler  ·  *(İstek 2 + analiz yaşam döngüsü)*

**Mekanizma:** macOS yerel bildirimi — `osascript -e 'display notification "…" with title "…"'`
(harici bağımlılık YOK, 0 token, veri makineden çıkmaz). `.env` `BILDIRIM=true/false` ile kapatılır.
Bildirim metni **redaksiyonlu** (API anahtarı/şifre/PII içermez — mevcut `sir_redakte` kuralı).
Windows bildirimi (PowerShell/`plyer`) **sonraki faz** olarak işaretlendi.

### 2.1 Analiz yaşam döngüsü bildirimleri  ·  *(YENİ — en yüksek değer)*
Analist bir analiz başlatıp başka işe geçtiğinde, iş bitince kendi makinesinde bildirim alır.
Her analiz kendi makinesinde çalıştığı için bildirim **doğal olarak yerel**dir.

| Olay | Örnek bildirim metni |
|---|---|
| **Süreç analizi tamamlandı** | *«{doküman}» süreç analizi tamamlandı — {N} açık soru çıkarıldı. Açık soruları cevaplayarak devam edebilir veya teknik analiz adımına geçebilirsiniz.* |
| **Teknik analiz tamamlandı** | *«{doküman}» teknik analizi tamamlandı — {N} açık soru. İnceleyip onaylayın; Jira'da oluşturmaya hazır.* |
| **Analiz hata verdi** | *«{doküman}» analizi tamamlanamadı: {insanlaştırılmış hata}. Ayrıntı için uygulamayı açın.* |

- **Tetik:** workflow durumu `onay_bekleniyor` / `teknik_onay_bekleniyor` / `hata` durumuna
  **GEÇİŞTE** (transition) **bir kez** ateşlenir — her poll'de değil (dedup: son bildirilen durum
  saklanır, aynı duruma tekrar bildirim gitmez).
- **Açık soru sayısı:** `/api/sorular` taze-filtreli sonucundan alınır (bu oturuma ait sorular).
- **{doküman}:** yüklenen girdi dosyasının adı (yoksa "Analiz").

### 2.2 Jira köprü bildirimleri  ·  *(İstek 2)*
| Durum | Jira yanıtı | Masaüstü bildirimi |
|---|---|---|
| **Tanımsız komut** (agent açık+bağlı) | ✅ *«❓ Bilinmeyen komut: `x`. `/analyst_agent yardım`»* (mevcut) | — |
| **Komut başarıyla işlendi** | ✅ Jira yanıtı (mevcut) | opsiyonel: *«{key} analiz edildi»* |
| **Jira bağlantı hatası** (agent açık, Jira erişilemez) | ❌ (bozuk kanal Jira'nın kendisi) | ✅ *«Jira bağlantısı koptu — komutlar işlenemiyor. Bağlantıyı yenileyin.»* |
| **Açılışta kaçan komut** (agent kapalıydı) | ✅ şimdi işlenir + Jira yanıtı | ✅ *«Çevrimdışıyken {N} komutunuz işlendi.»* |
| **Agent TAMAMEN kapalı** | ❌ imkansız | ❌ anlık imkansız → açılışta catch-up (yukarı) |

**Açılış catch-up:** agent açıldığında köprü aktifse, `pencere` kadar geriye bir tarama yapıp
sahibinin çevrimdışıyken girdiği **kendi** işlenmemiş komutlarını bulur → işler + tek bir özet
bildirim gösterir. Böylece "agent kapalıyken girdim, hiç işlenmedi" durumu ortadan kalkar.

### 2.3 Fiziksel sınır (dürüst)
Agent **tamamen kapalıyken anlık bildirim İMKANSIZDIR** — kapalı bir süreç ne Jira'ya ne
masaüstüne yazabilir. Tek gerçekçi çözüm yukarıdaki **açılış catch-up**'tır. Ekip bunu bilmeli.

---

## 3. Köprü durum göstergesi (uygulama-içi)

Kullanıcı, agent'ına güvenmeden önce canlı olduğunu **görebilmeli**. `GET /api/jira-kopru/durum`
zaten var; şu alanlar netleştirilir ve üst-barda/köprü ekranında küçük bir rozetle gösterilir:
- **aktif mi** · **Jira bağlı mı** (son `myself`/tarama başarılı mı) · **son tarama zamanı** ·
  **son hata** (varsa). Yeşil "bağlı · son tarama 12:40" / kırmızı "Jira bağlantısı yok".

---

## 4. Yapılacaklar — tek tek (öncelikli)

| # | Madde | Ne yapılır | Nerede | Efor | Risk |
|---|---|---|---|---|---|
| 1 | **Yetkisize sessizlik** | Yetkisiz-yazar dalındaki `jira_yorum_ekle(⛔…)` çağrısını kaldır; işlenen-id'ye EKLEME (başka agent işleyebilsin); `atlanan` sayacı kalsın | `jira_kopru._tek_tur_ic` | Küçük | Düşük · testle |
| 2 | **Self-scope** | Allowlist boşsa OAuth `myself.accountId`'e otomatik kilitle (fail-closed korunur; elle allowlist override) | `jira_kopru.ayarlar`/`_tek_tur_ic` | Orta | Orta · güvenlik-testi |
| 3 | **Bildirim altyapısı** | `skills/bildirim.py`: `gonder(baslik, metin)` → `osascript`; `BILDIRIM` env; redaksiyon; 0-token; hata-yutar (bildirim başarısız olsa akış bozulmaz) | yeni modül | Küçük | Düşük |
| 4 | **Yaşam döngüsü bildirimi** | Workflow geçişini yakala (onay/teknik-onay/hata) + dedup → §2.1 mesajları (açık soru sayısıyla) | `app.py` (workflow-state gözlemi) + `skills/bildirim.py` | Orta | Orta |
| 5 | **Köprü bildirimleri** | Jira bağlantı hatası → bildirim; açılış catch-up → işle + özet bildirim | `_jira_kopru_dongusu`/`_jira_kopru_baslat` | Orta | Orta |
| 6 | **Durum göstergesi** | `/api/jira-kopru/durum`'a `bagli`/`son_hata` ekle + UI rozet | `app.py` + `index.html`/`kopru.html` | Küçük | Düşük |
| 7 | **Test + doküman** | `test_jira_kopru`: silent-skip + self-scope assert'leri; §5 tablosunu ekip test rehberine koy; CLAUDE.md güncelle | `tests/` + `docs/` | Küçük | Düşük |

**Öneri sıra:** 1 → 3 → 4 (en değerli: analiz-bitti bildirimi) → 2 → 5 → 6 → 7.
Her madde ayrı commit + `ruff` + test; ekip testine kadar hepsi tamamlanmalı.

---

## 5. Ekip için: beklenen davranış tablosu (test rehberi)

Test edenlerin "neden yanıt gelmedi?" sorusunu önlemek için — bu tablo *hedeflenen* davranıştır:

| Senaryo | Beklenen sonuç |
|---|---|
| Entegrasyonu olmayan biri `/analyst_agent analiz` yazdı | **Sessizlik** (tasarım gereği). Yorum Jira'da kalır. |
| Analist kendi komutunu yazdı, agent'ı açık | İşlenir; yanıt kendi Jira hesabından gelir. |
| Analist komut yazdı, kendi agent'ı **kapalıydı** | O an sessizlik; agent **açılınca** işlenir + "çevrimdışıyken işlendi" bildirimi. |
| Analist **tanımsız** komut yazdı (agent açık) | Jira'ya *«❓ Bilinmeyen komut… yardım»* yanıtı. |
| Analistin agent'ı açık, **Jira bağlantısı kopuk** | Jira'ya yazılamaz → **masaüstü bildirimi** "Jira bağlantısı yok". |
| Analist süreç/teknik analizi bitirdi | **Masaüstü bildirimi**: "«X» tamamlandı — N açık soru…" |
| Analist analizi bitti, **hata** aldı | Masaüstü bildirimi + uygulamada hata kartı. |

---

## 6. Güvenlik & gizlilik

- **Bildirimler yereldir** — hiçbir veri kullanıcının makinesinden çıkmaz (yalnız macOS Bildirim
  Merkezi'ne yerel mesaj).
- **accountId-only** yetki + **fail-closed** aynen korunur; self-scope bunu gevşetmez (yalnız
  sahibinin kendi kimliğine daraltır).
- **Sessizlik**, agent'ın varlığını yetkisiz kullanıcılara sızdırmaz (bilgi ifşası önlenir).
- **Bildirim metni redaksiyonlu** — sır/şifre/anahtar içermez; doküman adı + sayılarla sınırlı.

## 7. Bilinen sınırlar & kararlar

- **Agent-off anlık bildirim yok** → açılış catch-up ile telafi (§2.3).
- **Windows bildirimi** sonraki faz (şimdilik macOS `osascript`).
- **Çoklu sekme:** bildirim süreç (agent) bazlıdır, sekme bazlı değil — bir analiz bitince tek
  bildirim, kaç sekme açık olursa olsun.
- **Token maliyeti:** catch-up yalnız açılışta bir tarama; bildirimler 0 token (deterministik).
