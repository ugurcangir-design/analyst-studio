# Mimari & İç İşleyiş — Detaylı Referans

> CLAUDE.md'den ayrılan detay. İlgili alanda çalışırken oku; her istekte gerekmez.

## Çıktı Dosyaları (output/, `IZIN_VERILEN_CIKTILAR`)
```
surec-analizi.md   teknik-analiz.md   acik-sorular.md
brd-analizi.md     brd-sorular.md     kapsam-analizi.md   alternatif-surecler.md
mockup.html        workflow-state.json   sorular.json
test-senaryolari.md   izlenebilirlik-matrisi.md   delta-analizi.md
```
Yeni output dosyası → `app.py` `IZIN_VERILEN_CIKTILAR` set'ine ekle.

## Analiz Zenginleştirmeleri (benzer-agent araştırmasından; Kiro/BMAD/Copilot4DevOps esinli)
- **Belirsizlik Denetimi** (`belirsizlik_denetimi`, base.py — 0 token, deterministik regex):
  muğlak Türkçe ifadeleri ("hızlı", "kolay", "vb.", "gerektiğinde"…) satır no + nedenle raporlar;
  kod blokları/HTML yorumları atlanır, max 20 bulgu. Süreç + teknik + delta çıktılarının sonuna
  "🔎 Belirsizlik Denetimi" bölümü olarak eklenir.
- **Değişiklik Etkisi** (`skills/degisiklik_etkisi.py` — 0 token, base.py import ETMEZ):
  `sinyaller(metin)` girdide veri değiştiren işlem arar (zorunluluk kaldırma · silme · alan/öğe kaldırma ·
  pasife alma · güncelleme · tip/isim değişimi; Türkçe-katlanmış regex). Varsa `degisen_adaylari` değişen
  öğe adlarını çıkarır (tırnaklı ad, "X alanı", camelCase/snake) → `tuketici_tara` bunları **Swagger**
  (`reference/services/*.json` — parametre + istek/yanıt alanları, `$ref` çözümlü, `taxNumber`≈`tax_number`≈
  "Tax Number" normalize) · **Confluence** (`*.md`) · **Jira** export'unda arar → **Olası Tüketiciler**
  (aday başına sırayla dağıtım, ≤25 satır; sayfaların %40'ından fazlasında geçen genel aday atlanır).
  `degisiklik_blogu(metin, hedef)` talimat + netleştirilecek noktalar + tüketici tablosu (sinyal yoksa '',
  hata → ''). **İLKE: analizi büyütmez** — etki AYRI bölüm değil: `surec` → mevcut "İlişkili Ekranlar /
  Etki Analizi" bölümüne kısa `Veri Değişikliği Etkisi` tablosu + etki ilgili PA/AF'ye işlenir · `teknik` →
  §3 akışına + DB (§4) / API (§5) / cache-event (§6) karşılığı · `gorev` → §3 akışına (çok öğe varsa kısa
  tablo) · `gorev_hata` → `## Çözüm` altında tek `Etki:` maddesi. **Yalnız 'güncelleme' sinyali** (BRD'lerde
  çok yaygın) → tablo YOK, tek kısa talimat. Enjeksiyon kullanıcı mesajında (cache breakpoint'inden SONRA):
  süreç (girdi), teknik (surec-analizi.md), görev (özet+açıklama; Jira Köprüsü + İnteraktif Analiz miras).
- **Süreç ve Ekran Bütünlüğü kuralları** (`_BUTUNLUK_KURALLARI`, base.py): `prompt_yukle` → `_prompt_ekleri`
  ile `_BUTUNLUK_SKILL_IDS` (surec_analizi · teknik_analiz_bolumler · gorev_teknik_analiz) promptuna HER ZAMAN
  eklenir (`prompts.json` override'ında da; ekrandaki özel promptta EKLENMEZ). Amaç: analizi büyütmeden
  uçtan uca akışı kapatmak — testçi kontrol listesi DEĞİL. Model yazmadan önce akışı yürütür: süreç↔ekran
  eşleşmesi (karşılıksız adım / işlevsiz buton yok) · giriş-çıkış (aksiyon sonrası ekran durumu) · karar
  noktalarının TÜM dalları · veri sürekliliği/durum geçişleri · etki akışta · kabul kriterleri akışı doğrular
  (sayı doldurmak için kriter YOK). Eksik halka İLGİLİ MEVCUT BÖLÜMDE tamamlanır (ayrı bölüm/liste yazılmaz),
  kaynaktan tamamlanamıyorsa açık soru. + **Zorunlu Açık Soru** kuralı.
- **Zorunlu açık soru** (`- Zorunlu: Evet`): süreç/teknik soru şablonları + teknik açık-soru adımı + görev
  açık-soru adımı bu alanı üretir. `sorular.zorunlu_mu` → parse `zorunlu: bool`; `istatistik.zorunlu_acik`;
  `/api/pano.sorular.zorunlu`. UI: kırmızı **ZORUNLU** rozeti (Sorular sekmesi, onay kapısı kartları, Task
  soru kartları), onay bağlamı + Ana Sayfa sayacı. **YUMUŞAK ENGEL** (`_zorunluSoruKapisi`): süreç onayı
  (`onayla`) ve teknik onay (`teknikOnaylaFeBe/JiraIle/SizJira`) öncesi cevapsız zorunlu soru varsa
  `confirm` — "yine de devam" serbest (sert kilit yok; hata → engellemez). Task: `_jgZorunluKapi`
  (`jgJiraGuncelle` · `jgFeBeOnayla` · `jgYeniTaskAc`) + devam edilirse sorular task gövdesine
  `## ❗ Cevap Bekleyen Zorunlu Sorular` olarak eklenir (geliştirici/test görür); `ornek_havuzu._temizle` bu
  bölümü few-shot örneğinden çıkarır.
- **Akış Bütünlük Denetimi** (`akis_butunluk_denetimi`, base.py — 0 token): süreç analizinde TANIMLANAN
  (tablo ilk hücresi / `**ID:**`) AF/EF/EK/BR'lerden akışa BAĞLANMAMIŞ olanlar (tanımı dışında referans yok VE
  tanım satırında kendi bağlı PA'sı yok — şablon "Bağlı adım: PA-…" taşır) + tanımsız PA/AF/EF/EK referansları
  → "🔗 Akış Bütünlük Denetimi" bölümü (bulgu varsa). Açık Sorular/denetim bölümlerindeki atıf bağ sayılmaz;
  `BR-002–BR-005` aralıkları çözülür. Test: `tests/test_degisiklik_etkisi.py`.
- **Akış Kapatma — Faz 3** (`skills/akis_kapatma.py`): bütünlük kuralları modelin kendi kontrolü, akış
  bütünlük denetimi yalnız GÖSTERİR; bu adım boşluğu KAPATIR. (1) **Tespit** — 1 AI çağrısı (`_TESPIT_SISTEM`,
  MAX_TOKENS_KISA): analiz + kaynak (süreç: girdi doküman · teknik: surec-analizi.md · Task: görev) + deterministik
  denetim bulguları → `<akis_bosluklari>` JSON (≤8; tür: ekran_eslesme · giris_cikis · karar_dali ·
  veri_surekliligi · etki · tanimsiz; kozmetik/üslup YOK). Her boşluk `duzelt` (bilgi analizde/kaynakta AÇIKÇA
  var) ya da `soru`. (2) **Kapatma** — `_hedef_bolum`: hedef ID'nin TANIMLANDIĞI satırı (`**PA-001:**`,
  `| BR-002 |`, başlık) içeren en derin bölüm (yalnız atıf alan bölüm DEĞİL; `revizyon_ai.bolum_bul` gövde
  fallback'i 'Bağlı adım: PA-001' yazan ekrana/Kabul Kriterlerine yönlenirdi). Aynı bölümün boşlukları TEK
  çağrıda (`_DUZELT_SISTEM`, çıktı limiti bölüm boyuna göre); düzeltmeler sırayla, her seferinde GÜNCEL metinde
  bölüm yeniden bulunarak uygulanır (bölümler iç içe). **Korumalar** (`_duzeltme_gecerli`): başlık aynen ·
  kısalma <%90 RED (kesik çıktı) · büyüme > max(600, %50) RED (analiz büyümesin) · bölüm >30k krk düzenlenmez
  → reddedilen boşluk açık soruya döner. (3) **Sorular** `soru_bloklari` (`Kategori: Akış Bütünlüğü`, riskliyse
  `Zorunlu: Evet`, numara mevcut en büyükten devam): süreç → analizin Açık Sorular sonuna (`Q-`, otomatik denetim
  bölümlerinden ÖNCE — `sorulari_analize_ekle`) · teknik → `acik-sorular.md` (`Q-T-`) · Task → görevin açık
  soruları (`Q-T-`). **Otomatik:** `surec_analizi_yap` + `teknik_analiz_yap` SON kayıttan sonra
  `dosya_akis_kapat` (özel promptta ATLANIR); sonuç TEK revizyon (`yeniden_bazla` → `revizyon_oner` →
  `onayla`) → Revizyon ekranından Geri Al dosyayı birebir eski hâline döndürür. Özet `output/.akis-kapatma.json`
  → `/api/pano.akis_kapatma` (bu oturuma ait) → onay kapısı satırı "🔗 Akış kapatma: N boşluk kapatıldı · M soru
  açıldı (Revizyon'da gör / Geri Al)". **Task:** "Akışı Kapat" butonu (`jgAkisKapat` → iş modu `akis-kapat` →
  `gorev_akis_kapat`); önceki hâl `akis_onceki`'de → `jgAkisGeriAl`; rapor + detay `_jgAkisRaporGoster`.
  Kapatma: `.env` `AKIS_KAPATMA=false` ya da `HIZLI_MOD=true`. Hata → None (analiz ASLA kırılmaz). NOT: teknik
  akışta RTM/test senaryoları/TL;DR akış kapatmadan ÖNCE üretilir (kapatma son adım). Test: `tests/test_akis_kapatma.py`.
- **İzlenebilirlik Matrisi / RTM** (`izlenebilirlik_matrisi_olustur`, base.py — 0 token):
  süreç ID'si ↔ teknik analizde geçtiği bölüm başlıkları tablosu → `izlenebilirlik-matrisi.md`.
  Süreç metninde ID yoksa (özel prompt çıktısı) üretilmez.
- **Test Senaryoları / Gherkin** (`_test_senaryolari_uret`, teknik_analiz.py — MODEL_HAFIF/Haiku):
  kabul kriterleri + canlı gözlem kayıtlarından Diyelim ki/Eğer ki/O zaman senaryoları →
  `test-senaryolari.md`. Prompt: `test_senaryolari`. Hata pipeline'ı bozmaz (try/except).
- **CR / Delta Analizi** (`skills/delta_analizi.py` + `POST /api/delta-analiz` + UI paneli):
  mevcut teknik-analiz.md (zorunlu) + CR metni → yalnızca DELTA raporu (etkilenen bölümler,
  DBR-XXX değişen gereksinimler, regresyon riski) → `delta-analizi.md`. SENKRON çalışır
  (jira_gorev_analiz deseni — workflow durum makinesine girmez; çalışan analiz varsa 409).
  Referanslar + canlı gözlem (Bağlam Filtresi) delta'da da geçerli. Prompt: `delta_analizi`.
- **Mermaid süreç diyagramı**: süreç analizi promptuna otomatik ek talimat (varsayılan yolda) —
  Süreç Adımları sonuna `flowchart TD` bloğu (≤12 düğüm, PA-XXX etiketli). SPA'da mermaid@10 CDN +
  `mermaidRender()` tüm markdown görüntüleyicilerde (çıktı/önizleme/history) SVG render eder;
  bozuk diyagram metin olarak kalır (try/catch).

## Workflow Durumları (`workflow.py → Durum`)
```
IDLE → SUREC_ANALIZI_CALISIYOR → ONAY_BEKLENIYOR
     → TEKNIK_ANALIZ_CALISIYOR → TEKNIK_ANALIZ_ONAY_BEKLENIYOR
     → BRD_REVIZE_BEKLENIYOR   → BRD_TAMAMLANDI
     → JIRA_GONDERILIYOR       → JIRA_TAMAMLANDI → HATA
```
**Otomatik kurtarma:** `baslat()`/`baslat_teknik()` yalnız CALISMA_DURUMLARI'nda reddeder;
HATA/bekleme/tamamlanmış durumlardan temiz başlar. Stale CALISIYOR (state çalışıyor der ama
subprocess yok — örn. uygulama analiz ortasında kapandı/çöktü): `_stale_workflow_kurtar()`
`/api/run`, `/api/run-teknik` **ve** `GET /api/workflow-state`'te çağrılır. Üçüncüsü kritik:
UI bu uç noktayı birkaç saniyede bir poll edip `busy` durumuna göre Başlat butonunu
disable ediyor (`updateUI()` → `btn-surec.disabled = busy || !selectedFiles.surec`); yalnızca
run/run-teknik'te temizlense stale durum kalıcı olurdu çünkü buton disabled kaldığı için
kullanıcı hiç `/api/run`'a basamaz — kendini düzelten kod hiç tetiklenmezdi (tavuk-yumurta).
Artık her poll'da kontrol edilip ilk fırsatta sıfırlanıyor.

## Sabitler / Limitler (`skills/base.py`)
```python
MODEL_ANALIZ = "claude-sonnet-4-6"   # tüm analizler
MODEL_HAFIF  = "claude-haiku-4-5"    # hafif iş (jira_gorevleri Standart Formatla, açık sorular; jira_agent görev başlığı)

# Karakter limitleri
MAX_CHARS_BRD=100_000  MAX_CHARS_GENEL=30_000
MAX_CHARS_REF=15_000   # dosya başına
MAX_CHARS_CONF_TOT=80_000  MAX_CHARS_JIRA_TOT=60_000  MAX_CHARS_SERVIS_TOT=60_000
MAX_CHARS_LIVE_APP_TOT=60_000  MAX_CHARS_DIGER_TOT=20_000
MAX_CHARS_REF_GLOBAL=140_000  # GETİRİM BÜTÇESİ: tüm tiplerin TOPLAM tavanı (.env; 0=sınırsız).
                              # _ref_bloklari_olustur tipleri sırayla doldurur, bütçe dolunca keser.
MAX_CHARS_REF_GLOBAL_CLI=100_000  # CLI modunda prompt-cache YOK → bütçe her çağrıda tam ödenir; CLI için
                              # daha sıkı tavan (_ref_global_butce: CLI'de min(genel, CLI); genel sınırsızsa CLI tavanı).

# Token limitleri
MAX_TOKENS_UZUN=16_000  (süreç analizi)   MAX_TOKENS_KISA=3_000
MAX_TOKENS_COMBINED=16_000  (teknik; DDL+OpenAPI)   MAX_TOKENS_BRD_CMB=9_000   MAX_TOKENS_KAPSAM=8_000
```

### Heartbeat / Suspend (`app.py`)
`SUSPEND_SURE=30s` (overlay göster) · `KAPAT_SURE=180s` (DESKTOP_MODE'da kapat; Chrome arka-plan
throttling'e dayanıklı; analiz sürerken `_analiz_calisiyor_mu` guard'ı ile ASLA kapanmaz; SIGINT
10s'de işe yaramazsa `os._exit(0)`). UI heartbeat: 20s interval + visibilitychange'te anında.

### Retry (`_api_yeniden_dene`)
429/5xx/connection için exponential backoff (4s, 8s, 16s; 3 deneme).

### Çıktı Önbelleği (`_api_cagri`, token tasarrufu / 429 çare)
İçerik-hash'li önbellek: aynı (sistem prompt + mesajlar + model + limit) → kaydedilen yanıt, 0 token.
İçerik değişince taze çağrı. Refine'in düzeltme notu doğal cache-miss. `_api_cagri(..., onbellek=False)`
okumayı atlar ama yazar — kesik-çıktı retry'ı (`_teknik_uret_tam` 2+ deneme) ve refine bunu kullanır.
Depo: `.api_cache/` (gitignored), oturum başına süresi geçenler temizlenir. Kapat: `.env API_CACHE=false`,
TTL: `API_CACHE_TTL` (vars. 7 gün).

### Yönetici Özeti / TL;DR (`yonetici_ozeti_olustur`)
Süreç & teknik analiz çıktısının EN ÜSTÜne deterministik (0 token) özet: kapsam (endpoint/tablo/bölüm),
süreç kapsam %'si, açık soru (kritik) sayısı. **Jira'ya YAZILMAZ** — `yonetici_ozetini_cikar()` her Jira
yazma yolunda (jira_tasks hiyerarşi + gorev_jiraya_yaz) çağrılır.

### Jira'ya YAZILMAYAN bölümler — analist bilgisi vs. geliştirici task'ı
Analiz çıktısında KALIP Jira description'ına GİTMEYEN iki bölüm var; ikisi de analistin
doğrulama/şeffaflık bilgisidir, gereksinim değildir. Her Jira yazma yolu ikisini de çıkarır
(`gorev_jiraya_yaz` + `jira_tasks` hiyerarşi üretimi):
1. **Yönetici Özeti** → `yonetici_ozetini_cikar()` (başlıktan ilk `---` ayırıcıya kadar).
2. **Canlı Gözlem Kapsamı** → `canli_gozlem_kapsamini_cikar()`. MCP gözleminde nereye bakıldığını
   (gezilen tablar/modallar, YAPILAN yazma işlemleri, gezilemeyenler + nedeni) raporlar.
   Yönetici Özeti'nden farkı: sabit `---` ile bitmez → bölüm sonu **başlık seviyesine göre**
   belirlenir (aynı ya da daha üst seviyedeki sonraki başlık; yoksa doküman sonu). Başlıktaki
   emoji ve diakritiksiz yazım ("Canli Gozlem Kapsami") da yakalanır; bölüm silinince sarkan
   `---` ayırıcı da temizlenir. Modal önizlemede analist bölümü GÖRÜR (yalnızca yazılan kopya temizlenir).
3. **`[K: kaynak]` kanıt/izlenebilirlik etiketleri** → `kanit_etiketlerini_temizle()` (base.py).
   İnline `[K: BRD §3]` / `[K: Canlı UI:/route]` / `[K: Network:GET /api/x]` / `[K: Analist cevabı]` /
   `[K: 🔍 Türetilmiş - …]` / `[K: ❓ Belirsiz]` etiketleri agent'ın KAYNAK İZLENEBİLİRLİĞİ aracıdır —
   analiz dosyalarında + UI çiplerinde (`_kanitCipleriIsle`) DURUR, ama Jira'ya yazılan **gerçek task
   analizi** içinde YER ALMAZ (geliştiricinin task'ında işi yok). İki Jira-yazım sınırında da temizlenir:
   gövde (`gorev_jiraya_yaz` — hem köprü `_govdeye_yaz` hem ana app "Jira'ya gönder") + yorum
   (`jira_yorum_ekle` — açık sorular). Yalnız Jira'ya giden kopya temizlenir; kaynak-metin (ekran/dosya)
   dokunulmaz — köprü UI komut yanıtları da etiketleri korur (strip yerel `markdown` param'ında yapılır).

### FE/BE düz Task bölme (`skills/jira_fe_be.py`) — süreç ekranı onay → Jira
Süreç→Teknik akışında teknik analiz onaylanınca (süreç ekranı "Evet — FE/BE Task'larını Öner",
`teknikOnaylaFeBe`) alternatif bir Jira yolu çalışır. Epic/Story/Subtask hiyerarşisinden (`jira_tasks.py`)
FARKLI: **tüm issue'lar tek tip Task (görev)**, yapı DÜZ (üst başlık yok), FE ve BE ayrı task'lar.
- **Önizleme** (`jira_fe_be_uret`, `/api/jira/fe-be/preview`, Jira'ya YAZMAZ): teknik-analiz.md (TL;DR +
  Canlı Gözlem çıkarılmış) → AI `<fe_be_gorevler>` JSON. Her görev: `{id, katman:FE|BE, summary,
  description, acceptance_criteria, bagimli_be:[BE-id…]}`. `bagimli_be` = FE'nin ihtiyaç duyduğu BE
  görev(ler)i (BE 'blocks' FE). `_gorevleri_normalize` katmanı FE/BE'ye indirger (`_katman_indirge`:
  Frontend→FE, Backend→BE, belirsiz→BE) + var olmayan BE id'ye bağımlılığı (hayalet) düşürür.
- **Oluşturma** (`jira_fe_be_olustur`, `/api/jira/fe-be/create`): analistin seçtiği/düzenlediği görevleri
  Task tipinde (`_proje_bilgi.task_id`) açar — BE'ler ÖNCE (blocker), sonra FE'ler. Sonra `bagimli_be`
  haritasına göre **BE→FE Blocks bağı** kurar (`_blocks_bagla`: `outwardIssue=BE` bloklar,
  `inwardIssue=FE` bloklanan). Link tipi `_blocks_link_tipi` ile runtime'da doğrulanır (ad tam "Blocks"
  değilse 'block' outward'lı ilk tip; hiç yoksa bağ atlanır + `link_uyari`). Bağ YALNIZ ikisi de seçilen
  görevler arasında kurulur (UI `febeOnayla` bağımlılığı seçime göre filtreler + backend `secilen_idler`
  ile tekrar filtreler — çift güvence).
- **UI:** `#febe-modal` (index.html; `febeOnizlemeAc`/`febeModalDoldur`/`febeRefresh`/`febeOnayla`). Süreç
  onay butonu modalı AÇAR; task'lar GERÇEKTEN açıldıktan SONRA `febeOnayla` içinde
  `/api/approve-teknik-no-jira` çağrılıp workflow bitirilir (auto tek-Task YOK). Analist modalı iptal
  ederse workflow teknik-onay adımında KALIR → tekrar deneyebilir ya da "Atla" seçebilir. Eski
  tek-monolitik-Task yolu (`jira_agent.main`, `/api/approve-teknik`) kodda DURUYOR ama süreç ekranı artık
  bu FE/BE akışını kullanır.

## RAG Mimarisi (`skills/base.py`)
- **Bağlam blokları:** `_ref_bloklari_olustur(ref_dosyalar)` tipine göre gruplar — `### CONFLUENCE
  DOKÜMANTASYONU` (md), `### JİRA TASK GEÇMİŞİ` (`_jira_json_to_md` kompakt md), `### API / SWAGGER
  TANIMLARI` (filtrelenmiş openapi), `### CANLI UYGULAMA GÖZLEMİ` (`reference/live-app`),
  `### DİĞER REFERANSLAR`. Her tip ayrı limitle.
- **PDF-farkında filtre + keyword-odaklı çıkarım (KRİTİK):** `filtrele_referanslar` içerik-eşleşmesini
  `_filtre_metni_oku` (PDF'i `pdf_oku`/fitz ile çıkarır) üzerinden yapar — düz `read_text` bir PDF'i binary
  çöp okuyup ilgili referansı YANLIŞLIKLA elerdi (ör. 6.7 MB `TradePanel_1_7_9.pdf` confluence referansı).
  Confluence filtresi dosya adı VEYA içerik eşleşmesiyle dahil eder (farklı adlı ilgili sayfa da gelir).
  RAG blok üretiminde büyük dosya limitten (MAX_CHARS_REF=15K) büyükse `_keyword_odakli_metin` baştan
  kesmek yerine keyword geçen yerlerin ETRAFINDAN pencereler alır → ilgili bölüm (ör. Publish Overview
  PDF'in %25'inde) 15K bütçeye girer. Keyword yoksa baştan-kesmeye döner.
- **Bağlam filtresi:** `load_context_filter()` → keyword / jira_keys / confluence_pages ön-filtre +
  `live_app.target_url`, en fazla 5 `live_app.extra_urls` ve `live_app.use_as_sample`; `filtrele_referanslar(files, ctx)`
  büyük Swagger'ı `_filtrele_openapi_json()` ile keyword bazlı kırpar.
- **Canlı uygulama MCP/Chrome:** Süreç ve teknik analizde `canli_uygulama_baglami_hazirla()` URL listesi
  doluysa Claude Code'a ana URL'den başlayarak ekranı simüle etme, validasyon/mesaj/akışları ve network
  servislerini toplama görevi verir. MCP gözlem çıktıları `reference/live-app/` altına `.md/.json/.html`
  olarak bırakılırsa RAG'e `CANLI UYGULAMA GÖZLEMİ` bloğu olarak girer. Gizli header/token/cookie değerleri
  maskelenmelidir; kaynak etiketleri `[K: Canlı UI:<route>]` ve `[K: Network:<METHOD> <path>]`.
  `use_as_sample=true` ise ana URL süreç analizinde örnek ekran kabul edilir ve isterler ekran yapısına göre
  detaylandırılır. Ham UI kaynak kodu okuma/yükleme arayüzü kaldırılmıştır.
- **Prompt caching:** system prompt → `cache_control: ephemeral`; stable user blocks (ref+MCP hedefleri+mockup) son
  bloğa cache breakpoint; `anthropic-beta: prompt-caching-2024-07-31`. 5 dk içi tekrar ~%90 tasarruf.
  **Görev analizinde 2. breakpoint (madde 3):** görev içeriği (key/başlık/açıklama + analist notu) cevap/düzeltme
  turları arasında değişmez → refs breakpoint'ine ek olarak görev bloğuna da konur; cevap turlarında görev
  içeriği cache'ten okunur (sistem+refs+görev = 3 breakpoint, tavan 4). CLI modu cache_control yok sayar.
  THINKING yolunda da aktif (`_api_cagri_direct`) — eskiden yalnızca non-thinking yol cache'liyordu,
  EXTENDED_THINKING açıkken her çağrı tam input token maliyeti ödüyordu.
- **Tüm analiz skill'leri RAG kullanır:** `surec_analizi`, `teknik_analiz`, `brd_analizi`, `kapsam_analizi`
  → `referans_dosyalari_hazirla()` + `_ref_bloklari_olustur()`.

## Sistem Promptları (19) — `VARSAYILAN_PROMPTLAR` (`skills/base.py`)
Tutarlı yapı: `# ROL → GÖREV → ÇIKTININ AMACI → ÇALIŞMA YÖNTEMİ → RAG İLKESİ → BAĞLAM KULLANIMI → KALİTE ÖLÇÜTÜ`.
```
surec_analizi_rol   surec_analizi          teknik_analiz_rol   teknik_analiz_bolumler
teknik_analiz_sorular  teknik_analiz_denetci   brd_analizi_rol   brd_analizi_bolumler
brd_analizi_sorular   kapsam_analizi_rol   kapsam_analizi_bolumler   kapsam_analizi_alternatifler
html_mockup_base   jira_tasks   refine   confluence_publisher
gorev_teknik_analiz   test_senaryolari   delta_analizi
```
- `teknik_analiz_denetci` (Aşama 3 denetçi): `_ORTAK_EK_KURALLAR` ALMAZ; sadece sorun tespit eder.
  UI prompt editöründe `_PROMPT_GRUPLARI` (index.html) "Süreç / Teknik Analiz" grubunda.
- **EK KURALLAR (otomatik append):** `prompt_yukle()` şu 5 prompta `_ORTAK_EK_KURALLAR` ekler:
  `surec_analizi`, `teknik_analiz_bolumler`, `kapsam_analizi_bolumler`, `brd_analizi_bolumler`,
  `jira_tasks` (`_EK_KURAL_SKILL_IDS`). `_ORTAK_EK_KURALLAR` 4 bölüm: Kaynak Önceliği, Kaynak İzleme
  `[K: ...]`, Halüsinasyon Koruması (Entity Whitelist), İzlenebilirlik (aşama bazlı ID tablosu).
- **Override:** `reference/prompts.json` (UI'dan düzenlenince); `prompt_yukle()` önce override, yoksa varsayılan.
- **Özel Prompt (analiz-bazlı, EN YÜKSEK öncelik):** Süreç/Teknik Analiz ekranındaki "Özel Prompt"
  paneli (`op-surec`/`op-teknik` textarea'ları) → `context_filter.json → ozel_prompt.{surec,teknik}`.
  Dolu alan, ilgili analizde varsayılan promptun (rol + bölümler + `_ORTAK_EK_KURALLAR`) **tamamen
  yerine geçer** (`ozel_prompt_oku()`, `skills/base.py`).
  **Miras kuralı (`teknik_ozel_prompt_oku()`):** teknik alan boşsa SÜREÇ özel promptu teknik
  analize de taşınır — analist tek prompt girdiğinde tüm pipeline onu baz alır, teknik aşama
  sessizce varsayılana dönmez. İki alan da boşsa mevcut zincir aynen çalışır.
  Teknik analizde `<teknik_analiz>` XML çıktı zorunluluğu özel prompta OTOMATİK eklenir — pipeline
  (`_xml_ayir`, kesik-çıktı retry'ı) bu bloğa bağımlı, analist bunu bilmek zorunda değil.
  **Kaydetme — ÜÇ başlatma yolu da ekrandaki değeri kaydeder:** `runPipeline` (Başlat),
  `sadeceTeknikBaslat` (Sadece Teknik Analiz) ve `onayla` (Devam Et — Teknik Analiz Başlat) önce
  `buildContextFilter()`'ı POST'lar. (Geçmiş bug: son ikisi kaydetmiyordu → analist promptu yazıp
  bu yollardan başlatınca alt süreç eski/boş değeri okuyup VARSAYILAN prompta düşüyordu —
  "özel prompt çalışmıyor" algısının kaynağı.)
  **Doğruluk çekirdeği (`OZEL_PROMPT_DOGRULUK_EKI`, base.py):** Özel prompt varsayılan rol/bölüm
  promptlarının yerine geçer ama bu kompakt ek HER ZAMAN eklenir: verilen bağlamı (referanslar,
  Jira task içerikleri, Confluence, Swagger, canlı gözlem) aktif kullan; UYDURMA YASAK; ekran ↔
  servis eşleştir; `[K: ...]` kaynak etiketi kullan. Referans blokları + canlı uygulama MCP görevi
  kullanıcı-mesajı bloklarında taşındığından özel prompttan BAĞIMSIZ olarak aynen gider.
  **Özel promptta şablon dayatması YOK:** teknik analizin kullanıcı-mesajındaki "BR/AC/PA ID'lerini
  MUTLAKA referans al" talimatı nötr girdi talimatına döner; AI denetçi (varsayılan 11-bölümlük
  şablona göre denetler → yanlış bulgu üretirdi) atlanır ve denetim bölümüne not yazılır.
  Deterministik `surec_id_kapsam` çalışmaya devam eder (ID yoksa skor 1.0 — zarar vermez).

## Süreç Analizi Çıktı Formatı (analiz ekibi Confluence şablonu)
`VARSAYILAN_PROMPTLAR["surec_analizi"]` çıktısı, analiz ekibinin Confluence sayfalarıyla **aynı iskeleti**
üretir: üstte metadata tablosu (Target Release/Epic/Story/Jira Task/Jira Subtask/Analyst/Ürün Doküman
Versiyonu — değerler BOŞ; analist Confluence'a taşırken doldurur) → **AMAÇ → MOCKUP → GEREKSİNİMLER**
(İş Gereksinimleri↔İş Kuralları tablosu + Aktörler + numaralı **Ekranlar**: her ekran `Alan Adı | Açıklama`
ve `Buton Adı | Açıklama` tabloları + **Süreç Adımları** iş akışı) → **ÖNERİLEN DB ALANLARI → GELİŞTİRME
NOTLARI** (Sistemler ve Entegrasyonlar, Kabul Kriterleri, Karar Tabloları, Açık Sorular).
GEREKSİNİMLER altında **İlişkili Ekranlar / Süreçler ve Etki Analizi** (IB-XXX) bölümü zorunlu: referanslardan
bu süreçle ilişkili/etkilenen ekran-süreçleri, paylaşılan bileşen/servis/kural/entity'yi ve değişikliğin
etkilerini çıkarır (izole varsayma). Prompt'ta **KAYNAK KULLANIMI (ZORUNLU)** bloğu: sağlanan tüm
referansları (Confluence/Jira board/Swagger/canlı uygulama) aktif kullan, yüzeysel/tek-kaynaklı analiz üretme.
**Pipeline korunur (B yaklaşımı):** ID'ler (A/BR/PA/AF/EF/EK/AC/Q) ilgili bölümlere gömülür →
`surec_id_kapsam` + RTM çalışır; `### Süreç Adımları` başlığı mermaid enjeksiyonunun çapası;
`| Q-001 | …` tablosu Soru Defteri (`sorular._TABLO_SORU_SATIR`) çapasıdır. Format değişikliği bu üç
çapayı bozmamalıdır.

## HTML Prototip — canlı uygulama baz'lı (`skills/html_mockup.py`)
`html_mockup_uret()` süreç analizinden `mockup.html` üretir. **Canlı uygulama baz'ı:** context_filter
`live_app` (target_url + extra_urls) doluysa `canli_uygulama_baglami_hazirla()` ile Chrome MCP gezinme
görevi kurulur ve `_api_cagri(..., canli_uygulama_kapsami="surec")` ile CLI modunda **Playwright MCP açılır**;
`claude -p` verilen ekran(lar)ı gezip tasarım sistemini (palet/tipografi/spacing) + component desenlerini
(sidebar/tablo/form/buton/modal/tab/chip) çıkarır ve prototip bunlara birebir uyar. İçerik kaynağı süreç
analizinin **GEREKSİNİMLER → Ekranlar** (EK-XXX, Alan/Buton tabloları) bölümüdür. Tüm component'ler çalışır
(nav geçiş, form submit+doğrulama, tablo mock veri, modal aç/kapa). URL yoksa generic tasarım ipucuna düşer
(fallback korunur). `html_mockup_base` promptu buna göre güncellendi (eski "Bölüm 9" referansı yeni formata taşındı).
- **Sohbetle iteratif düzeltme:** `html_mockup_duzelt(talimat)` mevcut `mockup.html` + talimat → güncellenmiş HTML;
  `/api/mockup/duzelt` + `/api/mockup/geri-al` (yedek/undo), görüntüleyicide "Sohbetle düzelt" satırı — analist
  istediği hâle gelene kadar düzeltir, "✓ Onayla" ile kabul eder; teknik analiz `mockup.html`'i kaynak alır.

## ID Şeması (aşamalar arası izlenebilirlik)
```
BRD Analizi   : FR-XXX NFR-XXX US-XXX AC-XXX I-XXX
Süreç Analizi : A-XXX PA-XXX BR-XXX AF-XXX EF-XXX AC-XXX EK-XXX (ekran) IB-XXX (ilişki/etki)
Teknik Analiz : T-FE-XX T-BE-XX  (Bölüm 2/5/7'den çıkarılan FE/BE görevleri)
Kapsam Analizi: YE-XXX (yeni) KL-XXX (kaldırılan) DG-XXX (değiştirilen)
```

## FE / BE Katman Ayrımı
Süreç adımları, iş kuralları, ekranlar ve teknik iş öğeleri **katman etiketi** taşır: `FE / BE / FE+BE /
Tek tip`. FE+BE Jira görevlerinin ayrı ama ilişkili açılmasını sağlar.
- Teknik analizde: Bölüm 7 → Frontend İş Kırılımı; Bölüm 2 (İş Gereksinimleri)+5 (API) → BE/işlevsel
  görevler (Jira hiyerarşisi buradan çıkar). Jira önizleme modalı her Story/Subtask'ta FE/BE rozeti gösterir.

## Teknik Analiz ÜÇ AŞAMALI (`teknik_analiz_yap` → tuple(teknik_yol, sorular_yol))
1. **Aşama 1:** teknik analiz 1-11. bölüm (Amaç/Hedefler, İş Gereksinimleri, Teknik Gereksinimler,
   Veritabanı, API, İş Mantığı, Frontend İş Kırılımı, Role Management, Hata Yönetimi, Teknik Borç,
   Kabul Kriterleri). 12. bölüm "Karar Bekleyen Konular" regex'le prompttan çıkarılır → `teknik-analiz.md`
   (ham) BİTER BİTMEZ kaydedilir.
2. **Aşama 3 (denetim):** `surec_id_kapsam()` deterministik — süreç ID'leri (BR/AC/PA/EF/EK) teknik analizde
   referans edilmiş mi. Ardından `_teknik_denetle()` (prompt `teknik_analiz_denetci`) AI denetçi: kaynaksız
   iddia, §5↔§7 validasyon drift'i, uydurma endpoint/tablo, hata tutarsızlığı. Kapsam özeti + bulgular
   `## 🔍 Otomatik Denetim Notları` olarak teknik-analiz.md SONUNA eklenir (try/except — denetçi çökerse ham korunur).
   **`HIZLI_MOD=true` (.env) → AI denetçi ATLANIR** (`hizli_mod_acik()`, base.py): denetçi, teknik+süreç
   metninin tamamını İKİNCİ kez gönderen en pahalı ikinci çağrıdır — 429 limitine takılan ekipler için
   token tasarrufu. Deterministik kapsam denetimi her durumda çalışır; denetim bölümüne atlandı notu yazılır.
3. **Aşama 2:** ayrı `_api_cagri` — ham Aşama 1 + süreç analizi → açık sorular → `acik-sorular.md`
   (`### Q-T-NNN:` blok). Kapsamda karşılanmayan ID'ler Aşama 2'ye verilip GARANTİLİ soruya dönüşür.
- **Boş bölüm kuralı:** kapsam yoksa bölüm uydurulmaz; başlık + tek satır not.
- **Kesilme koruması:** `_teknik_uret_tam()` Aşama 1 yanıtında kapanış `</teknik_analiz>` yoksa kesilmiş
  sayar, yeniden dener (max 2, retry'da önbellek bypass); başaramazsa en dolu çıktıyı kaydedip uyarır.
  `_xml_ayir` kapanış etiketi yoksa yarımı stray-etiketsiz kurtarır.

## Mimari: subprocess + `sys.stdin.isatty()`
```
Tarayıcı → fetch /api/run → app.py → subprocess.Popen(run.py {mod})
                                  ↓  run.py → skills/* → Claude API
app.py /api/workflow-state ← polling 1.5s, workflow.py durum okur
not sys.stdin.isatty() → GUI modu (input() çağrılmaz, otomatik onay)
```
- Subprocess: `encoding="utf-8", errors="replace", start_new_session=True`; `_bekle()` thread'i
  timeout/crash'i yakalar, workflow'u HATA'ya çeker; zip-bomb koruması (compression ratio >100 atla).
- **Timeout katmanları** (CLI tam çıktıda yavaş): `_api_cagri_cli`/API SDK = 1200s (20 dk) **her claude
  çağrısı başına**; app.py `_bekle` subprocess = **MOD-BAZLI**: `teknik_analiz`/`brd_analizi` ÇOK AŞAMALIDIR
  (Aşama 1 teknik + canlı-uygulama MCP gezinme, Aşama 2 açık sorular = 2 ayrı çağrı, +olası Aşama 1 retry)
  → **2700s (45 dk)**; tek-çağrılık modlar (surec_analizi, kapsam_analizi, jira_gonder) → **1800s (30 dk)**.
  Eski sabit 1320s tek çağrıya göreydi → teknik analizde 2. aşama başlarken yanlışlıkla öldürüp "22 dk
  zaman aşımı" veriyordu. Dış timeout çağrı DİZİSİNİ kapsar; iç 1200s tek çağrının asılı kalmasını engeller.
- **CLI `--output-format json`** (text DEĞİL): text uzun/çok-turn yanıtta çıktının başını kaybediyordu;
  json `result` tam döner, `stop_reason`/`is_error` ile kesilme tespiti. `_claude_yolu_bul()` PATH'e
  bağımlı değil (GUI minimal PATH için nvm/~.local/homebrew tarar).

## UAT Mutabakat (ekran adı; `skills/backlog_senkron.py` + UI `page-backlog-senkron`)
Product'ın **UAT board'unda** (MBSUATEAM) açtığı taskları bizim **TRADE/OPS board**
(MBSTRADE/MBSOPS) tasklarıyla karşılaştırır; hangi UAT maddesinin işleme alınmadığını (açıkta
kalan iş) ve hangi hedef taskın kaynağının UAT'de bulunmadığını ortaya çıkarır. Analist tek tıkla
çalıştırır, sonucu ekranda görür, çok sayfalı Excel raporu indirir. **Excel girişi YOK** (eski
takip-Excel senkron akışı — upload + cerrahi lxml yazımı — bu sürümde kaldırıldı).
- **0 LLM tokenı — tamamen deterministik.** `claude -p`/MCP ÇAĞRILMAZ; yalnızca Jira REST okuması +
  openpyxl ile sıfırdan .xlsx yazımı (yeni dosya → cerrahi zip korumasına gerek yok).
- **İki board'u çek:** `mutabakat(uat_proje, hedef_projeler, mod, hedef_keys, anahtar_kelime)`. UAT
  board'u HER ZAMAN tam taranır (`project = UAT`). Hedef tarafı `mod`'a göre toplanır:
  `tum` (`project in (hedef...)`), `epic` (her key için `alt_gorevleri_cek` — parent+Epic Link+
  linkedIssues birleşimi; sonuç **hedef board'lara göre filtrelenir** = epic altındaki ama başka
  projedeki görevler elenir → tüm board yerine ilgili alt küme, token/zaman tasarrufu),
  `keyword` (`project in (...) AND text ~ "kelime"`). JQL literal'leri
  `_jql_kacis` ile kaçışlanır. Görevler `jira_gorevleri._issue_ayrıstir` ile ayrıştırılır (özet,
  durum, açıklama, **baglantililar** = issue-link listesi).
- **Katmanlı eşleştirme (güçlüden zayıfa):**
  1. **KESİN** — UAT ile hedef arasında zaten Jira issue-link var (iki yön de taranır, tekrarsız).
  2. **YÜKSEK** — link yok ama başlık+içerik Jaccard benzerliği `ESIK_YUKSEK` (0.55) üstünde →
     otomatik eşleşme. Jetonlar `jira_gorevleri._benzerlik_jetonlari` (başlık + açıklama ilk 300).
  3. **ADAY** — Jaccard `ESIK_ORTA` (0.35) ile `ESIK_YUKSEK` arası → analist teyit eder.
  4. **EŞLEŞMEYEN** — UAT tarafı (açıkta kalan iş) VE hedef tarafı (kaynağı UAT'de olmayan) ayrı ayrı.
  Dönüş: `eslesenler`, `adaylar`, `eslesmeyen_uat`, `eslesmeyen_hedef`, `sayimlar`, `jira_url`.
- **Eşleştirme incelikleri (sonraki eklemeler):**
  - **Kapsam dışı hedef:** UAT issue-link'i hedef-projedeki bir key'e işaret ediyorsa, o hedef taranan sette
    olmasa bile `_keyleri_cek` ile çekilip KESİN eşleşmeye dahil edilir.
  - **Story köprüsü (dolaylı/transitif):** UAT ve hedef task AYNI Story/Hikaye'ye bağlıysa eşleşir —
    `_story_baglari`: Story tipli issue-link VEYA Story tipli **parent** (alt görev doğrudan Story altında);
    yalnız Story seviyesi, Epic hariç (parser `parent_key`/`parent_type` verir).
  - **Kapsam dışı bırakılanlar:** Epic/Story (kapsayıcı) tipler + UAT board'unda `UAT_HARIC_DURUMLAR`
    ("Created in Error" vb.). **İptaller** (İptal Edildi/CANCEL/CANCELED — `_iptal_statusu_mu`) ana akıştan
    ayrılıp ayrı `iptaller` kovasında toplanır (JQL `status NOT IN` + elde güvenlik ağı).
  - **Atanan (assignee):** UAT ve hedef task'ların atananı da çıktıda (`uat_atanan`/`hedef_atanan`/`atanan`) →
    ekranda kolon + Durum/Atanan başlık filtreleri (istemci taraflı, AND); Excel raporunda Atanan kolonu.
- **`jira_url` (browse link'leri için):** canonical `atlassian.jira_site_url()` accessible-resources
  endpoint'inden cloud_id eşleşmesiyle site adresini (ör. `https://firma.atlassian.net`) alır, süreç
  boyunca cache'ler. **`.env` `JIRA_URL`'e GÜVENMEZ** — o bazı kurulumlarda OAuth callback adresini tutuyor;
  yalnızca `.atlassian.net` içeriyorsa yedek olarak kullanılır. Aynı helper `jira_agent.py` task-oluşturma
  browse link'lerinde de kullanılır (tek kaynak).
- **Sıralama:** tüm kovalar UAT sıra no'suna (`_sira_no` = key sonundaki sayı, MBSUATEAM-116→116; hedef
  kovası kendi key no'suna) göre ARTAN sıralanır → karışık liste değil 1,2,3… Her satırda `sira` alanı;
  UI ve export'ta ilk kolon "Sıra".
- **Export (`rapor_uret`):** openpyxl `Workbook` ile sıfırdan 3 sayfa: `Eşleşenler` (Sıra + eşleşen+aday,
  **Eşleşme** (Evet/Aday) + Gerekçe kolonlu), `Eşleşmeyen UAT`, `Eşleşmeyen TRADE-OPS` (hepsi Sıra kolonlu).
  Başlık dolgusu + freeze + autoFilter. UI'da (export'a yansımaz): stat kartları FİLTRE'dir (`bsFiltrele` —
  tıkla → yalnızca o grup görünür, aktif karta tekrar tıkla → tümü); satır rozetleri (✓ Eşleşti / ● Aday /
  ✕ Eşleşmedi); task key'leri Jira browse link'i (bold + ↗, yeni sekme); UAT durumu ≠ Hedef durumu olan
  satırlarda iki durum hücresi amber + "≠" ile vurgulanır (`bs-durum-fark`).
  Zaman damgalı `UAT_Mutabakat_YYYY-MM-DD_HHMM.xlsx`, `backlog/` altına.
- **Takip & kontrol amacı (UAT sürecinde product işlerinin önceliklendirilip analiz edilerek geliştirmeye
  atanması):** her UAT maddesi için **takip aşaması** (`takip_asamasi`) + her TRADE/OPS task'ı için **analiz
  durumu** (`analiz_durumu`) — 0 token, açıklamalar mutabakatta zaten çekilir (ek Jira çağrısı YOK).
  - **`analiz_durumu(aciklama)`** → `yapildi|kismi|yok`: ADF→metinde başlıklar kendi satırına düşer; bizim
    şablon başlıkları (`_ANALIZ_BASLIKLARI`: süreç→teknik 11 bölüm · Task analizi · FE/BE task şablonu · hata
    modu Sorun/Çözüm · köprü 🤖 Teknik Analiz · ekip formatı Mevcut Durum/Beklenen Davranış/Teknik Tasarım
    Önerisi) aranır; altında ≥60 krk içerik olan "dolu". **yapildi:** ≥3 dolu + çözüm tarafı (teknik) · ≥4
    dolu + amaç ve kabul kriteri tarafı (işlevsel) · Çözüm + (Sorun ya da kriter) (hata) · **kismi:** 1-2 dolu
    ya da şablonsuz ≥800 krk (serbest metin) · **yok:** boş/kısa. Gerçek veride kalibre edildi (kısa
    "Amaç + Kabul Kriteri" product brief'leri = kısmi).
  - **Geliştirmeye atanmamış = yalnız `Backlog`** (`GELISTIRME_ONCESI`). **`takip_asamasi`** (UAT başına):
    Kapandı (UAT durumu `TAMAM_DURUMLARI`) · Açıkta (task yok) · Teyit bekliyor (yalnız aday) · Analiz bekliyor
    (Backlog task'larından biri analizsiz) · Analiz kısmi · Atamaya hazır (Backlog task'ları analizli) ·
    Geliştirmede/sonrası (Backlog'da task kalmadı). Satır alanları: `takip`/`takip_kod`, `uat_analizli` ("x/y"),
    `hedef_analiz`/`_seviye`/`_dolu`, `hedef_kapsam_disi`; eşleşmeyen hedefte `analiz*`, eşleşmeyen UAT'ta `takip`.
  - **Sayımlar — TEKİL task, denklem olarak kapanır:** `uat_toplam = uat_eslesen + uat_aday + eslesmeyen_uat`
    (+`uat_iptal` ayrı, `uat_kapsayici_haric` Epic/Story) · `hedef_toplam = hedef_eslesen + hedef_aday +
    eslesmeyen_hedef` (+`hedef_iptal`, `eslesmeyen_hedef_aktif/_tamam`) · `bag` = UAT↔task çifti (eski `eslesen`
    satır sayısı — geriye uyum için durur; bir UAT 26 task'a, bir task birden çok UAT'a bağlanabildiği için task
    sayısı DEĞİL) · `takip{}` (toplamı = uat_toplam) · `backlog_analiz{yapildi,kismi,yok}` (Backlog'daki tekil
    eşleşen task'lar). **Story/Hikaye analiz EDİLMEZ** (kapsayıcı — hiçbir zaman hedef satırı olmaz); analiz
    durumu Story'nin alt/bağlı task'larından hesaplanır. **Story genişletme:** UAT bir Story'ye bağlı ama Story'nin
    task'ları taranan kapsamda yoksa (ör. epic modunda Story başka epic'te) `alt_gorevleri_cek(story)` ile alt
    task'lar çekilir (hedef board, kapsayıcı/iptal hariç) → Story köprüsüyle eşleşir, `hedef_kapsam_disi` (toplama
    girmez) → UAT "açıkta/analiz yok" sanılmaz. **Epic modu:** yalnız epic altı sayılır; kapsam dışından Jira linkiyle gelen task UAT'ı
    eşleştirir (iş takip ediliyor) ama `kapsam_disi_hedef` olarak AYRI sayılır, toplama girmez. **Tüm board
    modunda** eşleşmeyen TRADE/OPS = "UAT dışı proje işi" (sönük, problem değil).
  - **UI: ORİJİNAL ekran korunur (owner kararı — kompakt pano/huni/analiz kartları kullanışsız bulundu, geri
    alındı).** Ekran yalnız eşleşen/aday/eşleşmeyen/iptal kartları + tabloları gösterir; takip aşaması ve analiz
    durumu alanları backend'de hesaplanmaya devam eder (satırlarda + `sayimlar`) ve **Excel raporunda** görünür
    (Özet sayfası + Takip/Analiz/Dolu Başlıklar kolonları). Ekrana yeniden taşınacaksa önceki denemeler git
    geçmişinde: `4c0ca14` (büyük kartlar) · `2966a58` (kompakt pano). Ekranın üstünde **UAT Durum Senkronu** paneli.
  Test: `tests/test_backlog_analiz.py` (Jira MOCK, 0 token).
- **Endpoint'ler:** `POST /api/backlog/mutabakat` (config → kova JSON) · `POST /api/backlog/export`
  (sonuç body → `{dosya}`) · `GET /api/backlog/indir/<dosya>` (binary `send_file`). Dosyalar `backlog/`
  altında (gitignore). Bağımlılık: `openpyxl` (requirements.txt).

### UAT Durum Senkronu (`skills/uat_durum_senkron.py` + UAT Mutabakat ekranındaki `#us-panel`)
TRADE/OPS task'ı geliştirmeye alınınca ilişkili UAT task'ını Jira'da **'Devam Ediyor'a TAŞIR** (analist elle güncellemez).
- **Kural (owner kararı):** UAT task'ı **Backlog / Yapılacaklar**'da (`uat_kaynak_durumlar`; Hold/Tamam/İptal'e DOKUNULMAZ,
  geri yön YOK, UAT tarafındaki Epic/Story kalem sayılmaz) + **DOĞRUDAN Jira linkiyle** bağlı (Story köprüsü KULLANILMAZ,
  Epic/Story tipli link sayılmaz) TRADE/OPS task'ı **Devam Ediyor ve sonrası** (`tetik_durumlar`: Devam Ediyor, Test,
  READY FOR TEST, TEST BLOCKED, UAT, Tamam…; iptal hariç) → `hedef_durum` ('Devam Ediyor'). Bağlı task'ın durumu
  issue-link verisinde gelir (`_issuelink_ayikla.durum`) → tek JQL (`project=UAT AND status IN (Backlog, Yapılacaklar)`),
  ek okuma yok. `plan_hesapla` deterministik (Jira'ya yazmaz).
- **Taşıma (`tasi`):** `GET /issue/{key}/transitions` → hedef duruma giden geçiş (`to.name`, yoksa geçiş adı) →
  `POST .../transitions` (204) + `jira_kopru.jira_yorum_ekle` ile "🤖 Analyst Studio — otomatik durum güncellemesi:
  …" yorumu. Geçiş yoksa net hata (mümkün geçişler listelenir), yazma yok. İdempotent: yalnız hâlâ Backlog/Yapılacaklar
  olan UAT taşınır → birden çok makinede açık olsa da çift işlem olmaz.
- **Güvenli devreye alma:** varsayılan **KAPALI** + **rapor modu** (`mod:'rapor'` — "şunları taşıyacaktım" listesi,
  Jira'ya YAZMAZ); analist "Otomatiğe geç" (onaylı) → `mod:'otomatik'`. Ayar `reference/uat_senkron.json`
  (makine-yerel, **gitignore**); durum/plan/sonuç/geçmiş (son 300) `output/uat-senkron/durum.json`.
- **Zamanlama (app.py):** `_uat_senkron_dongusu` boot'ta HER ZAMAN başlar, ayarı dakikada bir okur (ekrandan aç/kapa
  restart istemez); `sira_geldi_mi` (aktif + `aralik_sn` vars. 7200 = 2 saat, alt sınır 600) dolunca `tur()`. Hata →
  `hata_kaydet` (tur zamanını DEĞİŞTİRMEZ) + 10 dk sonra tekrar. `_uat_senkron_lock` tek tur. Taşınan varsa yerel
  bildirim. **Yalnız uygulama açıkken çalışır** (Jira Köprüsü gibi). 0 token.
- **Uçlar** (kimlik-gate `/api/uat-senkron`): `GET /api/uat-senkron/durum` · `POST /api/uat-senkron/ayar {aktif?, mod?,
  aralik_sn?}` · `POST /api/uat-senkron/calistir {uygula: true|false|null}` (arka plan; null = ayardaki mod; 409 sürüyorsa).
- **UI:** durum satırı (Kapalı/Rapor/Otomatik · son/sonraki kontrol · son hata) + Aç/Kapat · "Şimdi kontrol et (rapor)" ·
  "Otomatiğe geç" / "Rapor moduna dön" · rapor listesi varken "Bu listeyi şimdi uygula" (onaylı) · son tur sonuç tablosu ·
  Geçmiş. Test: `tests/test_uat_senkron.py` (Jira MOCK — rapor modunda yazma YOK doğrulanır).

### Kabul Kontrolü (`skills/kabul_kontrolu.py`) — ANALIZ CHECK task'ını testçi gibi CANLI doğrula
Geliştirmesi biten task'ı analist agent'a verir; agent test ortamında uygulamaya girip task'taki isterleri
FİİLEN dener; eksik varsa iş geliştirmeye döner, tamsa analist test ekibine iletir (karar ANALİSTİN — owner kararı).
- **Akış (3 adım):** (1) `kabul_listesi_cikar` — 1 AI çağrısı (`_LISTE_SISTEM`): açıklamadaki analizden
  DENENEBİLİR kabul maddeleri `<kabul_listesi>` JSON (tür: alan · buton · validasyon · mesaj · servis · veri · rol ·
  bos_durum; `nasil`/`beklenen`/`ref`; ≤25; ekrandan doğrulanamayan → `denenebilir:false` = "ekran dışı", denenmez).
  (2) `canli_dogrula` — mevcut canlı-gözlem altyapısı (`canli_uygulama_baglami_hazirla(base_url_override,
  hedef_tarif)`; hedef `live_app_gorev`, yoksa `live_app` base; `live_app_auth` login) + `_kontrol_talimati`
  (gözlem DEĞİL doğrulama görevi: her maddeyi dene, boş/geçersiz değeri gerçekten gönder, isteği
  `browser_network_request` ile yakala, yazma işlemleri GERÇEK + `AI-TEST` öneki, tahmin YASAK) →
  `_api_cagri(onbellek=False, canli_uygulama_kapsami="gorev")` → `<kabul_sonuc>` JSON. (3) `_sonuc_normalize`:
  madde başına `dogrulandi|eksik|dogrulanamadi` (geçersiz/bildirilmemiş → `dogrulanamadi`, tahmin yok) →
  **sonuç:** ≥1 eksik → `geri` · hepsi doğrulandı → `teste_hazir` · doğrulandı + doğrulanamayan → `teste_hazir_kismi`
  · hiç doğrulanan yok → `dogrulanamadi`. Canlı hedef yoksa AI çağrılmaz, net neden. `rapor_md` → yorum metni
  (sonuç etiketi, madde tablosu + kanıt `[K: Canlı UI/Network]`, "Geliştirmeye dönecek maddeler", yazma
  işlemleri, gezilemeyen, "_Durum değiştirilmedi_").
- **Analist promptuyla hizalama (2026-10-16 — ekip arkadaşının "DEV kabul kriterleri doğrulaması" promptu içeri
  alındı):** (1) **Kabul kriteri birimi:** `_LISTE_SISTEM` "KABUL KRİTERLERİ BİRİNCİLDİR" — task'ta AC-n / Kabul
  Kriterleri varsa her kriter ≥1 madde, `ref`=AC-n; `_kriterler()` madde sonuçlarını kritere toplar (≥1 eksik → eksik ·
  hepsi ✓ → dogrulandi · yalnız ekran dışı → ekran_disi · aksi → dogrulanamadi; `_kriter_anahtar`: `§5 AC-2` → `AC-2`,
  ref'siz madde kendi kriteri) → `kriter_sayim` (toplam / karşılanan / karşılanmayan / doğrulanamayan). (2) **BE/FE:**
  BE task'ı kriterleri ENDPOINT üzerinden (network: method/path/status/alan/hata kodu, ör. silme engeli 409), FE ekran
  davranışından; GET/POST/PUT/DELETE hepsi test ortamında serbest (AI-TEST). `_kontrol_talimati` çerçevesi: "yeni task
  önerme, çok başlıklı analiz yazma — TEK çıktı: kriterler karşılanıyor mu". (3) **`talimat` (opsiyonel):** UI
  `jgKabulKontrol` `prompt()` → adım `talimat`; köprü `kontrol <talimat>`; içinde URL varsa `_hedef_url` → canlı görev
  o ekrandan BAŞLAR (`base_url_override`=tam URL), yoksa bağlam filtresi ANA adresi; talimat liste promptuna ve
  kontrol talimatına "ANALİST TALİMATI (öncelikli)" olarak girer. (4) **İlgili task'lar** (`gorev.baglantililar` →
  `_ilgili_tasklar`): FE/BE bağlı task başlıkları hedef tarifine + rapora ("İlgili task: KEY (FE)"). (5) **Rapor
  (`rapor_md`, analist yapısı):** başlık bloğu `Task · Konu · Ortam (_ortam_adi: DEV/UAT + host) · İlgili task` →
  `### Doğrulama Sonucu` (Toplam kabul kriteri / Karşılanan / Karşılanmayan / Doğrulanamayan (AC listesi) / Ekran dışı /
  Netleştirilmesi gereken konu) → `**Genel değerlendirme:**` (`genel_not`, 2-4 cümle) → `### Öne çıkan bulgular`
  (`bulgular`, kanıtlı) → `### Kriter bazında sonuç` tablosu (Kriter | Madde | Durum | Kanıt) → Geliştirmeye dönecek
  maddeler → `### Netleştirilmesi gereken konular` (`acik_konular`) → yazma işlemleri → gezilemeyen → `**Sonuç:** N
  kabul kriteri karşılanmıştır. [M karşılanmadı → geri.] [AC-x ile doğrulanamayan senaryolar tamamlanmadan tüm kapsamın
  doğrulandığı kabul edilmemelidir.]` → durum notu. `<kabul_sonuc>` JSON'una `bulgular` + `acik_konular` eklendi. UI
  özet satırı kriter sayımını + ortamı gösterir.
- **Listeden doğrudan (2026-10-19 — owner: 'ANALIZ CHECK task'ı seçince başlat butonu olsun, tekrar analiz yapmasın'):**
  görev kartındaki **'🧪 Kabul Kontrolü'** (`jgKabulKontrolBaslat`; statü check/kontrol/test ise yeşil vurgulu 'Başlat') →
  opsiyonel talimat → `_jgIsBaslat([{mode:'kabul-kontrol', markdown:'', gorev}])` — teknik analiz ÜRETİLMEZ, task
  içeriğindeki kabul kriterleri + canlı gözlemle doğrulanır (giriş kapısından geçer). Sonuç `kabulOnly` entry: panel
  başlığı 'Kabul Kontrolü — KEY', editörde rapor markdown'ı, Onayla/Eğitime Ekle/Düzelt kapalı, 'Jira'dan içeriği çek'
  önerilmez; 'Raporu Jira'ya yorum olarak yaz' çalışır.
- **Kanallar:** Task Analizi önizleme → **"Kabul Kontrolü"** (`jgKabulKontrol`, onaylı; iş modu `kabul-kontrol`
  → `sonuc.kabul{markdown,sonuc,sayim,maddeler}`; analiz içeriğine DOKUNMAZ, eğitim havuzuna GİRMEZ) → `_jgKabulGoster`
  (özet + madde listesi) + **"Raporu Jira'ya yorum olarak yaz"** (`POST /api/jira/gorev/kabul-yorum {key, markdown}` →
  `jira_yorum_ekle`). Jira Köprüsü: `/analyst_agent kontrol` (eş anlam: kabul · doğrula · verify · check) →
  `_kontrol_islet` → rapor yorum. **Jira durumu HİÇBİR kanalda değişmez.** Maliyet: task başına 2 AI çağrısı
  (liste + canlı doğrulama; canlı doğrulama CLI/Playwright, `LIVE_APP_CLI_TIMEOUT`). Test: `tests/test_kabul_kontrolu.py`.

## İnteraktif Analiz — Ekran Bazlı İş (sohbet → ekran başına FE/BE task)
Owner isteri: "BRD ile uygulamaya gir, BRD'deki isterlere göre ekranları kontrol et, her ekran için BE+FE task aç; analist
isteri adım adım oluştursun, agent soru sorsun, açık soruları sırayla sorsun." Sohbet ekranı büyütüldü (yeni ekran yok):
1. **Girişi Test Et** — `giris_testi()`: `_canli_tabanli_baglam` (miras `live_app` ANA adresi + hedef) ile 1 CLI/Playwright
   çağrısı; `<giris_sonuc>{ok,neden,ekran,menu}`; `oturum.giris` + sohbete sistem mesajı + ekranda durum bandı. URL yoksa AI
   çağrılmaz. Amaç: "Wrong Password" gibi erişim sorununu dakikalarca süren gözlem/üretimden ÖNCE yakalamak.
2. **🌐 Canlı gözlemle yanıtla** — mesaj `{gozlem:true}` → `_sohbet_is_baslat('gozlem')` (arka plan; çip/HUD "canlı gözlemli
   yanıt") → `sohbet_mesaj(metin, gozlem=True)`: analist mesajı HEMEN yazılır (yeniden bağlanma), canlı görev bloğu + "sohbet
   tonunda gözlem" talimatı, `_api_cagri(onbellek=False, canli_uygulama_kapsami='surec')`; yanıt `gozlem` bayraklı.
3. **Sıralı açık sorular** — UI `_shSorulariYukle` (`/api/sorular`, bu oturumun `surec-analizi.md/teknik-analiz.md/
   acik-sorular.md` açık soruları) → tek tek kart (Cevapla→sonraki · Varsayım · Atla → `POST /api/sorular/<id>`) → sonunda
   "Cevapları analize uygula" (`/api/sorular/uygula`). `_cevaplanan_sorular_metni()` (bu oturum: `guncellendi_at` ≥ ilk mesaj)
   sohbet turuna "CEVAPLANAN SORULAR" bloğu + üretim girdisine "Analistin kesin cevapları" olarak girer → tekrar sorulmaz.
   Sistem promptu: aynı anda en fazla 1-2 soru (sırayla), BRD referansta hazır, hedef ekran bazlı iş.
4. **Ekran Task'ları Üret** — `ekran_listesi_cikar()` (1 AI: sohbet + RAG/BRD → `<ekranlar>[{ad,menu,ister,brd_ref,not}]`,
   ≤40) → `oturum.ekranlar` + seçim tablosu → `ekran_gorevleri(secilen)`: sentetik görev `EKRAN-n` (summary "menü › ekran"
   — menü zaten ekran adıyla bitiyorsa tekrar eklenmez; description = ister + BRD ref + kesin cevaplar + sohbet bağlamı) +
   `canli_hedef` → `mode:'fe-be-ayir'` adımları → UI `_jgGorevler[key]=gorev` + `_jgIsBaslat` + `switchTab('jira-gorevler')`.
   `_adim_isle`: `canli_hedef` → `_canli_tabanli_baglam` → `canli_baglam_override` (live_app_gorev DEĞİL, miras ana adres +
   ekran hedefi). Sonuç Task Analizi'nde ekran başına BE+FE entry; Jira'ya **Yeni Task Aç** (fe-be mode, Epic'e Relates).
   Korumalar: `jira_gorev_is_baslat` tüm adımlar görev dict'li (description'lı) ise Jira bağlantısı istemez, ≤12 adım;
   sentetik `EKRAN-` eğitim havuzu/depoya girmez; `gorev_yeni_task_olustur` geçersiz kaynak anahtarına bağ kurmaz; UI
   sentetik kayıtta 'Onayla ve Jira'da Güncelle' kapalı (Jira'da task yok). Test: `tests/test_sohbet_ekran.py`.

### BFF Keşfi (`skills/bff_kesif.py`) — agent'ın KENDİ CRUD gözlemiyle ekran servis sözleşmesi
Owner isteri: Task Analizi'nde ekrandaki BFF'leri canlı gözlemlemek için analist elle create/update/delete yapmak
zorunda kalıyordu → agent bunu kendisi yapar. Kararlar: otomatik + buton; AI-TEST kayıtları KALIR (silme ayrı ikinci
kayıtta denenir); rapor 7 gün önbellek.
- **Plan (`_kesif_plani`, odaklı gözlem kapsamı olarak `canli_uygulama_baglami_hazirla(hedef_tarif=plan)` — mevcut
  CRUD/verimlilik/maskeleme kuralları dahil):** 1 liste+lookup (filtre/sayfalama 1 kez) · 2 OLUŞTUR `AI-TEST-<MMDD-HHMM>`
  (POST payload+yanıt, kayıt KALIR) · 3 DOĞRULAMA (zorunlu alan boş, 1 kez) · 4 GÜNCELLE (PUT/PATCH, kalır) · 5 SİL
  (`AI-TEST-…-SIL` ayrı kayıt → DELETE) · 6 diğer aksiyonlar yalnız kendi kaydında, geri alınamaz olanlar HARİÇ ·
  yapılamayan → "Gezilemeyen". Çıktı `<bff_rapor>` sabit bölümler (Ekran · Açılış/liste servisleri · Form alanları ·
  CREATE · DOĞRULAMA · UPDATE · DELETE · Diğer aksiyonlar · Bırakılan AI-TEST kayıtları · Gezilemeyen).
- **Hedef:** `ekran_bazli=True` (İnteraktif Analiz ekran işi, `canli_hedef`) → miras `live_app` ANA adresi + ekran
  tarifi, `canli_uygulama_kapsami='surec'`; değilse `live_app_gorev` hedefi, `'gorev'`. Hedef yoksa AI çağrılmaz.
- **Depo/önbellek:** `reference/live-app/bff/<sha1(url|ekran)[:12]>.md` (+`.json` {ts, ok, hedef_url, ekran}).
  `rapor_oku` · `taze_mi` (ok ∧ yaş < 7 gün) · `rapor_blogu` (prompt bloğu: "GERÇEK gözlem; burada olmayan endpoint
  UYDURMA"). Blok yoksa kaydedilmez; CREATE/servis bölümü yoksa `ok=False` (kaydedilir ama taze sayılmaz).
  `reference/live-app` RAG corpus'unda (`rglob`) → raporlar tüm analizlere referans olarak da girer.
- **Entegrasyon (app `_adim_isle`):** mod `analiz`/`fe-be-ayir`/`bff-kesif` → hedef URL + tarif → `rapor_oku`; `bff-kesif`
  ya da (taze değil ∧ `otomatik_acik()`) → `job.aktif_not` = "BFF keşfi — ekranda CRUD gözlemi" → `kesfet` → `rapor_blogu`
  → `gorev_analiz_et(bff_rapor=…)` / `gorev_fe_be_analiz(bff_rapor=…)` (stable blok, canlı görevden önce). `bff-kesif`
  sonucu `sonuc.bff{ok,md,ts,yas_gun,anahtar,neden,yol}` (analiz içeriğine dokunmaz, eğitim havuzuna girmez).
  `/api/jira/gorev/is/durum.aktif_not` → UI işlem başlığı. Ayar `live_app_gorev.bff_otomatik` (vars. true; Task ekranı
  "BFF keşfi otomatik" kutusu; `_context_filter_normalize` + `/api/context-filter` korur). UI: "BFF Keşfi (CRUD)" butonu
  (`jgBffKesif`, onaylı) + `_jgBffGoster` (durum + "Raporu gör"); ekran-bazlı sentetik görevlerde `canli_hedef` görev
  dict'inde de taşınır (`_adim_isle` her ikisini okur). Maliyet: ekran başına 1 canlı CLI çağrısı (5-10 dk), 7 günde bir.
  Test: `tests/test_bff_kesif.py`.

### BFF Keşfi — İnteraktif Analiz'den
Aynı motor (`skills/bff_kesif.py`), sohbet ekranından: `sohbet_analiz.bff_kesfet(ekran)` → miras `live_app` ANA adresi +
ekran tarifi (`ekran_bazli=True`, 'surec' kapsamı) → rapor (anahtar = URL + ekran, Task Analizi ile ortak depo) →
`oturum.bff[]` (ekran başına tek kayıt) + sohbete sistem mesajı (`bff_anahtar` → UI "Raporu gör" → `GET /api/sohbet/
bff-rapor?anahtar=<12 hex>`). `_bff_raporlari_blogu()` oturumun taze (7 gün, ok) raporlarını `rapor_blogu` ile her sohbet
turuna (kullanıcı/asistan çifti) ve `_uretim_girdisi`'ne (Süreç/Teknik üretim, girdi listesinin BAŞINA) ekler. Üretim
öncesi otomatik keşif YOK (owner: yalnız mevcut raporlar); "Ekran Task'ları Üret" yolu Task iş sistemine düştüğü için orada
otomatik keşif zaten çalışır. UI: kilometre taşı satırında "BFF Keşfi (CRUD)" (prompt ile ekran; envanterdeki ilk ekran
varsayılan) + envanter tablosunda satır başına 🔌 BFF; iş hedefi `bff` çip/HUD'da "BFF keşfi (ekranda CRUD)".
`POST /api/sohbet/bff-kesif {ekran}` (URL yoksa 400). Test: `tests/test_sohbet_bff.py`.

## Jira Görevleri Özelliği (`skills/jira_gorevleri.py` + UI `page-jira-gorevler`)
Doküman yüklemeden, **mevcut** Jira Epic/Story altındaki görevleri çekip triyaj eder.
- **Çekme — İKİ AŞAMALI (keşif + taze okuma):**
  1. **Keşif (arama):** `alt_gorevleri_cek` üç bağ modelini birleştirir (tekrarsız):
     `parent = KEY` (sub-task), `"Epic Link" = KEY` (epic), `issue in linkedIssues(KEY)`
     (Relates — bazı ekipler hiyerarşi yerine kullanır). Bu aşama yalnızca HANGİ issue'ların
     bağlı olduğunu belirler. `parent_key` JQL'e girmeden `_ID_DESENI` ile doğrulanır (enjeksiyon engeli).
  2. **Taze içerik (`_taze_issue_oku` → `POST /rest/api/3/issue/bulkfetch`, 100'lük parçalar):**
     başlık/açıklama/yorum/bağlantılar DOĞRUDAN issue'dan okunur.
     **NEDEN:** `/rest/api/3/search/jql` sonuçları arama İNDEKSİNDEN gelir ve indeks
     eventually-consistent'tır — Atlassian dokümanı: *"Recent updates might not be immediately
     visible in the returned search results."* Bu yüzden Jira'da bir task'ın başlığı/açıklaması
     güncellendikten sonra görevler yeniden çekilse bile ESKİ içerik dönebiliyordu. bulkfetch
     indeksi atlar → güncellemeler anında görünür. bulkfetch başarısız olursa (yetki/endpoint)
     arama sonucuna düşülür — akış kırılmaz, yalnızca bayat olabilir.
  3. **Girilen anahtarın KENDİSİ (`_kapsayici_mi`):** Epic/Story ise *kapsayıcı* sayılır ve
     listede yer almaz (analist altındaki görevleri ister — eski davranış). Görev/Bug gibi
     *yaprak* iş kaleminde ise analistin asıl incelemek istediği şey odur → listenin EN ÜSTÜNE
     eklenir (kendisi + bağlı task'ları). **DİKKAT:** Jira'da Story ve Task AYNI
     `hierarchyLevel`'a (0) sahiptir — gerçek Jira'da doğrulandı (Hikaye=0, Görev=0) — bu yüzden
     ayrım tip ADIna göre yapılır (`_KAPSAYICI_TIP_ADLARI`: epic/epik/story/hikaye/initiative);
     `hierarchyLevel >= 1` her hâlükârda kapsayıcıdır (özel epic adlarını da kapsar).
  Ortak ayrıştırma `_issue_ayrıstir` (arama + bulkfetch aynı fonksiyonu kullanır): yorumlar
  (ADF→metin) ve `issuelinks` (`_issuelink_ayikla` → `baglantililar`: bağlı task key/summary/tip/
  ilişki + kaba `katman` tahmini be/fe/belirsiz `_katman_tahmin` ile).
- **İki fazlı sınıflandırma:** FAZ 1 (`/cek`, `ai_kullan=False`) yapısal ön-tarama (`_yapisal_skor`),
  anında 0 token, `kaynak=yapisal`. FAZ 2 (`/siniflandir`, "AI ile Sınıflandır") AI her görevi içerikten
  okur (parçalı), `kaynak=ai`, opt-in.
- **Sadece Client ayıklama** (`/gorevler/sadece-client`, "Sadece Client İşleri" butonu — opt-in): AI her
  görevi + BAĞLI task'larını inceleyip HİÇBİR BFF/BE değişikliği gerektirmeden yalnızca frontend'de
  tamamlanabilecekleri ayırır (`sadece_client_ayikla` → `{sadece_client, diger}`). Bağlı BE task'ı olan
  görev "sadece client" DEĞİLDİR (isterin sunucu tarafı ayrı task'ta geliştiriliyor). Emin olunamayan
  görevler güvenlik gereği `diger`e düşer (false-negatif, false-pozitiften güvenli). AI çağıramazsa
  (`_sadece_client_ai` boş dönerse) hiçbir görev "sadece client" KESİNLEŞTİRİLMEZ (fallback → hepsi `diger`).
  **PARÇALI TASARIM (çok görevde timeout/askıda kalma önlemi):** Endpoint tek batch alır
  (`{gorevler: [...]}`, en fazla `SADECE_CLIENT_BATCH_LIMIT=25`; Jira'dan yeniden çekmez, görevler
  client'tan gelir — `/formatla`, `/analiz` deseniyle aynı). Frontend tüm görevleri `SC_BATCH=20`'lik
  gruplara bölüp arka arkaya çağırır (`jgSadeceClient` döngüsü): her istek SINIRLI sürer (tek AI çağrısı),
  kısmi sonuçlar her grup sonrası birikip render edilir, ilerleme gösterilir (`n/toplam`), bir grup hata
  alsa öncekiler korunur. Buton çalışırken "Durdur"a döner (`_jgScDurdur` → mevcut grup bitince durur).
  **Eski tek-istek tasarımı KALDIRILDI** — 200+ görevde tek HTTP isteği dakikalarca sürüp tarayıcıda
  timeout olurken sunucu arka planda öğütmeye (token harcamaya) devam ediyordu.
  UI: mevcut iki grubu bozmadan 3. grup `#jg-sc-group` (varsayılan gizli, butonla üretilir); yeniden
  çekmede bayat sonuç gizlenir.
- **Tüm Görevler + statü filtresi (UI, `#jg-tum-group` — 0 token, tamamen frontend):** sonuç alanının
  EN ÜSTÜNDE, çekilen tüm görevleri listeleyen ana başlık. İçinde dinamik **statü filtre çubuğu**
  (`#jg-status-filtre`) — görevlerdeki distinct Jira statülerinden sayaçlı chip'ler (`Tümü` + her statü).
  **Çoklu seçim** (`_jgStatusSecili` Set; boş=tümü), `jgStatusToggle`/`jgTumFiltrele`. Statü filtresi
  YALNIZCA bu başlığı süzer; mevcut arama (`jgFiltrele`) ile birlikte çalışır. Kartlar ortak
  `_jgKartHtml(g, sinif)` ile çizilir (her görev `_grup` etiketiyle hazir/detay sol-kenar rengini korur).
  Export ('tum') aktif filtreye göre. Mevcut iki grup + Sadece Client + aksiyonlar aynen korunur.
  **Atanan kişi:** her kartta atanan rozeti (`assignee` displayName; boşsa italik `ATANMAMIŞ`) +
  filtre çubuğunda **dropdown** (`jg-assignee-select`: Tümü / her isim sayaçlı / ATANMAMIŞ).
  `_jgAssigneeSecili` (`''`=tümü, `JG_ATANMAMIS`=atanmamış, veya isim). Statü chip'leri + arama ile
  birlikte `_jgTumFiltreliListe()` üzerinden AND'lenir; yalnızca "Tüm Görevler"i süzer. `assignee`
  alanı Jira'dan zaten `_issue_ayrıstir` ile geliyor → 0 token, tamamen frontend.
- **Analist Notu (opsiyonel, `context_filter.json → gorev_analist_notu`):** Jira Görevleri ekranındaki
  textarea (`jg-analist-notu`, canlı-uygulamadan bağımsız; `jgAnalistNotuKaydet`/`jgAnalistNotuTemizle`,
  PATCH ile yalnızca kendi anahtarını yazar). Doluysa `gorev_analiz_et` bunu analiz kullanıcı-mesajına
  belirgin bir talimat bloğu olarak ekler ("mevcut promptla BİRLİKTE çalışır, doğruluk/spekülasyon
  kurallarını GEVŞETMEZ"). Boşsa hiç eklenmez (token yok). YALNIZCA "Teknik Analiz Et"i etkiler
  (Formatla/Sınıflandır/Sadece Client değişmez). Not: `_context_filter_normalize` (base.py) ve
  `context_filter_kaydet`/`_oku` (app.py) bu anahtarı açıkça taşır — sabit-şema rebuild'i düşürmesin diye.
- **İptal edilenler hariç:** görev çekiminde (`/cek` ve `/siniflandir`) `iptal_ayikla` iptal statülü
  görevleri listeden çıkarır (`_iptal_statusu_mu` — İptal Edildi / İPTAL EDİLDİ / Cancelled / Canceled;
  `upper()` ile, Türkçe İ casefold sorununu atlar). Bağlı task'lara dokunulmaz. Yanıt `iptal_haric`
  sayısını taşır; UI'da kalıcı bilgi notu ("İptal edilmiş biletler listeye dahil edilmemiştir" +
  varsa "N iptal edilen görev çıkarıldı", `#jg-iptal-not`).
- **Benzer içerik:** `benzer_gorevleri_isaretle` Jaccard (eşik 0.35, 0 token) → kartta sarı uyarı + link.
- **Triyaj KAPSAMI — yalnızca Backlog + atanmamış (`_triyaja_uygun_mu`):** *Hızlı İşleme Alınacak* ve
  *Detaylı Analiz Gerekir* gruplarına YALNIZCA durumu Backlog VE atanmamış görevler girer (analistin
  işleme alıp detaylandıracağı fresh işler). UAT/TAMAM/READY FOR TEST/Devam Ediyor gibi ilerlemiş
  görevler triyaja alınmaz. `gorevleri_siniflandir` üç liste döndürür: `hazir`/`detay` (triyaj alt
  kümesi) + `tum` (TÜM görevler). AI sınıflandırma yalnızca uygun görevlerde çalışır (token tasarrufu).
  UI: "Tüm Görevler" başlığı `tum`'u gösterir (triyaj dışı kartlar nötr — durum/gerekçe yok);
  Sadece Client de `tum` üzerinde çalışır; aksiyonlar tüm görevlerde geçerli.
- **İki aksiyon:** *Hızlı İşleme Alınacak* → **Standart Formatla** (4 başlık, Haiku); *Detaylı Analiz
  Gerekir* → **Teknik Analiz Et** (Sonnet + RAG/bağlam filtresi + ayrı Haiku açık-sorular; modal'da
  2. sekme, Jira'ya yazılmaz). Sadece-client görevlerinde de aynı iki aksiyon kullanılabilir.
  **YALIN PROMPT (`gorev_teknik_analiz`):** `gorev_analiz_et` artık ağır 11-bölümlük
  `teknik_analiz_bolumler` şablonunu KULLANMAZ (o, süreç→teknik ana pipeline'a özgüdür). Görev-bazlı
  analiz uyarlanabilir yalın bir prompt kullanır: yalnızca görevin GERÇEKTEN dokunduğu bölümler
  (Amaç/Kapsam · Etkilenen Alanlar · Teknik Değişiklikler · Kabul Kriterleri) kısa yazılır, ilgisiz
  başlıklar HİÇ açılmaz ('kapsam dışı' dolgu yok). Basit görev 2-3 kısa bölüm olur → sistem promptu
  ~16K→~2K krk (~%87 girdi tasarrufu) + çok daha kısa çıktı. Kalite güvenceleri korunur (kaynak
  etiketleri `[K:...]`, uydurma yasağı, belirsizde `[K: ❓ Belirsiz]`, davranış testi varsa AC zorunlu).
  **SPEKÜLASYON YASAĞI:** gözleyemediği sunucu-içi nedeni tahmin etmez ('backend karşılığı ör.
  eksik provider config… olabilir', 'sunucu loglarından bakılmalı', '…gözlemlenemez' gibi olası-neden
  dizisi/gözlem-sınırı meta-notu YASAK); yalnızca gözlemlenen gerçeği yazar (ör. aksiyon→errorCode),
  gerisini kısa açık soruya bırakır. Canlı uygulama (MCP) promptunda da aynı kural
  (`canli_uygulama_baglami_hazirla` → "gözlemlenemeyenleri tahmin etme/sıralama"). Görev-dışı genel
  yorum/'incelenmeli' notu da yazmaz. Sistem Promptları'ndan düzenlenebilir.
- **UI:** arama/filtre, katlanabilir gruplar, tam ekran modal (`.jg-modal`, Esc), `_jgTabAktif` üst-bar guard.
  **Onayla** → `gorev_jiraya_yaz` Jira description'ı ÜZERİNE YAZAR (atlassian_put + markdown_to_adf; HTML yorumları silinir).

Soru Defteri durumları: `acik / bekleniyor / cevaplandi / atlandi / varsayim` (kalıcı `output/sorular.json`, atomik).
**Parse formatları (`parse_md_sorular`, öncelik sırasıyla):** (1) `### Q-T-001:` yapısal blok, (2) `| Q-001 |`
tablo satırı, (3) **fallback** — yapısal HİÇ soru yoksa `_parse_liste_sorulari`: "Açık Sorular" başlığı altındaki
düz NUMARALI liste (`1. …`) soruları yakalar, ID yoksa sıra numarasından türetir (`Q-001…`; merge (id,kaynak_dosya)
ile anahtarladığından dosyalar arası çakışmaz). Analiz açık soruları numaralı liste ürettiğinde (özel prompt/model
sapması) "Sorular" sekmesi artık boş kalmaz. Yapısal format varsa fallback TETİKLENMEZ (regresyon yok).
**Onay kapısında inline cevaplama (FE):** süreç ve teknik onay adımlarının KENDİSİNDE açık sorular tek-tek
cevap kutularıyla gösterilir (`_onaySorulariRender`/`_onaySoruKart`/`_onaySorulariUygula`, container
`#onay-sorular-surec|teknik`) — Sorular sekmesiyle AYNI backend (`/api/sorular/<id>` kaydet + `/api/sorular/uygula`
uygula, `_sorularUygulaBekle` poll). Boş kutu = atla; "Cevapları Uygula" → analiz güncellenir, sorular yakınsar,
sonra "Devam Et". Tam 5-aksiyon (Beklet/Varsayım/Atla) için "Sorular sekmesinde aç" linki durur. Render koruması:
analist yazarken ezmez (`dataset.dolu`), apply sonrası zorla tazeler, gate gizlenince sıfırlanır.

## Canlı Uygulama (Chrome MCP) — ekran + servis gözlemi
Bağlam filtresinde `live_app.target_url` (+ en fazla 5 `extra_urls`) doluysa süreç/teknik analiz
sırasında `claude -p` alt süreci gerçek uygulamayı gezip DOM + network (BFF) gözlemi toplar.

**KRİTİK — izin/araç zinciri (`skills/base.py`):**
- `_live_app_cli_argumanlari(kapsam: str|None)` **OPT-IN**'dir: yalnızca çağıran, mesajlarına
  GERÇEKTEN bir browsing talimatı (`canli_uygulama_baglami_hazirla()` çıktısı) eklediyse
  `kapsam="surec"` veya `kapsam="gorev"` verir ve o zaman şu argümanlar eklenir:
  `--mcp-config .mcp.live-app.json --strict-mcp-config --allowedTools <16 tarayıcı aracı>`.
  `kapsam=None` (varsayılan) → canlı uygulama HİÇ açılmaz, global URL tanımlı olsa bile.
- **Geçmiş bug (düzeltildi):** Eskiden bu kontrol yalnızca "global URL tanımlı mı" bakıyordu —
  browsing talimatı içermeyen HER `_api_cagri()` çağrısı (BRD analizi, kapsam analizi, HTML
  mockup, Jira görev sınıflandırma/"Standart Formatla", teknik analizin denetçi + açık-sorular
  aşamaları) de gereksiz yere Playwright MCP başlatıyordu — talimat olmadığı için tarayıcı hiç
  kullanılmıyordu ama her çağrı dakikalarca npx/Chrome başlatma yüküne katlanıyordu (bir teknik
  analiz koşusunda "🌐 Canlı uygulama modu" 3 kez basılıyordu, oysa yalnızca 1. aşama browsing
  talimatı içeriyordu). `canli_uygulama_kapsami` parametresi artık yalnızca gerçekten talimat
  içeren çağrılarda ("surec": `surec_analizi.yap`, `teknik_analiz`'in 1. aşaması;
  "gorev": `gorev_analiz_et`) veriliyor; diğer tüm çağrılar hiç geçmiyor → varsayılan olarak kapalı.
- `--allowedTools` VERİLMEZSE headless `-p` modunda izin sorulamaz → tarayıcı araçları
  **sessizce reddedilir** (`permission_denials`) ve özellik çalışmaz. Eski hata buydu.
- `live_app_mcp_config_yaz()` MUTLAK yollarla config üretir: `npx -y @playwright/mcp@latest
  --headless --browser chrome --user-data-dir .live-app-profile`.
- `_npx_yolu_bul()` PATH'e bağımlı değil (GUI minimal PATH); npx'in dizini `cli_env["PATH"]`e eklenir.
- `LIVE_APP_ALLOWED_TOOLS`: navigate/navigate_back/snapshot/**network_requests + network_request**/
  console/click/type/**fill_form**/press_key/hover/select_option/wait_for/handle_dialog/tabs/find.
  `browser_evaluate` (keyfi JS), `browser_file_upload`, cookie/localStorage/sessionStorage
  okuma-yazma, `browser_run_code_unsafe`, mouse-seviyesi kontrol, route interception, video/tracing
  bilinçli olarak DIŞARIDA (paket 0.0.78'de bunlar dahil ~65 araç var; yalnızca gözlem için
  gereken dar kapsamlı 16 tanesi allowlist'te — fill_form dahil; login + CRUD formları için).
- **Geçmiş bug (düzeltildi):** `browser_network_requests` (çoğul — numaralı liste döner) ile
  `browser_network_request` (tekil — listedeki bir isteğin tam header/body detayını döner) PAKETTE
  İKİ AYRI ARAÇ; eskiden yalnızca çoğul olan listede vardı. Model detay için tekili çağırınca
  headless `-p` modunda onay alamıyor, `permission_denials`'a bile düşmeden "Analist onayı
  bekleniyor" durumunda süresiz askıda kalıyordu (kullanıcı raporu: UI'da onaylayacak bir
  modal/alan da yok — headless modda zaten hiç olamaz). Artık ikisi de allowlist'te.

**Oturum/login:** `.live-app-profile/` kalıcı Chrome profili (gitignored, çerez içerir).
`POST /api/live-app/login` sistem Chrome'unu bu profille HEADED açar → analist bir kez giriş yapar,
pencereyi kapatır (profil kilidi). Sonraki headless analizler aynı çerezleri kullanır.
`GET /api/live-app/status` → `{npx, urls, profil, hazir}`; UI'da Bağlam Filtresi altında durum
noktası + "Tarayıcıda Giriş Yap" butonu. `live_app_profil_var_mi()` profil hazırlığını gösterir,
**giriş yapıldığını KANITLAMAZ** — analiz login sayfasına düşerse prompt kuralı gereği varsayım
üretmeden bildirir.

**Kapalıyken:** live_app URL'i yoksa hiçbir ek argüman geçmez → normal analiz davranışı aynen korunur.

**Sistematik tarama planı (`canli_uygulama_baglami_hazirla`):** MCP görevi serbest "gez ve gözle"
değil, zorunlu sıralı bir plandır: (1) açılış snapshot + network, (2) TÜM tablar/segment kontrolleri
(`?tab=` yalnızca başlangıç), (3) her aksiyon butonunun modal/formu — alan tipi/zorunluluk/default/
cascade, (4) filtre/arama/sayfalama + query parametreleri, (5) CRUD (aşağıdaki kurallara göre GERÇEK),
(6) her aksiyondan sonra `browser_network_requests`, kritik isteklerin detayı `browser_network_request`,
(7) edge-case'ler (boş liste/loading/hata/yetki). Gözlemler "adım → beklenen/gözlenen sonuç" (test
senaryosu türetilebilir) formatında; çıktı sonuna **"Canlı Gözlem Kapsamı" raporu zorunlu** (gezilen +
YAPILAN yazma işlemleri + gezilemeyen ve nedeni). NOT: derin tarama uzun sürer — CLI timeout 20 dk;
alt URL sayısını sınırlı tut, gerekirse HIZLI_MOD ile denetçi aşamasından süre kazan.

**CRUD kuralları (test ortamı — yazma GERÇEKTEN uygulanır):** Test ortamı linkleri verildiği için
create/update uçtan uca yapılır ve yazma servislerinin gerçek istek/yanıt çiftleri (method, path,
payload, status, gövde özeti) yakalanır — bug-fix/CR analizlerinin dayanağı budur. Koruma sınırları:
oluşturulan kayıtlara `AI-TEST` öneki; SİLME yalnızca bu oturumda kendi oluşturduğu kayıtlarda;
GERİ ALINAMAZ süreç aksiyonları (ödeme, rollback, publish, onaya gönderme) UYGULANMAZ —
`[K: 🔍 Türetilmiş]` + açık soru. Yapılan tüm yazmalar Gözlem Kapsamı raporunda listelenir.

**Odaklı gözlem (`gozlem_kapsami`):** `live_app.gozlem_kapsami` / `live_app_gorev.gozlem_kapsami`
(her ekran KENDİ alanını kullanır) doluysa tam tarama planı YERİNE analistin tarif ettiği bölüm/akış
uçtan uca ve derinlemesine incelenir ("ekranın tamamını taramak zorunda değilsin" + validasyon/hata
edge-case'leri dahil) — daha hızlı, daha az token, bug-fix/CR hedefine isabetli. UI: Bağlam
Filtresi'nde "MCP Gözlem Kapsamı" textarea'sı (`ctx-live-scope`), Jira Görevleri widget'ında
`jg-live-scope`. CRUD kuralları ve kayıt formatı iki modda da ortaktır. Belirli bir akışı hedeflemek
için doğru araç BUDUR — Özel Prompt değil (o sistem promptunu değiştirir, gezinme görevine dokunmaz).

**Verimlilik kuralları (`verimlilik_kurallari`, iki modda da ortak):** tur/token maliyetini düşürmek
için MCP görev metnine eklenir — önce planla + tek geçişte uygula (aynı ekranı tekrar gözlemleme);
snapshot ekonomisi (tam `browser_snapshot` yalnızca DOM anlamlı değişince, öğe bulmak için
`browser_find`); network ekonomisi (liste yalnızca yeni istek tetiklenince, tam detay sadece kritik
istek için); bitiş koşulu (çekirdek gözlem — giriş → aksiyon → istek+yanıt → sonuç → hata — tamamsa
DUR ve raporu yaz). Doğruluk kuralları (CRUD, kayıt formatı, spekülasyon yasağı) aynen geçerlidir.

**Özel Prompt ile ilişki:** MCP görevi SİSTEM promptunda değil, kullanıcı mesajı bloğunda
(`stable_bloklar`) taşınır — ekrandaki Özel Prompt varsayılan sistem promptunun yerine geçse bile
canlı uygulama görevi + araç izinleri AYNEN gider; gözlem etiket kuralları görev bloğunun içinde
olduğundan özel promptta tekrar yazılması gerekmez.

**Jira Görevleri'nden erişim — BAĞIMSIZ ikinci hedef (`live_app_gorev`):** Süreç/Teknik Analiz'in
`live_app` alanından TAMAMEN ayrı, `context_filter.json`'da ikinci bir alan: `live_app_gorev`
(yalnızca `target_url`; alt URL/örnek-ekran kavramı yok — task bazlı tek ekran içindir). İki akış
birbirinin URL'ini asla kullanmaz:
- `gorev_live_app_urls()` / `live_app_urls()` (`skills/base.py`) ayrı okuma fonksiyonları.
- `canli_uygulama_baglami_hazirla(gorev: bool)` hangi hedeften talimat metni üretileceğini seçer;
  `_api_cagri(..., canli_uygulama_kapsami="gorev")` yalnızca `gorev_analiz_et()`
  (`skills/jira_gorevleri.py`) bu talimatı gerçekten ürettiğinde verilir. `_gorev_acik_sorular_uret()`
  (Aşama 2, zaten üretilmiş metni özetler) hiçbir kapsam GEÇMEZ — browsing talimatı içermediği için
  canlı uygulama hiç açılmaz (bkz. yukarıdaki "Geçmiş bug" notu).
- UI: Jira Görevleri sayfasında ("Üst Görev" paneli) Bağlam Filtresi'yle aynı `.la-durum` bileşenini
  (`jg-live-target`/`jg-la-*` id'leriyle) kullanan ayrı bir widget. `jgLiveAppKaydet()` mevcut filtreyi
  GET edip `live_app`'e DOKUNMADAN yalnızca `live_app_gorev.target_url`'i güncelleyip geri POST'lar
  (`/api/context-filter` POST'u tam nesne bekler — kısmi gönderim diğer alanları silerdi).
  `jgLiveAppGiris()` alan boşsa backend'in `live_app_urls()` fallback'ine (Süreç'in URL'i) düşmesin
  diye istemci tarafında erken çıkar.
- `GET /api/live-app/status?scope=gorev` → `gorev_live_app_urls()`; parametresiz → Süreç'in `live_app`'i.
  Profil/npx durumu ortak (aynı `.live-app-profile` Chrome oturumu paylaşılır), yalnızca `urls`/`hedef` ayrışır.

**Profil kilidi self-heal:** Chrome aynı `--user-data-dir`'i tek seferde yalnızca bir süreçte açabilir.
Analist HEADED giriş penceresini kapatmayı unutursa hem yeni "Tarayıcıda Giriş Yap" tıklaması hem de
analiz sırasındaki headless Playwright başlatması aynı kilide takılır (`claude -p` non-interactive
çalıştığından, kilidi tutan yetim süreç bir insan/agent onayı olmadan sonlandırılamaz → analiz askıda
kalır). `live_app_kilidi_temizle()` (`skills/base.py`) bunu otomatik çözer: `SingletonLock`
symlink'inden PID'i okur, süreç yaşıyorsa SIGTERM gönderip **en fazla ~5 sn** (0.25 sn aralıklarla
poll) kendiliğinden kapanmasını bekler, hâlâ yaşıyorsa SIGKILL'e düşer; `Singleton*` dosyalarını
siler. Hem `POST /api/live-app/login`'de (her tıklama gerçekten temiz pencere açsın) hem
`_live_app_cli_argumanlari()`'nde (her live-app'li analiz temiz başlasın) çağrılır — ayrı bir onay
akışı gerektirmez, uygulama kendi kaynağını kendi temizler.

**Neden 5 sn poll (sabit 1 sn değil):** Chrome SIGTERM'i normal kapanış sayar ve bu sırada
çerezleri/oturum verisini diske yazar (flush) — ama bu anlık değil. İlk sürümde sabit 1 sn bekleyip
koşulsuz SIGKILL atılıyordu; analist TAM O SIRADA giriş yapıp pencereyi henüz kapatmışsa (veya
analiz otomatik başlayıp self-heal'i tetiklemişse) taze çerezler flush olmadan kesilme riski vardı —
sonuç: profil "hazır" görünür ama analiz yine login duvarına düşer (giriş yapılmış gibi görünüp
aslında geçerli oturum kaydedilmemiş olur). Artık süreç kendiliğinden kapanana kadar bekleniyor,
yalnızca gerçekten yanıt vermiyorsa zorla kapatılıyor.

**Otomatik giriş (opsiyonel):** Bağlam Filtresi panelinde (Süreç ekranı) `live_app_auth`
(kullanıcı adı + şifre) girilirse, MCP tarayıcısı bir login/giriş formuna düşünce bu bilgilerle
otomatik giriş yapıp devam eder — önceden yalnızca "login duvarına takıldı" diye açık soru
üretilebiliyordu. `live_app_auth` **iki akış da (Süreç/Teknik Analiz + Jira Görevleri) paylaşır**
(aynı test hesabı); `canli_uygulama_baglami_hazirla()` her iki `gorev` değeri için de bu bilgiyi
ekler. Şifre `reference/context_filter.json`'da düz metin tutulur — dosya zaten gitignore'da
(hard kural #2) ve `context_filter_kaydet()` yazımdan sonra dosya iznini 600'e sıkılaştırır.
Prompt talimatı modele şifreyi ASLA çıktıya yazmamasını söyler (mevcut token/cookie maskeleme
kuralına ek).

**`/api/context-filter` POST artık PATCH semantiği kullanır (düzeltildi):** Eskiden istek
gövdesinde eksik olan HER üst-düzey alan boş değere sıfırlanıyordu — bu yüzden Süreç ekranından
kaydedince (`buildContextFilter()` `live_app_gorev` alanını hiç bilmez) Jira Görevleri'nin hedefi
sessizce siliniyordu, ve tersi de geçerliydi. `context_filter_kaydet()` (`app.py`) artık önce
mevcut dosyayı okur; istek gövdesinde bulunmayan alan (`"anahtar" in data` değilse) mevcut kayıtlı
değerini korur. Yalnızca gövdede AÇIKÇA gönderilen alan güncellenir/silinir — `ctxFilterTemizle()`
gibi "temizle" akışları hâlâ çalışır çünkü ilgili alanı açıkça boş gönderirler.

### Model araç çağırmama (num_turns=1) — teşhis + otomatik tekrar (2026-10-16)
**Belirti:** `⚠ CANLI GÖZLEM YAPILMAMIŞ OLABİLİR (num_turns=1, reddedilen=[])` — rozet "YAPILAMADI".
**Teşhis yolu:** Claude CLI'ın MCP logu `~/Library/Caches/claude-cli-nodejs/<cwd-slug>/mcp-logs-playwright/*.jsonl`
(cwd-slug = repo yolunun `-` ile yazılmış hâli). Başarısız koşularda sunucu `Successfully connected … hasTools:true`
ile bağlanmış, 64–96 sn sonra `SIGINT` ile kapanmış — araç çağrısı yok. Yani MCP/Chrome/npx sağlam; **model**
büyük promptta (referans blokları + few-shot + domain kuralları) ortada kalan tarayıcı talimatını atlayıp araçsız
rapor yazdı. Küçük promptlu aynı çağrı (`canli_uygulama_baglami_hazirla` + kısa sistem) 10 tur gezdi.
**Çözüm (`base._api_cagri_cli`):**
1. Canlı kapsamlı (`_live_args` dolu) her çağrıda birleşik promptun EN SONUNA `_LIVE_APP_ZORUNLU_ILK_ADIM`
   (kısa, emredici: "yanıt yazmadan önce `browser_navigate`; araçsız rapor YASAK") — recency etkisi.
2. Yanıt `num_turns<=1` ise (izinli araç reddi DEĞİL) `_api_cagri_cli(..., _tekrar=True)` → promptun sonuna
   `_LIVE_APP_TEKRAR_UYARISI` ("önceki denemede araç çağırmadın, yanıt reddedildi") ile BİR KEZ daha. İkinci
   deneme de araçsızsa normal uyarı + rozet. `.env` `LIVE_APP_TEKRAR=false` kapatır (maliyet).
3. `.gozlem-durum.json` → `neden` ("izinli tarayıcı aracı reddedildi" / "model hiç tarayıcı aracı çağırmadı
   (MCP bağlıydı; tekrar denendi)") → Çıktı Dosyaları rozeti tooltip'inde.
4. `live_app_kilidi_temizle`: SingletonLock symlink'ine ek `pgrep -f --user-data-dir=<profil>` ile profili
   tutan başlı/yetim Chrome süreçleri de kapatılır (aksi hâlde Playwright "Browser is already in use" → model
   aracı dener, hata alır, `num_turns≈4`).
5. `bff_kesif.kesfet`: etiketsiz ama `## Ekran/Açılış/CREATE` başlıklı yanıt kabul edilir; blok hiç yoksa ham
   yanıt `reference/live-app/bff/<anahtar>.ham.txt`'ye yazılır (12 dk gözlem sonrası sessiz kayıp olmasın).
Test: `tests/test_canli_tekrar.py` (CLI mock, 0 token).


### Jira'ya giden task gövdesi — tek temizleme kapısı (`base.jira_icin_temizle`, 2026-10-16)
**Sorun (owner):** Task analizi Jira'ya yazılınca geliştiricinin işine yaramayan analist-içi bilgiler gövdede kalıyor,
elle siliniyordu: `<!-- RAG: … -->` yorumu, backtick'li `[K: …]` etiketlerinden kalan boş `` `` ``, "Analist notu bunu
doğrular: '…'" / "Confluence: '…'" alıntı cümleleri, "Confluence'a göre" önekleri, seçilen yaklaşımı alternatiflere karşı
savunan cümleler, "(… FE'nin kontrolü dışıdır — bkz. …)" hedge parantezleri ve atlanan şablon bölümleri yüzünden
1-2-3-7-11 diye kopuk numaralar.
**Çözüm — iki katman:**
1. **Prompt** (`gorev_teknik_analiz` → "# JİRA TASK DİLİ"): kaynak alıntısı yazma (kaynak yalnız `[K:]` etiketi),
   gerekçe/karşılaştırma yazma, hedge parantezi yazma, başka task'ı kanıt diye anlatma, motivasyon cümlesi yazma.
2. **Deterministik kapı** `jira_icin_temizle(md)` — sıra: `yonetici_ozetini_cikar` → `canli_gozlem_kapsamini_cikar` →
   HTML yorumu → `kanit_etiketlerini_temizle` (regex artık `` `[K: …]` `` backtick'lerini de yutar) → tamamı alıntı
   olan madde satırı (`_KAYNAK_MADDE`) → alıntı cümlesi (`_KAYNAK_ALINTI`) → "X'e göre" öneki (`_KAYNAK_ONEK`) →
   meta parantez bütünüyle (`_META_PARANTEZ`) → meta cümle (`_META_GEREKCE`) → boş kalan madde/parantez artıkları →
   `_bolumleri_yeniden_numarala` (`## N.` ardışık; `### N.M` + `bkz./(N.M)/bölüm N.M` atıfları aynı harita; numarasız
   başlık ve zaten ardışık metin dokunulmaz). Desenler satır sonunu YUTMAZ (`[ \t]*`), başlıklar birleşmez.
   Çağıranlar: `gorev_jiraya_yaz` (gövde) · `gorev_fe_be_task_olustur` (FE yeni task) · `_analiz_adf` (Yeni Task Aç) ·
   `jira_kopru._govdeye_yaz`. Analiz dosyası, ekran ve eğitim havuzu kopyası DEĞİŞMEZ (etiketler orada kalır).
Test: `tests/test_jira_temizle.py` (sentetik örnek; gerçek analiz içeriği tracked dosyaya konmaz).


### Açık Soru Öz-Çözümleme (`skills/soru_cozumleme.py`, 2026-10-16)
**Sorun (owner):** Task Analizi'nin açık soruları (ör. "my-permissions ucunu başka kim tüketiyor?", "dashboard izin kontrolünden
geçiyor mu?") analistin önüne araştırılmadan geliyordu; oysa cevapları Swagger/Confluence/Jira referanslarında, kodda ya da
canlı uygulamada vardı. Soru üretimi analizden sonra ucuz bir adımda çalışır ve referanslar soruya göre değil task metnine göre
seçilmiştir — soruya özel kanıt toplanmıyordu.
**Akış (`cozumle(acik_md, gorev, canli)` — `gorev_analiz_et` Aşama 2b):**
1. `_bloklar` `### Q-T-nnn` bloklarını ayırır (Soru/Beklenen/Bağlı; `Agent durumu` varsa "zaten çözümlü" → atlanır).
2. `kanit_topla` (0 token): `_corpus()` referans dosyalarını tipe göre (`services/`→swagger, `live-app/`, `confluence/`, `jira/`)
   `_ref_dokuman_metinleri` ile okur; soru başına `en_alakali_corpus` (~7k) + `_adaylar` (endpoint yolu `/a|b/...` ayrımı,
   son segment, camelCase/snake, backtick) ile `degisiklik_etkisi.tuketici_tara` + Kod Kaynağı bağlıysa `kod_kaynagi.ara`.
3. `_siniflandir` — TEK AI çağrısı (`_SISTEM`, `<soru_cozum>` JSON): `cevaplandi` (net, emir kipi cevap + `[K:]`) · `kismi` ·
   `karar_gerekli` (ürün kararı; kararı kolaylaştıran özet) + `gozlem_gerekli/gozlem_adimi`. UYDURMA yasak.
4. `_gozlemle` — yalnız `gozlem_gerekli` ve henüz cevaplanmamış sorular için TEK odaklı canlı tur (`live_app_gorev` hedefi,
   yoksa `live_app` ANA adresi + `base_url_override`; `canli_uygulama_kapsami` gorev/surec, önbellek kapalı; `<gozlem_cozum>`).
   `cevaplandi` → durum yükselir, cevaba "Canlı gözlem: …" + kanıt eklenir; `kismi` → karar_gerekli'yi kısmiye çeker;
   hata/MCP yok → referans sonucu korunur.
5. `_bloga_yaz` → bloğa `- Agent durumu: cevaplandı|kısmen|karar gerekli` · `- Agent cevabı` · `- Agent kanıtı` ·
   `- Agent gözlemi` (eski Agent satırları silinip yenilenir → cevap turunda çoğalmaz). Analiz YENİDEN YAZILMAZ.
**UI (`index.html`):** `_jgSorulariAyristir` → `agentDurum/agentCevap/agentKanit/agentGozlem`; `_jgSorulariRender`: özet bandı
("🤖 Agent N sorunun M'ini … cevapladı — kutular önceden dolu"), kart rozeti (`.jg-sk-agent ok|kismi|karar`, tooltip kanıt),
sol kenar rengi, cevap kutusu **agent cevabıyla ön-dolu** (karar gerekli → boş + "Agent notu" satırı); analistin kendi cevabı
(FE/BE geçişi `entry.cevaplar`) agent cevabına ÜSTÜN. "Cevapları İşle" değişmedi (ön-dolu kutular da gönderilir → analiz
cevaplarla yeniden yazılır, sorular yakınsar). Köprü yorumu aynı md → Agent satırları Jira'da da görünür.
6. **Otomatik işleme (2026-10-19 — "cevabı bulduysa neden analize işlemedi?"):** `cozulenleri_ayir` cevaplanan
   blokları ayırır → `uygulama_talimati` ("her cevabı Bağlı bölüme minimal işle, belirsizlik ifadelerini kaldır, başka
   bölüme dokunma") → `gorev_analiz_duzelt` (mevcut hedefli düzeltme: referans/gözlem yok, tek çağrı; `_rag_yorum_ayir`
   RAG yorumunu dışarıda tutar; çıktı gövdenin yarısından kısaysa reddedilir) → analiz güncellenir; çözülenler açık
   sorulardan düşer, `cozulen_bolumu` (`## 🤖 Agent'ın çözüp analize işlediği sorular`) şeffaflık için eklenir. UI
   `_jgCozulenBolumu` bunu katlanmış yeşil kutu olarak gösterir ("onay gerekmez"); Q- başlığı olmadığından soru sayılmaz,
   ZORUNLU kapısına takılmaz. Yalnız `kismi` (ön-dolu) ve `karar_gerekli` (boş + not) sorular analiste kalır. Hata →
   eski davranış (ön-dolu). `SORU_COZUMLEME_UYGULA=onay` eski davranışı seçer. Maliyet kıyası: eski yol "Cevapları İşle"
   = tam yeniden üretim (referans + canlı gözlem, dakikalar); yeni yol = tek düzeltme çağrısı (analiz uzunluğu kadar token).
**Kapatma/maliyet:** `SORU_COZUMLEME=false` ya da `HIZLI_MOD=true`; task başına 1 kısa AI çağrısı + gerekirse 1 canlı tur
+ çözülen varsa 1 hedefli düzeltme. Test: `tests/test_soru_cozumleme.py`.

### Canlı Uygulama Giriş Kapısı (`skills/canli_giris.py`, 2026-10-16)
**Owner isteri (Task Analizi):** canlı hedef tanımlıyken giriş yapılamıyorsa analiz başlamasın (yanlış şifre dakikalarca boşa
gözlem + token yakıyordu); hedef yoksa "canlı gözlem yapılmadan analiz yapılacak" bilgisiyle başlasın.
- **Modül:** `hedef_url(kapsam)` (gorev → `live_app_gorev`, surec → `live_app`) · `durum(kapsam)` → `{url, var, giris{ok,neden,
  ekran,ts,taze}, gerekli, mesaj}` (0 token) · `test_et(kapsam)` → 1 CLI/Playwright çağrısı (`giris_calistir`: ana adres, kayıtlı
  hesap, `<giris_sonuc>` JSON; oturum zaten açıksa ok) → `output/.giris-durum-<kapsam>.json` **imzalı** (sha1 URL+kullanıcı+şifre)
  · taze = imza aynı ve `GIRIS_TEST_GECERLILIK` (3600 sn) içinde · `gerekli` = URL var ve taze başarılı sonuç yok.
- **Uçlar (app.py):** `GET /api/live-app/giris-durum?kapsam=` · `POST /api/live-app/giris-test {kapsam}` → arka plan iş
  (`_giris_isler`, aynı kapsamda süren iş varsa o döner) · `GET /api/live-app/giris-test/durum?job=`. `_arka_plan_isleri_calisiyor`
  listesine eklendi (restart/kapanma kesmez).
- **UI (`index.html`):** `_jgIsBaslat` → `_jgCanliKapi(adimlar)`: canlı modlar (`_JG_CANLI_MODLAR`: analiz/fe-be-ayir/bff-kesif/
  kabul-kontrol) için kapsam = adımda `canli_hedef` varsa 'surec' (ekran bazlı iş, Süreç mirası) yoksa 'gorev'. Hedef yok → toast
  bilgi + başla. Gerekli → "Canlı uygulamaya giriş doğrulanıyor" HUD + iş polling (3 sn, 5 dk tavan) → ok: toast + başla ·
  başarısız: ⛔ neden + "Girişi tekrar dene ve başlat" (`jgCanliTekrar`, `_jgBekleyenBaslat`) + "Ayarlara git"; analiz başlamaz.
  Canlı-app durum satırında "Girişi Doğrula" düğmesi (`jgGirisDogrula`) + son durum (`_jgGirisDurumGoster`, boot/yenilemede).
- **Ortak çekirdek:** İnteraktif Analiz'in "Girişi Test Et"i (`sohbet_analiz.giris_testi`) artık `test_et('surec')` çağırır →
  sonuç imzalı dosyaya da yazılır; iki ekran aynı doğrulamayı paylaşır.
- Test: `tests/test_canli_giris.py` + `smoke_test` (4 uç kontrolü).

### Profil Havuzu — paralel canlı gözlem (`base._slot_al/_slot_birak`, 2026-10-16)
**Sorun:** tek Chrome profili (`.live-app-profile`) → ikinci eşzamanlı gözlem "Browser is already in use" ile düşüyordu
(Task Analizi + İnteraktif Analiz çakışması; farklı analistlerin Kabul Kontrolü + Süreç analizi de aynı). Eski kod analiz
öncesi ana profili kapatıyordu (`live_app_kilidi_temizle`) — bu da süren diğer gözlemi öldürüyordu.
**Çözüm:**
- `LIVE_APP_PROFILE_HAVUZ = .live-app-profiles/`; slot `slot-N` (N ≤ `LIVE_APP_PARALEL`, vars. 6, en çok 16).
- `_slot_al(bekle_sn)`: `slot-N.lock` dosyasını `O_CREAT|O_EXCL` ile oluşturur, içine pid yazar (süreçler arası güvenli:
  run.py alt-süreci ↔ Flask thread'leri). Kilit varsa: sahibi canlı başka süreç → atla · sahibi bu süreçte başka thread
  (`_SLOT_SAHIPLI`) → atla · ölü pid → bayat, devral. Slot alınınca `_profil_sureclerini_kapat(slot)` (yetim headless;
  pgrep deseni `--user-data-dir=<dir>(\s|$)` TAM eşleşme) + `_slot_oturum_kopyala(slot)`. Havuz doluysa 2 sn'de bir
  yeniden dener, `LIVE_APP_SLOT_BEKLE` (300 sn) sonunda None → `_live_app_cli_argumanlari` net RuntimeError.
- `_slot_oturum_kopyala`: ana profilin `Default/Cookies(-journal)`, `Network/Cookies`, `Login Data`, `Preferences` +
  `Local Storage`, `Session Storage`, `IndexedDB` dizinleri slota kopyalanır; `.oturum-damga` (ana mtime) ile yalnız
  ana profil yenilenince (analist "Tarayıcıda Giriş Yap" ile giriş yapınca) tekrar kopyalanır. macOS'ta Chrome çerez
  şifreleme anahtarı Keychain'de kurulum-başına → profiller arası kopya çözülür.
- `live_app_mcp_config_yaz(profil_dir, config_yol)` → `.live-app-profiles/mcp.slot-N.json`; `_live_app_cli_argumanlari`
  ana profili ARTIK KAPATMAZ (yalnız `/api/live-app/login` yolu `live_app_kilidi_temizle` çağırır).
- `_api_cagri_cli`: `_cli_calistir` try/finally → `_slot_birak()` her durumda (hata/timeout/Durdur); araç-çağırmama
  tekrarı (`_tekrar=True`) yeni slot alır. `slot_durumu()` → `/api/live-app/status.slotlar {toplam, dolu[], bos}`.
- Kanıt: iki eşzamanlı headless gözlem (example.com) ayrı slotlarda çakışmadan tamamlandı.
Test: `tests/test_live_app_slot.py`.

**Oturum kalıcılığı (2026-10-19 — "her seferinde tarayıcıdan giriş yapmak zorunda kalmasın"):** oturum akışı artık
ÇİFT yönlü. Agent bir slotta kayıtlı hesapla (prompt "OTOMATİK GİRİŞ") giriş yapınca `_slot_birak` →
`_slot_oturum_geri_yaz(slot)`: slotun oturum dosyaları ana profilden yeniyse ana profile kopyalanır + `.oturum-son-giris`
işareti; ana profil başlı Chrome'da açıksa atlanır (yarım dosya riski); slot damgası güncellenir (kendini yeniden
kopyalamaz). Sonraki her slot alımı `_slot_oturum_kopyala` ile bu oturumu devralır → bir kez agent girişi = Task ·
İnteraktif · Kabul Kontrolü · Süreç analizlerinin hepsi girişsiz başlar. Oturum düşerse agent yeniden girer ve
tazeler; prompt kuralı: "oturum zaten açıksa giriş adımını ATLA, asla logout yapma". `oturum_durumu()` →
`/api/live-app/status.oturum`; iki ekranın canlı-app durum satırı kayıtlı oturumu (kaynak agent/tarayıcı + yaş) gösterir.
Düğme "Elle giriş (ayrı Chrome)" adını aldı, soluk/ikincil; tıklamadan önce onay: kayıtlı oturum varsa bildirilir ve
"agent'ın KENDİ profiliyle AYRI bir Chrome penceresi açılır (kişisel Chrome değil)" açıklanır — yalnız 2FA/captcha için.

### Katman seçimli Jira yazımı — FE+BE setinden yalnız FE / yalnız BE (2026-10-16)
**Sorun (owner):** FE+BE ayrı analizde "Onayla" her zaman iki işi birden yapıyordu (BE'yi kaynak task'a yaz + FE için yeni
task + Blocks); "Yeni Task Aç" da hep iki task açıyordu. Oysa iş bazen tek katmandadır (FE analizi "BE'de düzenleme gerekmez"
diyordu) ve içerik sonradan değişebilir.
**Çözüm:**
- **Onay satırı:** FE+BE setinde `#jg-katman-sec` (BE → kaynak'a yaz · FE → yeni task aç). `_jgKatmanSecimHazirla`: varsayılan
  bakılan sekmenin katmanı; agent `is_var === false` dediyse o katman işaretsiz + not; `entry.jiraYazildi` olan katman işaretsiz.
  `_jgKatmanEtiketGuncelle` düğme metnini seçime göre yazar; sıfır seçimde düğme kapalı.
- **Backend:** `gorev_fe_be_task_olustur(key, be_md, fe_md, summary, katmanlar)` — `be`: `gorev_jiraya_yaz` ('BE - ' başlık) ·
  `fe`: `_issue_olustur` ('FE - ') · ikisi: `_blocks_bagla` (BE→FE) · yalnız FE: `jira_issue_link(fe_key, key, Relates)`
  (izlenebilirlik; BE task'ı yok → Blocks yok) · yalnız BE: task açılmaz. Eksik katman içeriği → ValueError. Uç `fe-be-olustur`
  `katmanlar` alır, doğrular, yalnız yazılan katmanları `_ornek_yakala_md`'ye verir. `gorev_yeni_task_olustur(mode='be'|'fe',
  markdown)` → katman önekli TEK yeni task + üst öğe/kaynak Relates; uç `mode` doğrular (tek|fe-be|be|fe).
- **Yeni Task Aç paneli:** FE+BE setinde radyo (BE+FE / Yalnız BE / Yalnız FE), varsayılan bakılan sekme (agent "iş yok" dediyse
  diğerine düşer); not satırı seçimi açıklar; gövde `mode:'fe-be'|'be'|'fe'`.
- **Agent önerisi:** `gorev_analiz_et` KATMAN ODAĞI bloğu analizin başına `**Bu katmanda iş:** VAR|YOK — gerekçe` ister (YOK ise
  kalan analiz 2-3 cümle); `katman_is_var_mi` → `gorev_fe_be_analiz` sonucu `is_var` (UI `isVar`). Satır Jira'ya da gider
  (geliştirici için bilgi); `jira_icin_temizle` dokunmaz.
- Kısmi yazım kalıcı: `jiraYazildi` sette (`_jgSetKaydet`) → sayfa yenilense de "FE KEY açıldı ✓" görünür, diğer katman
  sonra yazılabilir. Test: `tests/test_katman_secimi.py`.

### Kota Faz 2+3 — hedefli cevap uygulama + model katmanları (2026-10-19, plan §7)
**Faz 2 — "Cevapları İşle" hedefli (`jira_gorevleri.gorev_cevap_uygula`):** eskiden analistin cevapları `gorev_analiz_et(cevaplar=…)`
ile TAM zinciri (gözlem fazı + analiz + açık sorular + öz-çözümleme) yeniden koşturuyordu. Şimdi: `(1)` `_rag_yorum_ayir` ile RAG
yorumu ayrılır, `(2)` `gorev_analiz_duzelt(gorev, govde, _CEVAP_TALIMAT + cevaplar)` cevapları ilgili bölümlere işler (belirsiz/
varsayım işaretlerini kaldır, `[K: Analist cevabı]` ile kesin bilgi, Açık Sorular'dan düş, ilgisiz bölüme dokunma — yardımcı
katman, aşama `gorev:cevap`), `(3)` `_gorev_acik_sorular_uret(yeni, gorev, cevaplar, onceki_sorular)` kalan soruları yakınsar (hafif
katman; hata yutulur → cevaplar yine işlenir), RAG yorumu geri konur → `{markdown, acik_sorular, hedefli:True}`. Mevcut analiz /
cevap boşsa `ValueError` (çağıran tam üretime düşer). `cevap_hedefli_acik()` (`CEVAP_HEDEFLI`, vars. açık). **app.py `_adim_isle`
mode `cevap`:** adım `markdown` (editör içeriği) doluysa hedefli; boşsa/kapalıysa `mode="analiz"` tam üretim (eski yol, BFF bloğu
olmadan). Eğitim toplama/telemetri diğer modlarla aynı. **UI:** `jgCevaplariIsle` → `mode:'cevap'` + editör markdown'ı; düğme
"Cevapları İşle → Analize Uygula"; `jgCevaplariBastanUret` (`_jgCevapBastan`) → `mode:'analiz'` bilinçli tam üretim. FE+BE
setinde `::FE` sentetik anahtar `_jgGorevCoz` ile gerçek göreve çözülür (duzelt ile aynı). **Köprü `cevap`:** `son_analiz[key].md`
ya da gövdeden `_analiz_bolumu_ayikla` varsa `gorev_cevap_uygula(_orijinal_gorev(gorev), …)`; hata/yoksa `_bridge_uret` (tam).
**Faz 3 — model katmanları (yalnız CLI modu):** `base.KATMANLAR=("ana","yardimci","hafif")`, `cli_model_katman(k)`: ana →
`aktif_cli_model()` (CLAUDE_CLI_MODEL) · yardimci → `CLI_MODEL_YARDIMCI` (vars. `sonnet`) · hafif → `CLI_MODEL_HAFIF` (vars.
`haiku`); boş env → varsayılan; canlı okunur (restart gerekmez). `_api_cagri(..., katman="")`: açık katman > model sabiti
(`MODEL_HAFIF`→hafif, `MODEL_YARDIMCI="claude-sonnet-5-5"`→yardimci — MODEL_ANALIZ ile AYNI id olamaz, yoksa ayırt edilemez) >
ana → `_api_cagri_cli(katman=)` `--model cli_model_katman(katman)` (tekrar denemeleri katmanı taşır; `--resume` tamamlaması aynı
model). `_api_cache_key(..., katman)` → katman modeli anahtarda (yardımcı sonuç ana diye dönmez). `_cagri_kaydet(katman=…)` →
`cagri.jsonl` + Kullanım Raporu model sütunu gerçek modeli gösterir. **Atama:** yardimci = `gozlem.rapor_al`, `canli_giris.
giris_calistir`, `bff_kesif.kesfet`, `kabul_kontrolu` (liste + doğrulama), `soru_cozumleme` (`_siniflandir` + `_gozlemle`),
`gorev_analiz_duzelt` (→ cevap uygulama ve öz-çözümleme işlemesi de), `sohbet_analiz.ekran_listesi_cikar`; hafif = `MODEL_HAFIF`
çağrıları (formatla, test senaryoları, açık soru toplama); ana = süreç/teknik/görev analizi, denetçi, FE/BE bölme, akış kapatma,
sohbet turu, kapsam/BRD/delta. API modunda `model` parametresi aynen gider (katman etkisiz). **CLI sürümü:** alias'lar
(`sonnet`/`haiku`/`opus`) ve `claude-opus-5-5` CLI ≥ 2.1.303 ister (2.1.267 `unrecognized_model`); eski CLI'da `claude update`.
Owner makinesinde ana katman `claude-opus-5-5` (`.env`; karşılaştırma plan §7). Test: `tests/test_kota_faz23.py`.

### Kota Faz 0+1 — ölçüm ve gözlem fazı ayrımı (2026-10-19, `docs/KOTA-OPTIMIZASYON-PLANI.md`)
**Teşhis:** canlı gözlem analiz çağrısının içinde agentik döngüyle yapılıyordu; her araç turu (17-34) ~40k token'lık tam
analiz bağlamını yeniden okuyordu (tek süreç analizi çağrısı: 5.9M cache okuma). Task Analizi'nde token ölçümü de yoktu.
**Faz 0 — ölçüm:** `base.asama_ayarla(ad)` thread-local aşama etiketi; `_api_cagri_cli` her başarılı çağrı için
`logs/usage/cagri.jsonl`'a satır yazar (`_cagri_kaydet`: ts, asama, model, canli, kapsam, tur, girdi, cikti, cache_yaz,
cache_oku, sure_sn, tekrar, max_tur_takildi, prompt_kc — analiz içeriği yazılmaz). `cagri_ozeti(gun)` aşama+model+canlı
bazında toplar → `GET /api/usage/cagri-ozet?gun=` (usage-gate) → Kullanım Raporu "Aşama bazlı tüketim" tablosu (cache oku
= döngüde yeniden okunan bağlam; ana kalem).
**Faz 1 — gözlem fazı (`skills/gozlem.py`):**
- `rapor_al(canli_blok, kapsam, gorev_ozet, yeniden, max_turns)`: prompt = motorun zaten ürettiği canlı görev bloğu
  (URL + hedef + giriş + kurallar) + ≤3k görev/doküman özeti + `_RAPOR_FORMAT`; referans/few-shot/domain YOK →
  `_api_cagri(onbellek=False, canli_uygulama_kapsami=kapsam, max_turns)` → `<gozlem_raporu>` (etiketsiz gövde de kabul)
  → `reference/live-app/gozlem/<anahtar>.md/.json` (anahtar = sha1(kapsam|blok); ≤12k char). `ok` = `.gozlem-durum.json`
  yapildi + kanıt etiketi var. `yeniden=False` ve taze (`GOZLEM_RAPOR_GECERLILIK` 6 sa) → önbellekten, AI çağrılmaz.
- `rapor_blogu(rapor)`: analize giren blok — "gözlem tamamlandı, bu çağrıda tarayıcı YOK; etiketleri aynen taşı; raporda
  olmayanı uydurma; referansla çelişirse gözlem kazanır". `gozlem_yok_blogu(neden)`: gözlem yapılamadıysa.
- **Motorlar:** `gorev_analiz_et` (canlı blok varken `rapor_al` → `rapor_blogu` stable bloğa; analiz çağrısı
  `canli_uygulama_kapsami` olmadan, önbellek normal — rapor metni anahtarda), `gorev_fe_be_analiz` (TEK gözlem, `gozlem_rapor`
  iki katmana), `surec_analizi_yap` / `teknik_analiz_yap` (aynı; `_teknik_uret_tam` tarayıcısız). Cevap turu / düzelt
  (`cevaplar|onceki_sorular`) → `yeniden=False`; yeni analiz → `yeniden=True` (taze gözlem).
- **Tur tavanı:** `_api_cagri(max_turns)` → `_api_cagri_cli` canlı çağrıda `--max-turns` (`LIVE_APP_MAX_TUR`, 40);
  `error_max_turns` → `--resume <session_id> --max-turns 3` + "araç kullanma, raporu şimdi yaz" (çıktı kaybolmaz;
  `max_tur_takildi` kaydedilir). Canlı prompt "TUR DİYETİ" kuralları.
- **Yalın CLI (ölçüldü):** `claude -p` sabit bağlamı ~98k token (yerleşik araç şemaları ~35k; kullanıcı MCP'leri küçük pay).
  `_yalin_cli_argumanlari`: gözlemsiz çağrıda `--tools "" --disable-slash-commands` + boş strict `.mcp.bos.json` → sabit
  bağlam 62k. CANLI çağrıda `--tools ""` kullanılmaz (soğuk süreçte ilk tur araçsız gidiyordu; gerçek koşularda ilk deneme
  düştü, araçları açık tekrar başardı) → yalnız slash kapalı (~99k/tur). `CLI_YALIN=false` eski davranış.
- Etki (ölçüldü/beklenen): sabit yük tur başına ~98k→62k; gözlem fazı analiz bağlamını (~40k) döngüden çıkarır; FE+BE'de iki döngü → bir; cevap turunda gözlem yok.
  Ölçüm Kullanım Raporu panelinde (aşama "gozlem" vs "gorev:analiz").
- **Araçsız ilk tur / pseudo araç metni:** CLI oturum kayıtlarında başarısız giriş testleri modelin araç çağrısını metin
  olarak yazdığını gösterdi (araçlar ilk turda yok); hep yeniden başlatma sonrası (soğuk npx). Önlem: araçsız tek-tur ya da
  pseudo-araç deseninde 2 ek deneme (2 sn gecikme, yerleşik araçlar açık), `mcp_isit()` boot'ta gerçek MCP el sıkışması (initialize + tools/list) ile ısıtma. Gerçek koşu: restart sonrası ilk giriş testi araçsız (1 tur, 4 sn) → 1. tekrar 5 turda başarılı (mekanizma doğrulandı).
**Test kuralı:** motor çağıran her test `canli_uygulama_baglami_hazirla`'yı mock'lar; aksi hâlde gözlem fazı gerçek
CLI/Playwright açar (test_katman_secimi bunu yaşadı → düzeltildi). Test: `tests/test_gozlem_fazi.py`.

## Bilinen Kısıtlamalar
- CLI modu görsel (PNG/JPG) analiz EDEMEZ (text-only); görsel BRD için API modu gerekir.
- `markdown_to_adf` nested list'leri düzleştirir.
- History limiti 5 (sabit, `save_to_history()`). Tek input dosyası (çok yüklenirse ilk).
- Atlassian-only (Azure DevOps/GitHub Issues yok). macOS-only dağıtım. Tek aktif analiz (sunucu modunda).
## Task Analizi (Jira görev analizi) — UI akışı
> Backend çekme/sınıflandırma: yukarıdaki "Jira Görevleri Özelliği". Bu bölüm UI akışıdır. Dağınık tek-seferlik düzeltmeler `docs/DEGISIKLIK-ARSIV.md`'de (özet index: `docs/DEGISIKLIK-GECMISI.md`). Değişince güncelle.

- **Modal-içi JARVIS reaktör:** üretim/düzeltme sırasında `#jg-proc` (`_jgProcBaslat/_jgProcBitir` + geçen-süre + model readout).
- **İlişkili FE/BE analizi:** görevin bağlı task'ları varsa 'Teknik Analiz Et' önce **seçim paneli** açar (`_jgSecimGoster`): birincil + bağlı task'lar, her biri katman (FE/BE, tahmin `_jgKatmanTahmin`). 'Seçilenleri Analiz Et' her task'ı AYRI analiz eder (`jgIliskiliAnalizBaslat`), diğerleri `iliskili_keys` bağlamı olur; karşı katman yalnız `## Bağımlılık ve Arayüz (FE↔BE)` sözleşmesi olarak yazılır (`gorev_analiz_et(gorev, iliskili, katman)` + `gorev_getir`). Sonuçlar `_jgAnalizSeti`'te; task DEĞİŞTİRİCİ (`_jgSwitcherRender`/`_jgSonucGoster`), her analiz KENDİ Jira görevine ayrı yazılır.
- **Açık soru YAKINSAMASI:** `_gorev_acik_sorular_uret(teknik, gorev, cevaplar, onceki_sorular)` — takip turunda önceki tur soruları + cevaplar prompt'a girer; cevaplanan sorular ÇIKAR, kalan açık olanlar AYNI ID+metinle korunur, yalnız yeni bloklayan belirsizlik eklenir (max 6) → sorular turlar içinde azalır/biter (drift yok). Frontend `jgCevaplariIsle` `onceki_sorular: s.acik_sorular` geçer.
- **Arka plan iş modeli (GÖMÜLÜ + kesintisiz):** analiz/cevap/düzelt/formatla `POST /api/jira/gorev/is/baslat` → arka plan thread (`_gorev_isler`, `_gorev_is_calistir`); UI `_jgIsBaslat`→`/is/durum` polling (`_jgPollDurum`, 2.5sn). **Çok adımlı işler EŞZAMANLI (P1-C, ThreadPoolExecutor, `GOREV_PARALEL`=3)** — ilişkili FE/BE paralel; token ölçümü thread-local (`token_capture_baslat/al`). Panel MODAL değil GÖMÜLÜ (`#jg-preview-card.jg-inline` → `#page-jira-gorevler`); kapatınca iş sürer, üstte 'sürüyor/✓tamamlandı' çipi (`_jgSurenChipGuncelle`), dönünce `_jgReattach` (localStorage `jg-aktif-job`).
- **GERÇEK Durdur (P0-4):** `/is/durdur` o an süren `claude -p`'yi killpg ile ANINDA öldürür (`base._cli_calistir` killable Popen + thread-keyed `_CLI_PROC_REG`, `cli_proc_durdur`); worker `DurdurulduError`'ı iptal sayar, `job["worker_tids"]` tüm pool thread'lerini kapsar. `_cli_calistir` `start_new_session=True` → run.py SIGTERM/SIGINT handler'ı `cli_tum_durdur()` ile köprüler (`_surec_durdur` killpg'i claude'a ulaşsın).
- **İşlem güvenliği:** üretim/düzeltme sürerken Onayla/Düzelt/Cevapları-İşle PASİF + switcher KİLİTLİ (`_jgSwitcherKilit`) → işlem bitmeden başka task içeriği gösterilmez, Jira'ya YAZILMAZ. Her açık soru ayrı kart+cevap kutusu (`_jgSorulariAyristir/_jgSorulariRender`). İteratif düzelt `#jg-duzelt`→`jgAnalizDuzelt`→`/api/jira/gorev/duzelt` (yalnız ilgili kısım). Sorular/cevaplar Jira'ya YAZILMAZ; Onayla yalnız analiz metnini yazar.
- **Bağlam filtresi kaydı:** `jgAnaliz`/`jgCevaplariIsle` öncesi `_jgFiltreKaydet` (buildContextFilter→POST) ekrandaki filtreyi diske yazar. Görev prompt'u ana süreç→teknik formatının başlık kümesini kullanır; yalnız DOKUNULAN başlıklar dolar. NOT: `reference/` boşsa RAG 0 döner.

## Telemetri (Kullanım İzleme) — `skills/telemetri.py`
> `backlog_senkron`/UAT → "## UAT Mutabakat"; `html_mockup` → "## HTML Prototip"; skills modül listesi → CLAUDE.md.

- **Kapsam:** yalnız metadata; olaylar `logs/usage/events.jsonl`'e append + opsiyonel `USAGE_SINK_URL`'e fire-and-forget POST (Apps Script → Sheet write-only; bkz. `docs/telemetri-apps-script.md`). `istatistik()` 0-token deterministik özet.
- **Emit noktaları:** `run.py` (surec/teknik/brd/kapsam/jira_gonder; parent `_bekle` yalnız timeout'ta) · app.py in-process (mutabakat, gorev_analiz, gorev_guncelle, mockup `/api/mockup/generate`).
- **KRİTİK — `_sink_gonder` SENKRON POST** (daemon thread DEĞİL): kısa-ömürlü subprocess (run.py) çıkışında daemon thread öldürülüp POST kaybolurdu → süreç/teknik/brd/kapsam Sheet'e HİÇ ulaşmazdı. olay_yaz işlem sonunda çağrıldığından senkron bloklama sorun değil.
- **Token/maliyet (P0-2 + P1-A):** her AI çağrısı `base.py` birikimli sayaca girdi/çıktı/cache token + maliyet ekler (CLI `usage`+`total_cost_usd`; API `yanit.usage`, `_api_kesilme_uyar` içinden). `token_sayac_oku/token_delta/_token_ekle`; paralelde `token_capture_baslat/al` (thread-local). `olay_yaz(..., token={...})`. Emit: run.py sayaç=koşu toplamı (subprocess taze); app.py `_telemetri_olay(token_bas=...)`. `istatistik()` `token_ozet` (genel) + analist `token{}`. API-cache replay 0 token. Dashboard: `#ku-ozet` Token/Maliyet kartları + analist tablosu sütunları + Excel 4 sütun.
- **Owner-gate:** `OWNER_KONSOL=true` (AUTH'tan BAĞIMSIZ; analist build'lerinde yok → Kullanım+Yetki sekmeleri gizli + `/api/usage/*` 403). ESKİ `USAGE_DASHBOARD` ARTIK OKUNMAZ (kopyalanan owner `.env`'i ekranları açıyordu → `OWNER_KONSOL`'a yenilendi). `auth/me` `usage_admin` döner.
- **Analist kimliği:** UI'dan Ayarlar → "Analist Adı Soyadı" → `analist.json` (gitignore, makineye özel; `/api/analist`, owner-gate YOK). Öncelik: login username > `ANALIST` env > `analist.json` > `ANALYST_NAME` env > OS user; subprocess'e `ANALIST` env ile geçer.
- **Jira key izleme:** `jira_key_ekle()` (jira_gonder → `islem:"acildi"`); `/api/jira/gorev/guncelle` → olay `gorev_guncelle` (`islem:"guncellendi"`). Task adedi `jira_task_arttir()` (hem `jira_agent` hem `jira_tasks`). Excel'de **Detay** (olay-bazlı, key'lerle).
- **Çift sayım önleme:** `olaylari_oku()` — `remote.jsonl` (Sheet, tüm ekip) VARSA yalnız onu okur (owner olayı hem lokal hem Sheet'te → aksi halde iki kez sayardı); yoksa lokal `events.jsonl`. Owner 'Uzaktan Çek' ile tazeler. HTTP `requests` (macOS SSL). Sink URL `VARSAYILAN_SINK_URL` gömülü (yalnız-yazma; `USAGE_SINK_URL` override).
- **Ölçümleme:** isim-sıralı sabit id · dönem bazlı `istatistik(gun, donem, analist)` (gün/hafta/ay trend + tek-analist filtresi) · Analist Özeti (Toplam İşlem/Başarılı/Hatalı/Açılan Task/Toplam Süre=efor) · Analist × Tür matrisi (sabit sütunlar; Teknik Analiz [süreç→teknik] ≠ Görev Analizi [Jira task]) · analist seçilince tür bazında Ort. Süre (yalnız aynı tip içinde ortalanır).
