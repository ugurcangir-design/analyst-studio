# Kota Optimizasyon Planı — agent tüketim taraması (2026-10-19)

> Durum: **Faz 0 + 1 + 2 + 3 UYGULANDI (2026-10-19, owner onaylı)**; Faz 4/5 ölçümden (1 hafta Kullanım Raporu) sonra. Bkz. §7 (Faz 2-3 uygulama notu + Opus 5.5 karşılaştırması). Etki ölçümü: Kullanım Raporu → "Aşama bazlı tüketim". İlke: **doğruluk/kalite kaybı YOK** —
> her madde için "kalite nasıl korunuyor" satırı var; kaliteyi düşürebilecek seçenekler ayrı başlıkta, karar owner'da.

## 1. Ölçülen gerçek (kullanım kayıtları + CLI MCP logları)

| Kanıt | Değer | Anlamı |
|---|---|---|
| Tek süreç analizi çağrısı (canlı gözlemli, Opus) | girdi 114 · çıktı 34.6k · **cache_yaz 103k · cache_oku 5.9M** · 571 sn | Tek `claude -p` çağrısı, agentik döngüde her araç turunda ~100k+ token'lık bağlamı yeniden okuyor; 5.9M okuma = ~55 tur × ~105k |
| Teknik analiz (4 çağrı) | cache_oku 111k · cache_yaz 173k · çıktı 39.8k | Gözlemsiz çağrılar makul; büyük kalem gözlem döngüsü |
| Sohbet turu (gözlemsiz) | cache_yaz ~110k / tur | Her tur 110k'lık sabit blok (referans + few-shot + domain) yeniden yazılıyor; CLI'da çağrılar arası cache YOK |
| Canlı gözlem oturumları (16 Ekim–19 Ekim) | 2–34 araç çağrısı / oturum, tipik 17–34 | Her araç çağrısı = bağlamın yeniden okunması; `browser_snapshot` erişilebilirlik ağacı tek başına 10–40k token |
| Task analizi olayları (18 kayıt) | **token = 0** | Task Analizi'nde token ölçümü KAYIT EDİLMİYOR → en çok kullanılan akış görünmez (ölçüm boşluğu) |
| Model | `CLAUDE_CLI_MODEL=claude-opus-4-8` | CLI modunda `_api_cagri(model=…)` parametresi **YOK SAYILIYOR**: açık sorular (`MODEL_HAFIF`=Haiku niyetli), giriş testi, kabul listesi, soru sınıflandırma, düzeltme — HEPSİ Opus'ta çalışıyor |

**Sonuç:** kotayı dolduran, analiz metninin kendisi değil; (1) canlı gözlem döngüsünün her turda **tam analiz
bağlamını** (referans 100k char + few-shot 2×16k char + domain + BFF raporu + task) yeniden okuması, (2) bu döngünün
FE+BE ayrımında ve "Cevapları İşle"de **baştan tekrarlanması**, (3) ikincil çağrıların da Opus'ta koşması.

## 2. Bir Task analizinin (FE+BE Ayrı, canlı hedefli) bugünkü çağrı zinciri

| # | Adım | Çağrı | Döngü? | Bağlam boyutu |
|---|---|---|---|---|
| 0 | Giriş kapısı (saatte 1) | 1 | 3–8 tur | küçük |
| 1 | BFF keşfi (7 günde 1 / ekran) | 1 | 20–60 tur | küçük (canlı görev) |
| 2 | **BE analizi** | 1 | **10–35 tur** | **~40k token** (referans+few-shot+domain+BFF+canlı) |
| 3 | BE açık sorular | 1 | — | analiz + task |
| 4 | BE öz-çözümleme | 1 (+1 gözlem döngüsü) | 5–15 tur | orta |
| 5 | BE düzeltme (çözülenler) | 1 | — | analiz in/out |
| 6–9 | **FE analizi** + sorular + çözümleme + düzeltme | 4 (+1 döngü) | **10–35 tur** | ~45k (BE sözleşmesi dahil) |
| 10 | "Cevapları İşle" (her tur) | 2 katman × tüm zincir | **yeniden gözlem** | tam |
| 11 | Akışı Kapat / Kabul Kontrolü / Mockup (isteğe bağlı) | 1–2 | döngü | orta |

Toplam: 10–14 çağrı, 3–5 agentik döngü; döngülerdeki okuma hacmi toplamın **>%85**'i.

## 3. Çözüm paketi (kalite korunarak)

### Faz 0 — Ölçüm (yarım gün) — önce görünür kılalım
- **A0.1** Task Analizi adımlarında token yakalama: `_adim_isle` → `token_capture_baslat/al` (altyapı var, bağlı değil) →
  `gorev_analiz` olayına `token{girdi,cikti,cache_yaz,cache_oku,cagri}` + `num_turns` + aşama kırılımı.
- **A0.2** Çağrı başına kayıt: `logs/usage/cagri.jsonl` (olay, aşama, model, canlı?, num_turns, token'lar, süre) —
  Kullanım Raporu'na "aşama bazlı tüketim" paneli. Sonraki fazların etkisi buradan ölçülür.
- Kalite etkisi: yok (yalnız ölçüm).

### Faz 1 — Canlı gözlem döngüsünü analiz bağlamından AYIR (en büyük kazanç; ~%70–80 okuma hacmi)
- **A1.1 İki fazlı analiz:** Gözlem fazı = KÜÇÜK prompt (canlı görev + task özeti + gözlem kapsamı; referans/few-shot/
  domain YOK) → yapılandırılmış **Gözlem Raporu** (`<gozlem_raporu>`: ekran/alan/buton/validasyon/istek-yanıt özetleri,
  ≤10k char, kanıt etiketli). Analiz fazı = TEK gözlemsiz çağrı (referans + few-shot + domain + BFF + **gözlem raporu**).
  BFF keşfi zaten bu desende çalışıyor (ayrı rapor → analize blok).
  Kalite: analiz fazı bugünkü tüm bağlamı görmeye devam eder; gözlem artık **açık ve denetlenebilir** bir rapor
  (bugün gözlem, modelin hafızasında kalıp rapora kısmen yansıyordu). Ek kazanç: "model araç çağırmadı" hatası büyük
  promptlardan kaynaklanıyordu → küçük gözlem promptunda kaybolur, `_tekrar` denemeleri azalır.
  Uygulama: `gorev_analiz_et` · `surec_analizi` · `teknik_analiz._teknik_uret_tam` · sohbet üretimi.
- **A1.2 Gözlem raporu paylaşımı:** FE+BE ayrımında TEK gözlem, iki analiz (bugün iki ayrı döngü). Kalite: aynı ekran,
  aynı gözlem; FE/BE farkı analiz fazında.
- **A1.3 Gözlem raporu kısa süreli önbellek (owner kararı — bkz. §5):** aynı hedef+kapsam için ≤N saat (öneri 6 sa)
  rapor yeniden kullanılır; cevap turu / düzelt / FE-BE geçişi yeniden gözlemlemez. "Yeniden gözle" düğmesi zorlar.
  Bugünkü kural "canlı gözlem = mevcut durum, önbellek okumaz" owner kararıydı → bu madde onaya bağlı.
- **A1.4 Döngü tavanı + snapshot diyeti:** `claude -p --max-turns` (gözlem 40 · BFF 60 · giriş 8 · soru-gözlem 15 ·
  kabul 60) + gözlem promptuna kurallar: aynı sayfayı ikinci kez `browser_snapshot` alma, önce `browser_find`,
  `browser_network_requests` listesinden yalnız ilgili isteğin detayını al, rapor yazmadan önce "yeterli kanıt" kontrolü.
  Kalite: tavanlar bugünkü gözlenen aralıkların üstünde (tipik 17–34), yalnız kaçak döngüyü keser.

### Faz 2 — Tekrarı kaldır (cevap turu ve geçişler)
- **A2.1 "Cevapları İşle" = hedefli düzeltme:** analist cevapları `gorev_analiz_duzelt` ile ilgili bölümlere işlenir
  (öz-çözümlemede yaptığımız yol), sorular yakınsama çağrısıyla güncellenir. Tam yeniden üretim yalnız analist
  "Baştan üret" derse. Kalite: cevap bir belirsizliği kapatır; bölüm düzeltmesi bunu tam olarak karşılar; referans
  gerekiyorsa düzeltme çağrısına yalnız ilgili bölümün BM25 parçaları eklenir (küçük).
- **A2.2 Öz-çözümleme düzeltmesi + cevap düzeltmesi tek çağrıda** (aynı analize iki ayrı düzeltme yerine birleşik talimat).
- **A2.3 Köprü `cevap` komutu** aynı hedefli yolu kullanır (bugün tam yeniden üretim).

### Faz 3 — Model katmanlama (doğruluk gerektiren yerde Opus kalır)
- **A3.1 CLI'da `model` parametresini onurlandır:** `_api_cagri_cli` çağrı bazlı `--model` geçsin. Tek başına: açık
  sorular (Haiku niyetli) Opus'tan çıkar.
- **A3.2 Katman tablosu:** Opus → ana analiz (süreç/teknik/görev) ve denetçi. Sonnet 4.6 → gözlem fazı (A1.1), BFF keşfi,
  kabul kontrolü gözlemi, giriş testi, ekran envanteri, soru sınıflandırma, düzeltme çağrıları, FE/BE bölme önizleme.
  Haiku → açık soru üretimi, kabul listesi çıkarımı, yönetici özeti maddeleri.
  Kalite: gözlem/sınıflandırma/düzeltme görevleri araç kullanımı ve biçim sadakati ister, muhakeme derinliği değil;
  Sonnet bu işlerde Opus ile eş sonuç verir (BFF keşfi ve giriş testi zaten dar talimatlı). Ana analizde Opus korunur.
  Owner isterse `MODEL_GOZLEM` / `MODEL_YARDIMCI` `.env` ile tek yerden değişir.

### Faz 4 — Bağlam diyeti (ölçülü)
- **A4.1 Task analizinde referans bütçesi 100k → 70k char** (task dar kapsamlı; BM25 zaten en alakalıyı seçiyor).
  Kalite güvencesi: A0 ölçümüyle `[K:]` kanıt sayısı ve "❓ Belirsiz" oranı izlenir; düşerse geri alınır. Süreç/teknik
  analizde 100k kalır.
- **A4.2 Few-shot: 2 örnek × 16k → 2 örnek × 10k char** (örnekler stil referansı; başı yeterli). Kalite: stil/derinlik
  örneği için ilk 10k char yeterli, tam örnek gerekmez.
- **A4.3 Sohbet turu sabit bloğu:** referans getirimi sohbet turunda soruya göre 30k char ile sınırlı; domain kuralları
  kısaltılmış özetle (tam metin yalnız üretim adımlarında). Kalite: sohbet Q&A; üretim adımları tam bağlamı alır.

### Faz 5 — Bekleme/yarış kayıpları
- **A5.1** Aynı task için eşzamanlı çift iş engeli (iki sekmeden aynı analiz).
- **A5.2** `_tekrar` (araç çağırmama) yalnız gözlem fazında ve A1 sonrası nadir; tavan 1 kalır.
- **A5.3** Timeout'ta kaybolan çıktı: `LIVE_APP_CLI_TIMEOUT` dolunca gözlem raporu kısmi de olsa kaydedilir (A1 ile
  mümkün) → tekrar koşuda sıfırdan başlanmaz.

## 3b. Uygulama sırasında ölçülen ek bulgu — Yalın CLI (uygulandı)
Trivial bir `claude -p` çağrısı bile ~98k token sabit bağlam taşıyor (cache_yaz 67k + cache_oku 31k): Claude Code sistem
promptu + **yerleşik araç şemaları (~35k)** + profil MCP'leri. Analizler metin-içi çalıştığından `--tools ""` +
`--disable-slash-commands` + (canlı değilse) boş strict MCP config eklendi → sabit bağlam **62k**; canlı gözlem turu için
`--tools ""` denendi (~69k) ama soğuk süreçte ilk tur araçsız gidiyordu (gerçek koşularda ilk deneme düştü) → canlıda
yerleşik araçlar açık bırakıldı (~99k/tur; güvenilirlik öncelikli). Düzeltilmiş beklenti: A1 ile tur başına okuma ~107k → ~99k
(analiz bağlamı döngüden çıktı), asıl kazanç tur sayısı (diyet+tavan) ve FE+BE'de 2→1 döngü; tur sayısı diyet + tavanla ayrıca düşer; FE+BE'de döngü 2→1.

## 4. Beklenen etki (Task analizi, FE+BE, canlı hedefli)

| Kalem | Bugün | Plan sonrası |
|---|---|---|
| Gözlem döngüsü okuma hacmi | ~2 döngü × (10–35 tur × ~107k) ≈ 2–7M | 1 döngü × (8–25 tur × ~65k) ≈ 0.5–1.6M (**~−70%**, yalın CLI + ayrım + diyet) |
| Cevap turu | tam zincir + yeniden gözlem | 1 düzeltme çağrısı (**−90%**) |
| İkincil çağrılar modeli | Opus | Sonnet/Haiku (kota ağırlığı Opus'un ~1/5'i) |
| Ana analiz kalitesi | — | **değişmez** (aynı bağlam + açık gözlem raporu) |

## 5. Owner kararı gereken noktalar
1. **A1.3 gözlem raporu önbelleği** (6 saat?) — "canlı gözlem = mevcut durum" kuralını yumuşatır. Öneri: cevap turu/düzelt/
   FE-BE geçişi için AÇIK, yeni analizde KAPALI (her yeni "Teknik Analiz Et" taze gözler).
2. **A3.2 model katmanı** — gözlem/yardımcı çağrılar Sonnet. Öneri: evet; ana analiz Opus.
3. **A4.1/A4.2 bütçe indirimleri** — Öneri: A0 ölçümü 1 hafta çalıştıktan sonra uygula.

## 6. Uygulama sırası ve süre
Faz 0 (yarım gün) → Faz 1 (2 gün; en büyük kazanç) → Faz 2 (1 gün) → Faz 3 (yarım gün) → ölçüm 1 hafta → Faz 4/5.

## 7. Faz 2 + 3 uygulama notu (2026-10-19) + model karşılaştırması
**Faz 2 (A2.1 + A2.3 uygulandı; A2.2 öz-çözümleme zaten tek düzeltmeyle işliyor):** `jira_gorevleri.gorev_cevap_uygula(gorev,
mevcut_md, cevaplar, onceki_sorular)` → (1) `gorev_analiz_duzelt` ile cevaplar ilgili bölümlere işlenir (`_CEVAP_TALIMAT`: belirsiz/
varsayım işaretleri kalkar, `[K: Analist cevabı]`, ilgisiz bölüme dokunma), (2) `_gorev_acik_sorular_uret(cevaplar, onceki)` ile
kalan sorular yakınsar; RAG yorumu korunur; gözlem/RAG/öz-çözümleme TEKRARLANMAZ. Task Analizi iş modu **`cevap`** (UI "Cevapları
İşle → Analize Uygula", editör içeriği = mevcut analiz); editör boşsa / `CEVAP_HEDEFLI=false` ise eski tam üretim; "Baştan üret
(pahalı)" düğmesi bilinçli tam üretim. Köprü `cevap` komutu da mevcut analiz (önbellek/gövde) varsa hedefli. Eskiden cevap turu =
tam zincir (gözlem + analiz + sorular + öz-çözümleme ≈ 4 büyük çağrı) → şimdi 2 küçük çağrı (yardımcı + hafif katman).
**Faz 3 (A3.1 + A3.2):** `base.cli_model_katman(katman)` — `ana` (CLAUDE_CLI_MODEL) · `yardimci` (`CLI_MODEL_YARDIMCI`, vars.
`sonnet`) · `hafif` (`CLI_MODEL_HAFIF`, vars. `haiku`). `_api_cagri(..., katman=)` açık katman > model sabiti (`MODEL_HAFIF`→hafif,
`MODEL_YARDIMCI`→yardimci) > ana; `_api_cagri_cli` `--model`'i katmana göre geçer, önbellek anahtarı + `cagri.jsonl` katmanı taşır.
Yardımcı: gözlem fazı, giriş testi, BFF keşfi, kabul listesi + doğrulama, soru sınıflandırma + çözüm gözlemi, hedefli düzeltme/
cevap, sohbet ekran envanteri. Hafif: formatla, test senaryoları, açık soru toplama. Ana (Opus): süreç/teknik/görev analizi,
denetçi, FE/BE bölme, akış kapatma, sohbet turu. API modunda `model` parametresi aynen geçerli (katman yalnız CLI).
**CLI 2.1.303 + alias'lar:** `sonnet`→claude-sonnet-5-5, `haiku`→claude-haiku-5-5, `opus`→claude-opus-5-5 (2.1.267'de
`claude-opus-5-5` reddediliyordu → analist makineleri `claude update` / `npm i -g @anthropic-ai/claude-code@latest`).
**Aynı minimal canlı prompt (example.com gez + rapor), CLI 2.1.303, 2'şer koşu:**

| Model | Tur | Çıktı token | cache_yaz / cache_oku | API eşdeğeri | Süre |
|---|---|---|---|---|---|
| Opus 4.8 | 7 / 4 | 713 / 267 | 100k / 496k · 66k / 331k | $1.26 / $0.83 | 26 s / 12 s |
| Opus 5.5 | 4 / 4 | 245 / 297 | 100k / 297k · 4k / 392k | $0.86 / $0.12 | 8 s / 11 s |
| Sonnet 5.5 | 4 / 4 | 242 / 245 | 100k / 198k · 4k / 394k | $0.42 / $0.06 | 9 s / 8 s |

Sonuç: aynı doğru çıktı; Opus 5.5 daha az tur + daha kısa çıktı + daha ucuz birim fiyat ($4/$20 vs $5/$25) → ana katman
**Opus 5.5** önerildi (owner makinesinde `.env` `CLAUDE_CLI_MODEL=claude-opus-5-5`); yardımcı işler Sonnet 5.5 (Opus'un ~yarısı,
aynı çıktı). Tokenizer aynı → girdi token sayısı değişmez; kazanç tur sayısı + birim fiyat + katmanlama. Test: `tests/test_kota_faz23.py`.
Her faz: offline testler (0 token) + 1 gerçek Task analizi ölçümü (önce/sonra token tablosu Kullanım Raporu'nda).

## 8. Kullanım taraması 2 (2026-10-19 akşam) — ekip "kota çabuk doluyor" şikâyeti
`logs/usage/cagri.jsonl` (128 çağrı, bugün) aşama bazında okuma hacmi: **gözlem fazı** 4 çağrı / 56 tur / **5.5M cache okuma**
(tek 31 turluk gözlem 3.0M) · **giriş testi** 12 çağrı / 2.4M (çağrı başı ~9 tur, 0.5–0.7M) · BFF keşfi 3×(~40 tur) ·
kabul doğrulama 8 tur / 0.5M · görev analizi çağrı başı ~134k yazma (referans 100k kc + few-shot 16k kc + domain + raporlar).
Tur başına bağlam ~96–100k → kalemler: CLI sistem promptu + yerleşik araç şemaları (~35k) + Playwright şemaları (24 araç, ~5k) +
biriken snapshot'lar. **Bulgular ve uygulananlar:**
1. **BUG — tavan sonrası yanlış tekrar (3× koşu):** tavana takılıp `--resume` ile tamamlatılan çağrının JSON'u yalnız
   tamamlatma turunu (num_turns 1-3) gösteriyordu → (a) `cagri.jsonl` 40 turu "1 tur" yazdı, (b) "model araç çağırmadı"
   tespiti tetiklenip TÜM gözlem 2 kez daha koştu (BFF keşfi 3×40 tur ≈ 650 s, 3×~100k yazma). Düzeltme: tavan/devam/
   tamamlatma koşularının kullanımı birikimli (`_onceki_koşular`), tespit birikimli tura bakar → tekrar yok.
2. **Canlı çağrıda `--tools ""` (ilk deneme):** MCP boot ısıtması sonrası 4/4 koşu başarılı; tur başına ~100k→~73k
   (cache okuma −35%). İlk denemede kapalı, tekrar denemesinde açık; `LIVE_APP_YERLESIK_ARACLAR=true` eski davranış.
3. **Giriş testi atlama:** agent girişiyle kaydedilmiş taze oturum (`oturum_durumu`, < GIRIS_TEST_GECERLILIK) varsa
   kapı 0-token geçer (gözlem zaten oturumla açılır; düşerse OTOMATİK GİRİŞ). Başarısız taze sonuç atlamayı ezer.
4. **BFF keşfi bütçesi:** `BFF_MAX_TUR` (70) + 1 devam → 40'a takılıp baştan koşmaz.
**Kalan öneriler (ölçümden sonra, Faz 4/5):** (a) snapshot şişmesi — `browser_find`/`browser_evaluate` ile hedefli okuma,
`--snapshot-mode none` + açık `browser_snapshot` (araç yanıtlarının otomatik snapshot'ını kapatır; en büyük kalan kalem),
(b) referans bütçesi CLI 100k→70k kc + few-shot 16k→12k kc (görev analizinde ~10k token/çağrı), (c) giriş testi tamamen
0-token (Playwright script, LLM'siz), (d) analist makinelerinde ana model: Sonnet 5.5 ile süreç/teknik kalite karşılaştırması
(Opus yalnız denetçi/FE-BE bölme). Analistlerin kendi `.env`'inde `CLAUDE_CLI_MODEL` değeri kotayı doğrudan belirler.
