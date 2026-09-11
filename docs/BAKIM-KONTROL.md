# Bakım & Kontrol Sistemi — Analyst Studio

> **Amaç:** Uygulamanın sağlığını periyodik denetlemek ve **yapıyı bozmadan** (regresyonsuz)
> ilerlemek için tek referans. Her iyileştirme / bug-fix / ek geliştirme bu dosyadaki
> **değişmezlere** (invariants) ve **değişiklik kontrol listesine** uymalıdır.
> İlgili: [CLAUDE.md](../CLAUDE.md) · [MIMARI.md](MIMARI.md) · [GUVENLIK-DAGITIM.md](GUVENLIK-DAGITIM.md)

---

## 1. Yapısal Değişmezler (INVARIANTS) — bunları BOZMA
Yük taşıyan sözleşmeler. Bir değişiklik bunlardan birini etkiliyorsa: önce burayı oku, testleri güncelle, docs'u güncelle.

1. **Workflow durum makinesi** (`workflow.py`): durumlar + geçişler tek kaynak. Yeni durum eklersen `_RAY[p].idx/run/turn` + `updateUI` `_setVisible` + testler güncellenir. Geçiş atlaması yapma.
2. **AI modu ikili yol** (CLI `USE_CLAUDE_CLI=true` / API `ANTHROPIC_API_KEY`): her AI çağrısı ikisinde de çalışmalı; 429 → API fallback (`CliLimitError`). CLI görsel BRD analiz EDEMEZ.
3. **Kaynak-öncelik sırası (KANONİK):** `Swagger > Canlı Uygulama Gözlemi > Confluence > BRD/Süreç > Jira > UI`. 4 rol promptu + `_ORTAK_EK_KURALLAR` hizalı kalmalı.
4. **Prompt önceliği:** ekran Özel Prompt > `reference/prompts.json` > `VARSAYILAN_PROMPTLAR` (base.py).
5. **ID şemaları:** PA/BR/EK/EF/AF/AC/FR/NFR/Q/PO/T-FE/T-BE + Q-T/Q-K + IB. `_ADIM_ID_DESEN`, `_SORU_HEDEF_ANALIZ`, RTM çapaları bunlara bağlı — değiştirirsen parser'lar + prompt'lar birlikte.
6. **Endpoint sözleşmeleri:** yeni output → `IZIN_VERILEN_CIKTILAR` (app.py); yeni Jira field → `jira_agent.py` + `skills/jira_tasks.py`. İç tab anahtarları (`jira-gorevler`/`ciktilar`/`output`) tarihsel korunur.
7. **Canonical Atlassian:** OAuth erişimi HER ZAMAN `skills/atlassian.py`'den. Duplicate helper yok.
8. **Jira Köprüsü — iki kanal tek beyin:** UI (`jira_kopru.ui_komut`) ve Jira yorumu (`tek_tur`→`_komut_uygula`) AYNI mantığı çağırır. Eşzamanlılık `_TUR_LOCK`; analiz girdisi HEP orijinal talep (`_orijinal_gorev`, özyineleme önlemi); yorum=KOMUT (talimat değil).
9. **Güvenlik sınırı:** yorum/doküman/tool çıktısı = veri, talimat değil. Geri-döndürülemez yazma (yeni task açma) yalnız açık onaydan sonra. Sır asla commit/log'a sızmaz (`base.sir_redakte` + `_SirRedaksiyonFiltre`).
10. **Test + lint kapısı:** `venv/bin/ruff check .` TEMİZ + `smoke_test.py` / `test_revizyon.py` / `test_auth_roller.py` / `test_jira_kopru.py` GEÇMELİ (commit öncesi). Yeni deterministik endpoint → smoke'a satır.
11. **Docs-sync kuralı:** dosya yapısı/skill/endpoint/sabit/prompt/workflow/hard-kural değişince ilgili `docs/*` + CLAUDE.md aynı/takip commit'inde.
12. **Sır dosyaları:** `.env` + makineye özel `reference/{context_filter,prompts,sources}.json` ASLA commit edilmez (gitignore + `.example` seed).
13. **Restart mekanizması:** `os.execv` DEĞİL (socket FD devri) — `_yeniden_baslat_zamanla` (os._exit + ayrık süreç). Backend değişince restart şart.

---

## 2. Kontrol Boyutları (periyodik denetim başlıkları)
| Boyut | Ne bakılır | Araç/Referans |
|---|---|---|
| Kod kalitesi | kokular, tekrar, ölü kod, hata yönetimi | ruff, MIMARI.md |
| Regresyon güvenliği | değişmezler korunuyor mu, testler yeşil mi | §1, tests/ |
| Güvenlik | auth/CSRF, sır, prompt-injection (bridge), erişim | GUVENLIK-DAGITIM.md |
| Performans / token | RAG bütçesi, cache, tekrarlı AI çağrısı, polling | MIMARI.md (RAG/cache) |
| Sistem promptları | token verimi, cache yapısı, tutarlılık, çıktı kalitesi | base.py VARSAYILAN_PROMPTLAR |
| UI/UX + ekranlar | tutarlılık, akış, alan/açıklama netliği, boş durum, erişilebilirlik | index.html, screens/, ds.css |
| Çıktı kalitesi | kaynak etiketleme, açık soru üretimi, spekülasyon yasağı | prompt kuralları |
| Kullanım kolaylığı | ilk-kullanım, hata mesajları (skills/hatalar), geri bildirim | — |
| Dağıtım/erişim | private repo, deploy key, auto-update | ANALIST-KURULUM.md |

---

## 3. Değişiklik Kontrol Listesi (her iş için)
**Öncesi:** ☐ İlgili değişmez(ler)i (§1) oku · ☐ etkilenen tek dosyayı hedefle (geniş tarama yok) · ☐ mevcut testleri gör.
**Sonrası:** ☐ `venv/bin/ruff check .` temiz · ☐ 4 test paketi geçer · ☐ yeni deterministik endpoint → smoke satırı · ☐ UI değişikliği → tarayıcıda doğrula + HEMEN commit · ☐ ilgili docs/CLAUDE.md güncel · ☐ commit attribution + push (testler geçince) · ☐ backend değişikliği → restart notu.

---

## 4. Periyodik Bakım Takvimi (öneri)
- **Her PR / büyük iş sonrası:** §3 kontrol listesi + ruff + testler.
- **Haftalık (hafif):** ruff + testler + boot log kontrolü + disk/telemetri sağlık (`/api/saglik`).
- **Aylık (derin denetim):** bu dosyanın §2 boyutlarını paralel ajanlarla tarat → §5'e bulgu yaz → önceliklendir → sprint'e al.
- **Sürüm öncesi:** güvenlik + regresyon + değişmez doğrulaması tam.

> Otomasyon (opsiyonel): aylık derin denetim bir zamanlanmış göreve (routine) bağlanabilir — token maliyeti olduğu için owner onayıyla açılır.

---

## 5. Denetim Bulguları & Backlog
> Her derin denetimde buraya tarih + P0/P1/P2 bulgular eklenir; kapananlar işaretlenir.
> Kaynak: paralel denetim ajanları (kod/güvenlik/performans/UI/prompt).

### 2026-09-11 — İlk kapsamlı denetim (5 paralel ajan: kod/güvenlik/performans/UI/prompt)
Genel: **ruff temiz**, hijyen güçlü, cache mimarisi 8.5/10, XML/parser tutarlı. Kritik kod-regresyonu yok.
Bulguların çoğu **Jira Köprüsü** (bu oturumun yeni kodu) + CLI-mod token'ında yoğunlaşıyor.

> **✅ UYGULANDI (A grubu, güvenli hızlı düzeltmeler):** GÜV allowlist fail-closed + accountId-only (docstring/`.env.example`/CLAUDE.md güncel);
> KOD `_mesgul_mu()` köprü `_TUR_LOCK` + soru-uygula koordinasyonu; UI global `:focus-visible`; KOD `durum.json` `son_analiz` budama (`_MAX_SON_ANALIZ=40`);
> GÜV kısa (<8) canlı-app şifre redaksiyonu (`sir_kaydet(asgari=4)`); PROMPT `kapsam_analizi_rol` numaralandırma+tekrar temizliği. (jira_kopru testi 32; ruff temiz.)
> **✅ UYGULANDI (B grubu — CLI token kazanımı):** CLI moduna sıkı RAG bütçesi (`MAX_CHARS_REF_GLOBAL_CLI=100000`,
> `_ref_global_butce`; CLI'de cache yok → her çağrının baskın girdi maliyeti düşer); köprü `_task_keywords` 12→8 + min-len 5
> (aşırı-isabet/az-alaka referans azaltıldı → daha küçük getirim). **NOT:** açık-soruları ana çağrıya BİRLEŞTİRME (P0-1)
> bilinçli ERTELENDİ — `_gorev_acik_sorular_uret` yakınsama (turlar içinde azalma) yük-taşıyan bir özellik; birleştirme
> onu + çıktı kalitesini riske atar (yapıyı bozmadan ilkesi). Ayrı, dikkatli bir turda ele alınmalı.
> **✅ UYGULANDI (B grubu — prompt tekrar temizliği):** 4 rol promptundaki (`surec/teknik/brd/kapsam_analizi_rol`)
> "BAĞLAM KULLANIMI" başlığı → "KAYNAKLARIN KULLANIMI"; kaynak-öncelik SIRASI + çakışma-kuralı verbatim tekrarları
> kaldırıldı → tek KANONİK blok (`_ORTAK_EK_KURALLAR`, gövde promptunda 1×). Per-kaynak analize-özel kullanım notları
> + BRD/Kapsam'daki ilke KORUNDU (değişmez zedelenmedi). Doğrulandı: 4 gövde promptunda "Öncelik Sırası"+"Çakışma Tespit
> Kuralı" tam 1×, eski tekrar başlığı 0. (Gerçek analiz çalıştırılmadı — kota; yapısal doğrulama yapıldı.)
> **✅ UYGULANDI (P2 — kilit yarışı + watermark):** `/api/sorular/uygula` arka plan worker'ı artık `_revizyon_lock`'u
> tutuyor → `/api/adim/duzelt` ile aynı `output/*.md`+`output/revizyon/` oturumuna YARIŞMA yok (adim/duzelt non-blocking →
> 409; circular-wait yok → deadlock yok). Köprü döngüsü JQL'e **watermark** (son taramadan geçen süre + 2dk örtüşme, `pencere`
> ile sınırlı) → steady-state'te her turda tüm task yorumlarını çekmek yerine yalnız yeni-güncellenen task'lar → çok daha az Jira REST.
> **✅ UYGULANDI (P2 — eşzamanlılık + poll):** `_kopru_isler` insert+trim `_kopru_isler_lock` altında (eşzamanlı
> POST'ta "dict changed size" yarışı kapandı). `workflow_state()` poll HOT PATH artık durum dosyasını TEK okuyor
> (`_stale_workflow_kurtar(ozet)` ön-okunmuş özeti alır; yalnız nadir sıfırlamada yeniden okur) — poll başına 2→1 okuma.
> **KALAN (P2 / tasarım — dikkatli tur):** `gorev_teknik_analiz` ~%30 kısaltma (prompt-kalite riski, gerçek testle),
> `/api/sorular/*` admin-gate (AUTH-sunucu modu; naif ekleme analist işlevini kırar), ilk-tarama eski yorum (davranış kararı),
> UI tasarım (12 öneri), açık-soru birleştirmesi. → BAKIM-KONTROL sonraki turlarda.

### 2026-09-11 — Canlı uçtan-uca doğrulama (gerçek analiz, kota harcandı)
Restart sonrası yeni kod (`71db3d4`) canlı doğrulandı: **(1) Jira Köprüsü** `/analyst_agent analiz` (MBSTRADE-1249) — komut algılandı, CLI+canlı gözlem (~6 dk / 29 tur), gövdeye yazıldı (orijinal talep ×1 + teknik analiz ×1, **çift-başlık yok**), açık sorular ayrı yorum, scope doğru, task-keyword RAG, kilit+döngü koruması+fail-closed+CSRF — hepsi çalıştı. **(2) Süreç Analizi** (`ORNEK-DOKUMAN.md`) — onay kapısına geldi, **gömülü Q&A canlı çalıştı** (5 UI + 1 API cevabı işlendi → gövdeye `[K: Analist cevabı]` → sorular 8→2 yakınsadı; uydurma yok). Analistin (bir analist) "açık sorular tek tek görünmüyor" sorunu çözülmüş — teyit edildi.

> **✅ UYGULANDI (canlı-doğrulama bulguları):**
> **[Bulgu 1 — gözlem uyarısı false-positive]** `_api_cagri_cli` sessiz-düşüş sezgisi (`base.py`) HERHANGİ "playwright/browser" reddini `_browser_reddi` sayıyordu → izin listesi DIŞINDAKİ yardımcı araç (`browser_evaluate`/`browser_take_screenshot`/`Bash`) reddi de tetikliyordu; çekirdek gözlem 29-57 tur başarıyla yapılsa bile `.gozlem-durum.json yapildi:false` + yanlış uyarı. **Fix:** yalnız `LIVE_APP_ALLOWED_TOOLS` içindeki (izinli) aracın reddi gerçek sorun sayılır; `num_turns<=1` guard'ı korundu. (`browser_evaluate` bilinçli izin-dışı — keyfi JS güvenliği; allowlist genişletilmedi.)
> **[Bulgu 2 — ajan ön-söz sızıntısı]** Canlı-gözlem sonrası ajan rapor ÖNCESİ düşünme cümlesini (`"I have sufficient focused observation... Now I'll produce the report."`) `result`'ın başına sızdırıp markdown çıktıya karıştırıyordu. **Fix:** `_onsoz_kirp` — yalnız ilk markdown-yapısal satırdan önceki kısa (<600, `{` yok) düz-metin ön-sözü kırpar; canlı-gözlem yolunda uygulanır; JSON/uzun gövde korunur. Birim testi 4 senaryo yeşil.

> **KALAN (canlı-doğrulamada keşfedilen — backlog):**
> **[Bulgu 1b — hedefli soru-uygulama isabetsiz]** `_sorulari_hedefli_uygula` → `revizyon_ai.bolum_bul(metin, bagli_id)` süreç analizinde tüm `bagli_id`'ler (PA-003, BR-006, EF-001…) için başarısız oldu → `hedefli:0, tam_uretim:6` (hepsi tam-regenerasyona düştü). Sonuç DOĞRU ama pahalı (tüm doküman yeniden yazılır + ön-söz yeniden sızabilir). `bolum_bul` süreç-analizi ID/başlık deseniyle hizalanmalı (teknik analizde çalışıyor). Dikkatli tur — çıktı kalitesini bozmadan.

#### P0 — önce bunlar
- **[GÜV] Allowlist varsayılan AÇIK + onay aynı güvenilmez kanaldan** (`jira_kopru.py:197`, `.env.example`).
  `JIRA_KOPRU=true` + allowlist boş ise: konfigüre projede yorum yazabilen HERHANGİ biri `analiz` (açıklamayı ezer)
  ve `ilişkili-aç→onayla` (task açar) tetikler; `onayla` da yorumdan geldiğinden saldırgan kendi taslağını onaylar.
  **Fix:** fail-closed (allowlist boşsa işleme) + yalnız `accountId` eşleşmesi (`displayName` taklit edilebilir, P1).
  *(Pilotta allowlist zaten sana kısıtlı → şu an kapalı; ama varsayılan güvensiz.)*
- **[GÜV] `analiz/cevap/düzelt/güncelle` DESCRIPTION'ı onaysız yazıyor** (`jira_kopru.py:377`). Bilinçli tasarım
  (kullanıcı #1 geri bildirimi) ama modül docstring'i "alanlara dokunmaz" diyor → **bayat docstring** + orijinal
  yalnız kırılgan regex ile korunuyor. **Fix:** docstring'i güncelle; orijinal talebi regex yerine ayrı sakla; risk P0-allowlist ile kapanır.
- **[UI] Klavye odağı görünmüyor** (`index.html` `.btn`/`.nav-item` — `:focus-visible` YOK). WCAG 2.4.7.
  **Fix:** global `.btn:focus-visible,.nav-item:focus-visible,[role=button]:focus-visible{outline:2px solid var(--accent);outline-offset:2px}`.
- **[UI] "çalışıyor=kırmızı" ↔ "hata=kırmızı" çakışması.** **Fix:** running=indigo/mavi+pulse, kırmızı yalnız hata.
- **[PERF-CLI] Açık sorular ayrı çağrı → CLI'de 2 tam-model çağrısı** (`jira_gorevleri.py:963/876`). `MODEL_HAFIF`
  CLI'de yok sayılır. **Fix:** ana teknik analiz + açık soruları TEK birleşik çağrıda üret (`api_cagri_kapanisli`
  `</acik_sorular>` deseni) → CLI çağrısını yarıya indir.
- **[PERF-CLI] CLI'de prompt-cache yok → RAG bütçesi (140K karakter) her çağrıda tam ödeniyor** (`base.py:161`).
  **Fix:** CLI modunda `MAX_CHARS_REF_GLOBAL` varsayılanını düşür (~90–100K) ve/veya keyword filtresini sıkılaştır.

#### P1 — önemli
- **[KOD] `_mesgul_mu()` köprü AI turunu + cevap-uygulamayı görmüyor** (`app.py:1915`) → çalışan AI sırasında
  otomatik güncelleme/disk temizliği kesebilir/yarışabilir. **Fix:** `_mesgul_mu`'ya `_TUR_LOCK.locked()` + `_sorular_uygula_durum["calisiyor"]` ekle.
- **[KOD] `/api/adim/duzelt` (`_revizyon_lock`) ↔ `/api/sorular/uygula` (`_sorular_uygula_lock`) yarışı** aynı çıktıya yazar. **Fix:** ortak kilit.
- **[GÜV] Yazar eşleşmesi `displayName` ile de kabul** (spoofable) → yalnız accountId. **[GÜV] arg prompt-injection** (yorum→model→kalıcı alan/issue). **[GÜV] tetikleyicide hız/maliyet sınırı yok** (token DoS). → hepsi allowlist fail-closed + accountId ile büyük ölçüde kapanır.
- **[PERF] Referans dosyaları analiz başına 2× okunuyor/parse** (`_filtre_metni_oku` önbeleksiz, PDF çift parse). **Fix:** `(path,mtime)` memoization.
- **[PERF] `_TUR_LOCK` uzun AI çağrısı boyunca bloklu** (UI-UI serileşme). **Fix:** key-bazlı kilit veya kuyruk + "sırada" bildirimi + `acquire(timeout=)`.
- **[PERF] `GOREV_PARALEL=3` CLI'de 429'u hızlandırır.** **Fix:** CLI modunda varsayılan 2.
- **[PROMPT] `kapsam_analizi_rol` bozuk numaralandırma + "Canlı uygulama gözlemi" 2×** (`base.py:960`). **Fix:** tekilleştir.
- **[PROMPT] Kaynak-öncelik listesi aynı promptta 3× tekrar** (rol + analiz + EK KURALLAR) → drift + token. **Fix:** tek kanonik blok (`_ORTAK_EK_KURALLAR`), rol promptları 1 satır atıf.
- **[PROMPT] ID şeması ↔ `_SUREC_ID_DESENI` denetçi uyumsuzluğu** (`base.py:1484`; A-/AF-/IB- denetlenmiyor, EK- yanlış eşleşir). **Fix:** hizala.
- **[UI] Revizyon ekranı tamamen bespoke** (`.rz-*`, sistem dışı görünüyor); **boş durumlar 3 farklı**; **Köprü input'ları taşma + hardcode proje**; **onay kapısı yoğun + yeşil primary** (aksiyon=indigo olmalı); **Task Analizi paneli aşırı yoğun**.

#### P2 — iyileştirme (backlog)
- **[KOD]** `durum.json` `son_analiz`/`taslaklar` sınırsız büyür (buda); `_kopru_isler` kilitsiz; JQL proje kaçışı yok; `_onaySoruKart` ölü dal; `_ADIM_ID_DESEN` `Q-T` kapsamıyor; ilk-tarama pencere içi eski yorumları işler.
- **[GÜV]** kısa (<8) canlı-app şifresi log redaksiyonuna kaydolmuyor; `/api/sorular/*` admin-gate yok (yalnız AUTH-sunucu modu).
- **[PERF]** `_task_keywords` gevşek alt-dize eşleşmesi (6-8'e indir, `\b`); köprü döngüsü watermark'sız tüm yorumları çeker; `workflow_state` poll başına 2× okunur; MIMARI.md cache-breakpoint iddiası (2 breakpoint gerçekte) — belge düzeltmesi.
- **[PROMPT]** `_ORTAK_EK_KURALLAR` tek-beden BRD/Kapsam'a da ekleniyor (whitelist/traceability ayır); traceability tablosu IB/Q eksik + T-BE hane; teknik 3 çağrı kaynağı cache'siz yeniden gönderir; `gorev_teknik_analiz` ~%30 kısaltılabilir; `MAX_TOKENS_BRD_CMB=9000` sıkı olabilir (ölç).
- **[UI]** teal renk kalıntısı (`ds.css:38`); iki ikon sistemi; dark `--text3` kontrast; geri bildirim 3 kanal; statik breadcrumb; yaygın inline-style + ~11 tek-kullanım font boyutu; komut paleti yalnız isimle eşleşiyor.

#### Tasarım önerileri (UI — gerçek ürün örnekli, backlog)
1. Tek boş-durum bileşeni her yerde (Linear/Height) · 2. Kalıcı workflow stepper (Stripe/Linear) ·
3. Onay kapısını "review" yerleşimi + tek primary (GitHub PR merge kutusu) · 4. running=indigo+pulse (Vercel/Linear) ·
5. Görev listeleri gerçek tablo — kolon/sıralama/sticky (Jira/Linear/Height) · 6. Task Analizi progressive disclosure (GitHub/Notion) ·
7. Zengin komut paleti — grup/kısayol/son kullanılan (Linear ⌘K/Raycast) · 8. Tek kart+buton ailesi (`.panel`+`.btn` kanonik) ·
9. Tipografi/spacing token ölçeği (Primer/Tailwind) · 10. Onboarding checklist kartı (Linear/Vercel) ·
11. Skeleton yükleme (Linear/Vercel) · 12. Bağlamsal breadcrumb + "sıra sende" vurgusu.

#### Doğru çalıştığı doğrulanan (aksiyon YOK)
ruff temiz · CSRF/Origin sağlam · şifre maskeleme + stdin (ps'de görünmez) · döngü koruması (ROBOT_IMZA+dedup+`_TUR_LOCK`) ·
gitignore sır kapsamı · iki-kanal köprü tekilliği (`ui_komut`≡yorum yolu) · güncelle 0-token reuse · düzelt RAG kurmaz ·
çıktı önbelleği CLI-model'i anahtara katar · getirim bütçesi tavanı · XML/parser hizası.
