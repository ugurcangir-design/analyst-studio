# brd-analyst-agent (Analyst Studio) — Claude Code Context

macOS masaüstü uygulaması. BRD/süreç dokümanı → RAG destekli analiz → Jira Epic/Story/Subtask.
Flask + Python **3.10+** (`str|None`), tarayıcı SPA `http://localhost:5003` (v2; v1 = 5002, ayrı dizin/süreç).
İki akış: **Süreç → Teknik → Jira** (ana, FE/BE ayrımı) · **BRD → Kapsam**. Ek: **İnteraktif Analiz** (doküman YOK, sohbetle).

## İnteraktif Analiz (Sohbetle Analiz — doküman yüklemeden, metin/chat ile)
Analist doküman yüklemeden bir isteri/fikir yazar → agent (RAG + domain kuralları + kaynak-öncelikle **topraklanmış**,
Claude chat gibi) **soru sorar / yöntem önerir** → adım adım **birlikte** olgunlaştırılır → hazır olunca **kilometre taşı
butonlarıyla** (`Süreç Analizi Üret` → `Teknik Analiz Üret`) formal analiz üretilir. **MEVCUT motorlar yeniden kullanılır**
(`skills/sohbet_analiz.py` → `surec_analizi_yap(icerik_override=sohbet, ozel_atla=True)` / `teknik_analiz_yap(ozel_atla=True)`)
→ çıktılar `output/surec-analizi.md` · `teknik-analiz.md` → **Çıktılar & Revizyon + Jira (FE/BE / Hiyerarşi / Yeni Task) aynen
akar** (Jira aktarma Çıktı Dosyaları ekranındaki mevcut butonlarla — ekran duplike edilmez). **Miras (tekrar girilmez):**
Bağlam Filtresi + uygulama giriş bilgileri (paylaşılan `context_filter.json`). **YOK:** doküman yükleme · Süreç/Teknik **özel
promptu** (hep varsayılan — `ozel_atla=True` özel promptu yok sayar) · manuel gözlem kapsamı alanı. **VAR:** analiz üretiminde
**canlı uygulama gözlemi** (miras `live_app` config; hedef sohbetten türetilir). Sohbet turu canlı gözlem YAPMAZ (hızlı Q&A);
gözlem yalnız üretim adımlarında. **Global süreç workflow'una DOKUNMAZ** (kendi içinde inline — iki ekran tek state çakışmaz).
Oturum `output/sohbet/oturum.json` (gitignore). Endpoint: `/api/sohbet/{oturum,mesaj,sifirla,uret,uret/durum}` (kimlik-gate,
üretim arka plan iş). **Tazelik:** `surec_var_mi/teknik_var_mi(oturum)` çıktıyı YALNIZ mtime ≥ oturumun ilk mesajı (yoksa
`created`) ise "var" sayar → önceki doküman/sohbet akışının bayat çıktısı sohbetin ürünü gibi GÖSTERİLMEZ (hata: 12 Eylül
çıktısı 15 Ekim sohbetinde göründü). **Arka plan + görünürlük:** üretim daemon thread'de sürer (ekran değişimi/yenileme KESMEZ; restart/kapanma koruması
`_arka_plan_isleri_calisiyor`). `_sohbet_aktif_is()` → `/api/sohbet/oturum.aktif_is` (ekran açılınca sürmekte olan işe YENİDEN
BAĞLANIR, `_shPoll`) + `/api/workflow-state.sohbet_is` (üst-bar işlem çipi + HUD her ekranda "İnteraktif süreç/teknik
analizi üretiliyor · süre"; global workflow'a DOKUNMAZ). `uret/durum` `gecen_sn` döner (180 sn üstü takılma uyarısı). **EKRAN BAZLI İŞ (owner isteri — 'BRD'yi uygulamayla ekran ekran karşılaştır, her ekran için FE/BE task'):** sohbet
ekranı büyütüldü, yeni ekran YOK. (a) **Girişi Test Et** (`POST /api/sohbet/giris-test` → `giris_testi`): miras canlı
uygulamaya kayıtlı hesapla giriş denenir (1 CLI/Playwright çağrısı), sonuç `oturum.giris` + sistem mesajı + ekranda bant
→ 'Wrong Password' gözlem/üretim ÖNCESİ yakalanır. (b) **🌐 Canlı gözlemle yanıtla** (mesaj `{gozlem:true}` → arka plan iş
hedef `gozlem` → `sohbet_mesaj(gozlem=True)`: miras `live_app` ANA adresi + mesaj = hedef, `canli_uygulama_kapsami="surec"`,
önbellek kapalı; mesajlar `gozlem` bayraklı, rozetli). (c) **Sıralı açık sorular**: sohbet ekranı bu oturumun
süreç/teknik/açık-soru dosyalarındaki açık soruları TEK TEK sorar (Cevapla→sonraki / Varsayım / Atla → `POST
/api/sorular/<id>`), sonunda "Cevapları analize uygula" (`/api/sorular/uygula`); `_cevaplanan_sorular_metni` bu oturumun
cevaplarını sohbet turuna ve üretim girdisine KESİN bilgi olarak verir (tekrar sorulmaz). Sistem promptu: SIRAYLA sor,
BRD referansta hazır (yükleme yok), ekran bazlı iş için 'Ekran Task'ları Üret'. (d) **Ekran Task'ları Üret**
(`POST /api/sohbet/ekranlar` → `ekran_listesi_cikar`: sohbet+BRD'den `<ekranlar>` JSON → `oturum.ekranlar` + seçim
tablosu) → seçilenler `POST /api/sohbet/ekran-gorevleri {secilen}` → `ekran_gorevleri`: SENTETİK görev `EKRAN-n`
(summary "menü › ekran", description ister + BRD ref + cevaplar + sohbet) + `canli_hedef` → mevcut Task Analizi iş
sistemine `mode:'fe-be-ayir'` adımları (`_jgIsBaslat` + `switchTab('jira-gorevler')`): her ekran için canlı gözlem +
BE + FE analiz → Task Analizi'nde görünür → Jira'ya **'Yeni Task Aç'** (FE+BE, Blocks, Epic'e Relates). Altyapı:
`jira_gorev_is_baslat` tüm adımlar görev dict'liyse Jira bağlantısı istemez + `canli_hedef` taşır; `_adim_isle`
`canli_hedef` varsa `_canli_tabanli_baglam` ile `canli_baglam_override` geçer; sentetik `EKRAN-` kayıtları eğitim
havuzuna/depoya GİRMEZ; `gorev_yeni_task_olustur` `_ID_DESENI`'ye uymayan kaynak anahtarını yok sayar; UI sentetik kayıtta
'Onayla ve Jira'da Güncelle' kapalı. Test: `tests/test_sohbet_ekran.py` (AI enjekte, 0 token).
**BFF KEŞFİ (sohbetten — `bff_kesfet`):** "BFF Keşfi (CRUD)" butonu (ekran adı sorulur) + ekran envanteri satırlarında
🔌 düğmesi → `POST /api/sohbet/bff-kesif {ekran}` → iş hedefi `bff` → `bff_kesif.kesfet(miras live_app ANA adresi,
ekran, ekran_bazli=True)` (anahtar Task Analizi ile ORTAK) → `oturum.bff[]` + sistem mesajı (yakalanan POST/PUT/DELETE
özeti, "Raporu gör" → `GET /api/sohbet/bff-rapor?anahtar=`). `_bff_raporlari_blogu` bu oturumun TAZE raporlarını her sohbet
turuna ve `_uretim_girdisi`'ne (Süreç/Teknik üretim) GERÇEK sözleşme olarak verir; üretim öncesi OTOMATİK keşif YOK
(owner kararı — yalnız mevcut raporlar; ekran bazlı işte keşif Task iş sistemi üzerinden zaten otomatik). Test:
`tests/test_sohbet_bff.py`. **Durdur / Devam Ettir / İptal:** `POST /api/sohbet/uret/durdur {job, iptal?}` → `_sohbet_is_kes`: iş
`durduruldu|iptal`, o an süren claude CLI `cli_proc_durdur(worker_tid)` ile process-grubuyla ÖLDÜRÜLÜR (token yakma anında
kesilir; `DurdurulduError` hata sayılmaz). `POST /api/sohbet/uret/devam {job}` yalnız `durduruldu` işte → AYNI hedefle yeni iş
(eski kayıt `devam_etti`); tamamlanan analiz aşamaları `_api_cagri` önbelleğinden gelir, yalnız kesilen aşama yeniden çalışır
(gerçek 'kaldığı yerden' — model çıktısı dondurulamaz). `oturum.durdurulmus_is` → ekran yenilense de Devam Ettir/İptal sunulur;
HUD'da sohbet işi için ⏸ Durdur. `base._onsoz_kirp` 2 katlı: baştaki düz ön-söz + meta-yorum/ayraç SONRASI, ilk
başlık/tablodan önceki İngilizce iç-konuşma paragrafı (`_ONSOZ_IC_KONUSMA`; gövde paragrafı/JSON dokunulmaz). Test: `tests/test_sohbet_tazelik.py`. UI: `screens/sohbet.html` (nav "İnteraktif Analiz", Analiz grubu; chat thread + `sh-*`). Test: `smoke_test`
(oturum + doğrulama uçları). **NOT — motor refactor'u:** `surec_analizi_yap(icerik_override, dosya_adi_override, ozel_atla)` +
`teknik_analiz_yap(ozel_atla)` opsiyonel parametre aldı — override YOKKEN davranış AYNEN korunur (doküman akışı etkilenmez).

## Analyst Studio — TEK ve NİHAİ sürüm (repo `ugurcangir-design/analyst-studio` · dal `main` · port **5003**)
Dizin: `brd-analyst-agent-v2`. **Repo: `ugurcangir-design/analyst-studio`, dal `main`.**
Bu, agent'ın **tek ve güncel** sürümüdür. Eski sürüm (v1 — `Analysys_Agent` reposu, port 5002,
`/Users/dt/brd-analyst-agent`) **EMEKLİYE AYRILDI ve git'ten silinecek**; ona **referans/bağımlılık
BIRAKILMAZ** (kırılır). Başlatma: `./start.sh` (varsayılan port **5003**; `app.py` default'u da 5003 →
env eksikse bile başka porta düşmez). AUTO_UPDATE `origin/main`'i `ff-only` çeker. Faz/tarihçe:
**`docs/DEGISIKLIK-GECMISI.md`**; eski geçiş yol haritası (tarihsel): `docs/ROADMAP-V2.md`.
- **Ekran-eklenebilir arayüz** (Faz 0): ekran page blokları `templates/screens/*.html` partial'larına
  çıkarılıp `index.html`'de `{% include %}` edilir — bkz. `templates/screens/README.md`.
  İlk çıkarılan ekran: `kilavuz`. Kalan ekranlar Faz 2'de kademeli taşınır.
- **Faz 1 — Revizyon oturumu:** `skills/revizyon.py` (deterministik: versiyon/geçmiş/onay/geri-al/diff,
  `output/revizyon/`) + `skills/revizyon_ai.py` (`bolum_duzenle`: yalnız hedef bölüm AI'a gider) +
  `/api/revizyon/*` + `screens/revizyon.html`. Tam yeniden-üretim (`/api/rerun`) dokunulmadan yanında durur.
- **UI v3 — görsel yeniden tasarım (tüm ekranlar, YALNIZ v2):** `index.html` `:root`/`[data-theme]` token'ları
  yeniden palete çevrildi — yumuşatılmış slate + **indigo** aksan (koyu `#6366F1` / açık `#4F4DD6`), yüksek metin
  kontrastı, 10px köşe. Başlıklarda **Space Grotesk** (`--font-display`; Geist gövde + Geist Mono veri korundu).
  **Renk anlamı:** kırmızı `--run` = çalışan işlem · amber `--yellow` = analist sırası/onay (`.status-waiting`) ·
  yeşil = başarı · indigo = marka/aksiyon. Token-tabanlı olduğu için değişiklik tüm ekranlara yansır.
  **Yeni bileşenler (index.html):** üst barda kalıcı **işlem çipi** `#run-chip` (her ekranda; `_updateRunChip(s)`
  ile `updateUI`'den beslenir — running→kırmızı+süre / bekliyor→amber "Onayınızda"; tıkla→HUD veya pipeline) +
  **İşlem Modu HUD** `#islem-modu` (JARVIS tarzı kırmızı reaktör; `islemModuAc/Kapat`, Esc kapatır —
  kapatınca iş arka planda sürer; süreç VE teknik analiz başlayınca otomatik gelir — `running=calisiyor&&!bekliyor`).
  **İÇERİK ALANINA CONTAIN edilir, tam-ekran DEĞİL** (`position:fixed; top:44px topbar altı; left:232px sidebar sağı`;
  daraltılmış menüde `left:60px`; ≤760px'de `left:0`) → sol menü + üst-bar açıkta kalır (analist gezinebilir, run-chip
  görünür), yalnız içerik butonları örtülür → **yanlış tıklama engellenir + çalışma başladığı belli olur**.
  "hazırlanıyor" analiz görseli de kırmızıya çekildi.
- **UI v3 — ekran/menü düzeni & yeniden adlandırmalar (YALNIZ v2):**
  **Açılır-kapanır sol menü** (`sidebarAcKapa()` → `.layout.sidebar-collapsed`, localStorage `sidebar-collapsed`) +
  **grup başlıkları katlanır** (`navBolumAcKapa()`, chevron, localStorage `nav-collapsed-<grup>`; rol-gizli item'lar
  `rol-gizli` sınıfıyla açılışta sızmaz). **Analist kimliği** sol alt (`#analist-kimlik`: `#ak-avatar`/`#ak-ad`/`#ak-rol`)
  + üst-bar avatarı (`#topbar-avatar`) → `/api/analist`'ten boot'ta + Ayarlar kaydında (`_analistKimligiUygula`).
  **Ana Sayfa (`pano.html`)** kart tabanlı: hızlı-eylem kartları + sistem-sağlığı kart ızgarası (`.pano-cards`/`.pano-card`).
  **Yeniden adlandırma:** "Jira Görevleri" → **Task Analizi** (iç tab anahtarı `jira-gorevler` KORUNDU; endpoint/id değişmedi),
  "Kullanım" → **Kullanım Raporu**, "Yetki & Denetim" → **Yetki**. **Kılavuz menüden kaldırıldı** — üst-bar **?**
  düğmesi (`switchTab('kilavuz')`) açar; sağ-üst Ayarlar düğmesi kaldırıldı (menüde zaten var).
- **Form dili — TEK tutarlı giriş stili (tüm ekranlar):** giriş alanları için form-reset tabanı
  (`input[type=...]`, `textarea`, `select` + `.field-input`/`.ctx-input`/`.setting-input`/`.form-group input`)
  → hiçbir giriş tarayıcı-varsayılanı (beyaz) kalmaz; `--surface2` zemin, `--border-strong`, 13px, 8×11 padding,
  indigo focus ring. Yeni bir input tipi eklerken bu tabana düşer (bespoke sınıf daha yüksek özgüllükle ezer).
  Yardım metinleri (`.field-sub/.field-hint/.ctx-field-sub/.jg-sub/.la-ipucu`) okunaklılık için `--text2`,
  12px, satır-yüksekliği 1.55, `max-width` ile sınırlı — soluk/küçük değil.
  **Aksiyon-bölümü deseni (onay kapıları + Jira Köprüsü — hedefli düzelt kutusu):** tek satırda sıkışık
  input+buton+mesaj yerine → üst-etiket + **tam-genişlik input (flex:1)** + buton aynı satırda, durum mesajı
  AYRI satırda (input'la yarışmaz). İki tekrar-kullanılabilir sınıf: `.adim-duzelt*` (index.html onay kapıları
  `surec-act-onay`/`surec-act-teknik-onay` — `adim-sohbet-*` id'leri KORUNDU) ve `.kopru-actions`/`.kopru-duzelt*`/
  `.kopru-eylem` (kopru.html — `kopruIs('duzelt'|'analiz'|'iliskili-ac')` onclick'leri KORUNDU). ≤640px'de dikey
  yığılır. Yeni bir "hedefli düzelt / eylem" satırı eklerken bu deseni kullan (bespoke tek-satır flex değil).
- **Denetim (audit) KALDIRILDI (v3):** `skills/denetim.py` silindi, `_denetim()` no-op, `/api/denetim` endpoint'i +
  `logs/audit.jsonl` + `/api/saglik` `denetim{}` alanı + Yetki ekranındaki Denetim paneli kaldırıldı. Analist iş
  takibi tamamen **Kullanım Raporu**'ndadır (`skills/telemetri`). Görünürlük (Yetki) yönetimi aynen durur.
- **Sağlamlaştırmalar (v3 inceleme):** (1) `base._api_cache_key` CLI modunda `aktif_cli_model()`'i anahtara katar →
  model değişince (Sonnet→Opus) eski sonuç yanlış "önbellek hit" dönmüyor. (2) `base.api_cagri_kapanisli(sistem,
  mesajlar, kapanis, ...)` — birleşik XML çağrılarında (BRD `</brd_sorular>`, Kapsam `</alternatif_surecler>`)
  kapanış-etiketi retry'ı → ikinci blok limitte kesilirse sessizce kaybolmuyor (teknik analizdeki `_teknik_uret_tam`
  deseni). (3) `/api/sorular/uygula` artık ARKA PLANDA (daemon thread + `/api/sorular/uygula-durum` polling) —
  bloklayan refine istek thread'ini tutmuyor. (4) `kod_kaynagi.ara` ripgrep hata verse de Python fallback çalışır.
  (5) **Durdur GERÇEKTEN durdurur:** `/api/reset` → `_surec_durdur()` çalışan alt-süreci PROCESS GRUBUYLA
  (`os.killpg`, `start_new_session`) öldürür SONRA `wf.sifirla()`. Eskiden yalnız state sıfırlanıyordu →
  subprocess sürüp durumu geri yazıyordu ("analiz kendi başlıyor"). `_durduruldu` bayrağı `_bekle`'nin bunu
  hata sanmasını önler; UI `resetWorkflowUI()` run-chip'i temizler + HUD'u kapatır. (6) `/api/sorular/uygula/durum`
  3-segmentli — 2-segmentli olsaydı dinamik `/api/sorular/<id>` (POST/DELETE) ile çakışıp GET 405 verirdi.
  (7) Küçük etiket/çip okunaklılığı (`.panel-tag`/`.ds-chip`/`.ds-panel-tag`/`.ctx-active-badge`) `--text2`+büyütüldü,
  "aktif" → büyük harf pill. (8) **Yeni yükleme = yeni oturum:** `/api/upload` artık `wf.sifirla()` yapar
  (çalışırken 409 verir) → bayat "onay_bekleniyor"/tamamlandı durumu yeni dokümana taşınmaz. (9) **Sorular
  tazelik filtresi:** `parse_ve_birlestir(taze_esik)` yalnız bu oturuma ait (mtime ≥ `_oturum_baslangic()`) TAZE
  çıktıların sorularını gösterir; bayat/önceki-oturum soruları düşürülür — süreç analizi tamamlanmadan hayalet soru
  görünmez (tüm analiz tipleri). `/api/sorular` her zaman filtreli döner. **Oturum-aidiyeti (bayat cevap taşınmaz):**
  soru id'leri (Q-001…) KONUMSALDIR — yeni doküman analizinde AYNI id farklı soruya denk gelir. Merge, `(id, kaynak_dosya)`
  eşleşen mevcut sorunun durum/cevabını YALNIZ o soru bu oturuma aitse (`olusturuldu_at` saniyesi ≥ `taze_esik` saniyesi —
  `_bu_oturuma_ait`) korur; önceki oturumdan devrolan aynı-id soru YENİ ('acik') sayılır. Yoksa yeni süreç analizinin açık
  soruları eski cevaplarla yanlışlıkla "tümü cevaplandı" görünürdü (yeni parse'ta otomatik iyileşir).
  **Soru formatı — dayanıklı parse:** `parse_md_sorular` üç format yakalar: `### Q-T-XXX:` blok · `| Q-XXX |`
  tablo · fallback "Açık Sorular" başlığı altında **numaralı VEYA madde-işaretli** liste (`_LISTE_ITEM`:
  `1.`/`2)`/`-`/`*`/`•`; bold `**Q-01:**` id de temizlenip yakalanır). Model açık soruları bullet-liste
  üretince (tablo/### değil) parse edilmiyordu → Sorular sekmesi boş kalıyordu; artık yakalanır. Test: `tests/test_sorular.py`.
  (10) **Ekran adları:** "Çıktılar" →
  **Analiz Dosyaları**, "Görüntüleyici" → **Çıktı Dosyaları** (iç tab anahtarları `ciktilar`/`output` korundu).
  (11) **Yetim workflow uzlaştırması:** `/api/oturum` — workflow "settled" (onay_bekleniyor/teknik_onay/
  brd_revize/tamamlandi) ama çalışmıyor ve **0 güncel çıktı** varsa (çıktı önceki oturumdan) → `wf.sifirla()` +
  idle. Dashboard/Çıktılar/üst-bar tutarsız "Analist onayı bekleniyor + GÜNCEL ÇIKTI 0" göstermez; legit onay
  (≥1 güncel çıktı) korunur, çalışan analize dokunulmaz.
  (12) **Kanıt çipleri + Gözlem rozeti (Faz 1):** Çıktı Dosyaları'nda markdown render sonrası `_kanitCipleriIsle`
  `[K: …]` kaynak etiketlerini renkli çipe çevirir (gerçek veri=yeşil · Confluence=mavi · BRD=nötr · Jira=indigo ·
  türetilmiş=amber · kaynaksız=kırmızı) + üstte özet sayaç ("N etiket · X gerçek · ⚠ Y doğrulanmalı") — yalnız metin
  düğümlerinde, `code/pre` hariç. `_api_cagri_cli` canlı-gözlem sonucunu `output/.gozlem-durum.json`'a yazar
  (`_gozlem_durum_yaz`: yapildi/num_turns/reddedilen — makine-doğrulanmış); `/api/oturum` `gozlem` alanı (yalnız bu
  oturuma aitse) → süreç/teknik çıktısında "🌐 Canlı gözlem yapıldı · N tur" / "⚠ YAPILAMADI" rozeti.
  (13) **Adım sohbeti + geri dönüş (Faz 2 — "önceki adımı yeniden çalıştırmak zorunda kalma"):** onay
  kapılarında (`#surec-act-onay`, `#surec-act-teknik-onay`) tek satırlık **"Bu adımı düzelt"** kutusu →
  `POST /api/adim/duzelt {dosya, talimat}`: hedef dosya ADIMDAN bellidir (niyet yönlendirme YOK); hedef bölüm
  talimattaki yapısal ID (`_ADIM_ID_DESEN`: PA/BR/EK/EF/AF/AC/FR/NFR/Q/PO/T-FE/T-BE-nnn) ya da bölüm başlığı
  kelimesinden türetilir (`_adim_hedef_bolum`) → yalnız o bölüm `revizyon_ai.bolum_duzenle` ile düzenlenir ve
  **otomatik `revizyon.onayla`** (sürüm oluşur, Revizyon ekranından Geri Al). **KRİTİK:** `bolum_duzenle`+`onayla`
  yalnız revizyon oturumunu günceller — `revizyon.onayla` ÇIKTI DOSYASINI YAZMAZ; her çağıran onaylı içeriği
  (`onayli_icerik`) `output/<dosya>`'ya GERİ YAZMALI (`/api/adim/duzelt` + `_sorulari_hedefli_uygula` + revizyon
  onayla/geri-al uçları bunu yapar). Yoksa dosya diskte bayat kalır ve sonraki adım (teknik analiz
  surec-analizi.md'yi DOSYADAN okur) düzeltilmemiş içeriği kullanır (regresyon: `tests/test_soru_hedefli.py`).
  **BAYAT OTURUM KORUMASI (veri kaybı önleme):** revizyon oturumu dosya-adı slug'ıyla anahtarlı ve pipeline/
  rerun/upload çıktıyı yeniden ürettiğinde tazelenmezdi → `bolum_duzenle` oturumu (eski içerik) baz alıp geri
  yazınca güncel analizi EZİYORDU. Artık: `bolum_duzenle` oturum içeriği ≠ disk ise diski otorite kabul edip
  `revizyon.yeniden_bazla` ile oturumu tazeler; `/api/upload` yeni dokümanda `revizyon.oturumlari_temizle()`
  yapar (regresyon: `tests/test_revizyon.py` #1). **Manuel revizyon yazıcıları** (onayla/geri-al) artık
  `_revizyon_lock`'u non-blocking alır (meşgulse 409) → arka plan hedefli-düzeltme ile yarış yok. **Sorular
  worker** import/kilit hatasında kilitleri sızdırmaz (dış try/finally). Bölüm bulunamazsa
  `tam_uretim_gerekli` döner → UI analiste ID eklemesini ya da "Tam yeniden üret" (eski `/api/rerun`, artık
  `<details>` içinde SON ÇARE) önerir; asla sessizce tümü yeniden yazılmaz. **"◂ Süreç analizine dön"**
  (`POST /api/geri-don` → `wf.surec_adimina_geri_don()`, yeni geçiş TEKNIK_ANALIZ_ONAY_BEKLENIYOR→
  ONAY_BEKLENIYOR): süreç analizi YENİDEN ÇALIŞMAZ, teknik-analiz.md silinmez; analist süreçte hedefli
  düzeltir, "Devam Et" teknik analizi yeniden üretir. **Soru cevapları hedefli:** `/api/sorular/uygula` →
  `_sorulari_hedefli_uygula`: `bagli_id` bölümü analiz dosyasında (`_SORU_HEDEF_ANALIZ`: acik-sorular→
  teknik-analiz · brd-sorular→brd-analizi · **surec-analizi→surec-analizi (kendisi)** · teknik-analiz→kendisi)
  bulunursa yalnız o bölüm düzenlenir; bulunamayanlar toplanıp `yeniden_calistir(hedef, …)`'a (TÜM **hedef=analiz**
  dosyası yeniden üretim — SORU dosyası `kaynak` DEĞİL; kaynak≠hedef'te kaynağı üretmek cevabı analize hiç
  işlemez=sessiz kayıp) düşer (`sonuclar[].hedefli/tam_uretim`). Süreç analizi soruları (`### Q-XXX:` blok,
  `bagli_id`=PA-XXX/BR-XXX) doğrudan surec-analizi.md'de yaşar → cevap AYNI dosyanın ilgili bölümüne hedefli
  uygulanır (gövde-içi ID fallback). Test: `tests/test_soru_hedefli.py`.
  **AÇIK SORU FORMATI — ÜÇ ANALİZDE TUTARLI (birleştirildi):** her analiz aynı `### <ID>: [Başlık]` blok yapısını
  kullanır (`- Kategori/Öncelik/Bağlı ID/Soru/Mevcut Durum/Beklenen Yanıt/Etki`). YALNIZ **ID öneki farklı**
  (izlenebilirlik): süreç `Q-XXX` · teknik `Q-T-XXX` · BRD `PO-XXX`. Eskiden süreç TABLO, teknik+BRD blok idi →
  süreç de bloğa çekildi (base.py). Parser (`skills/sorular.py`) yine de HEPSİNİ yakalar (blok · tablo · numaralı ·
  **bullet** · bold `**Q-01:**`) — model sapması olsa bile Sorular sekmesi dolar. **`revizyon_ai.bolum_bul` iki aşamalı:**
  (1) başlık eşleşmesi (teknik analiz — ID başlıkta), (2) başarısızsa **gövde-içi ID fallback** (süreç analizi —
  ID gövdede satır-içi `**PA-003:** …`; `anahtar`'daki ID token'ını içeren EN DERİN bölüm) → süreç Q&A cevapları da
  hedefli/ucuz uygulanır, tam-regenerasyona düşmez. ID yoksa/bulunmazsa None (tam-regen — doğru davranış).
- **Değişiklik Etkisi + Süreç/Ekran Bütünlüğü + Zorunlu Soru (analiz uçtan uca kapansın, BÜYÜMESİN):**
  `skills/degisiklik_etkisi.py` (0 token) girdide zorunluluk kaldırma/silme/alan kaldırma/pasif/güncelleme/tip
  değişimi sinyali bulursa değişen öğe adlarını Swagger+Confluence+Jira referanslarında arar (**Olası
  Tüketiciler**) ve analize "DEĞİŞİKLİK ETKİSİ" talimatı ekler — AYRI bölüm değil: süreçte mevcut Etki Analizi'ne
  kısa tablo + etki ilgili akış adımına işlenir; teknik DB/API/cache karşılığı; Task hata modunda tek `Etki:`;
  yalnız 'güncelleme' sinyalinde tablo yok. `_BUTUNLUK_KURALLARI` (base.py) `prompt_yukle` ile süreç/teknik/görev
  promptlarına HEP eklenir (override'da da): **testçi kontrol listesi DEĞİL** — süreç↔ekran eşleşmesi,
  giriş-çıkış, karar noktalarının tüm dalları, veri sürekliliği, etki akışta, kriterler akışı doğrular; eksik
  halka ilgili MEVCUT bölümde tamamlanır. Belirlenemeyen riskli nokta → `- Zorunlu: Evet` soru → parse
  `zorunlu`, `zorunlu_acik`, kırmızı ZORUNLU rozeti; **YUMUŞAK ENGEL** (owner kararı): süreç/teknik onay ve Task
  Jira yazma/yeni task öncesi `confirm` — devam edilirse Task gövdesine `## ❗ Cevap Bekleyen Zorunlu Sorular`
  eklenir (few-shot'tan temizlenir). Süreç sonuna `akis_butunluk_denetimi` (akışa bağlanmamış AF/EF/EK/BR +
  tanımsız referans). Ayrıntı → `docs/MIMARI.md` "Analiz Zenginleştirmeleri". Test: `tests/test_degisiklik_etkisi.py`.
  **Akış Kapatma (Faz 3 — `skills/akis_kapatma.py`):** süreç + teknik analiz SON kayıttan sonra OTOMATİK
  (özel promptta atlanır): 1 AI tespit çağrısı (≤8 gerçek boşluk) → bilgi analizde/kaynakta varsa yalnız
  boşluğun TANIMLANDIĞI bölüm minimal düzeltilir (`_hedef_bolum`; korumalar: başlık aynen, kısalma/aşırı büyüme
  RED → soruya döner), yoksa açık soru (süreç: analizin Açık Sorular'ı `Q-` · teknik: `acik-sorular.md` `Q-T-`).
  TEK revizyon → Revizyon'dan Geri Al. Özet `output/.akis-kapatma.json` → `/api/pano.akis_kapatma` → onay kapısı
  "N boşluk kapatıldı · M soru açıldı". Task Analizi'nde **"Akışı Kapat"** butonu (iş modu `akis-kapat`, istemci
  Geri Al). `AKIS_KAPATMA=false`/`HIZLI_MOD` kapatır. Test: `tests/test_akis_kapatma.py` (AI enjekte, 0 token).
- **Kaynak-öncelik sırası (KANONİK, tek liste — `_ORTAK_EK_KURALLAR` + 4 rol promptu hizalı):**
  `Swagger > Canlı Uygulama Gözlemi > Confluence > BRD/Süreç > Jira > UI`. İlke: **gözlemlenen/doğrulanabilir
  gerçek veri (Swagger sözleşmesi + MCP canlı gözlem), tarif edilen istekten (BRD) ÜSTÜNDÜR** — BRD
  hatalı/güncel-olmayan olabilir. Olgusal çelişkide (endpoint/alan/tip/gerçek davranış) gerçek veri kazanır,
  çelişki yine Açık Sorular/Tutarsızlıklar'a raporlanır. Ana doküman analizin KONUSU/izlenebilirlik çapası olarak durur.
  **GETİRİM SIRASI de kanonikle hizalı (`_ref_bloklari_olustur` TIP_KONFIG):** referans blokları Swagger →
  Canlı Uygulama → Confluence → Jira → Diğer sırasıyla çekilir. Global getirim bütçesi (`_ref_global_butce`;
  CLI ~100k, API ~140k) tipler boyunca birikimli tükenir ve dolunca kalan tipler ATLANIR → en yetkili kaynak
  (Swagger/canlı gözlem) HER ZAMAN önce girer, bütçe baskısında en düşük öncelikli (Jira/diğer) düşer.
  **CORPUS-GENELİ OTOMATİK ALAKA GETİRİMİ (Faz 1 — analist keyword girmez):** `_ref_bloklari_olustur(ref, sorgu_metni)`
  bir sorgu (analiz edilen DOKÜMAN metni) alırsa → `retrieval.en_alakali_corpus`: TÜM referans dosyalarının parçaları
  tek BM25 indexinde sorguya göre sıralanır ve bütçeye yalnız **en alakalı parçalar** girer (100+ dosya / ~10M
  karakterden ilgili ~%1; dosya sırası/tesadüf değil). Sorgu = doküman metni (`_ref_sorgu_hazirla`; str veya
  input_hazirla content-listesi → `_icerik_metni`) + varsa manuel `context_filter` keyword'leri (**5× boost** ile
  ağırlıklandırılır ama ZORUNLU değil — analist boş bırakır, agent dokümandan kendi bulur; keyword yalnız opsiyonel
  odak/daraltma). Her analiz KENDİ girdisini sorgu geçirir → süreç: yüklenen doküman · **teknik: kaynak
  süreç-analizi.md (teknik-lezzetli sorgu)** · BRD/kapsam: input · delta: CR metni · jira-görev: task özet+açıklama.
  Tip başına limit + kanonik sıra `_ref_alaka_bloklastir`'da korunur. Sorgu yoksa / hiç alaka yoksa / hata →
  eski **dosya-sıralı, tip-limitli fallback** (keyword-odaklı `_keyword_odakli_metin`). Tüm analizler
  `referans_dosyalari_hazirla`+`_ref_bloklari_olustur` çağırır; süreç/teknik/delta/jira-görev ayrıca
  `canli_uygulama_baglami_hazirla` (MCP canlı gözlem) ekler. UI: Bağlam Filtresi alanları "otomatik" rozeti +
  "boş bırakın, agent bulur" açıklaması; keyword alanı → **"Odak / Yönlendirme (opsiyonel)"**.
- **Bağlam filtresi — Jira Issue Keys (uzaktan çekme):** ekrandaki "Jira Issue Keys" alanı (`ctx-jira-keys` →
  `context_filter.jira_keys`) `filtrele_referanslar`'da ÖNCE yerel export'ta (`reference/jira/*.json`) aranır;
  yerelde BULUNMAYAN key'ler doğrudan Jira'dan (`_jira_keyleri_uzaktan_cek` → `jira_gorevleri._taze_issue_oku`
  bulkfetch, lazy import) çekilip `_context_filtered.json`'a eklenir → proje sync'i yapılmamış olsa bile girilen
  task'lar bağlama girer. Yalnız EKSİK key çekilir (yereldeki tekrar çekilmez); Jira bağlı değil / ağ / yetki
  hatasında BOŞ döner (analiz kırılmaz, uyarı loglanır). Yerel referans hiç yoksa bile jira_keys varsa fetch
  çalışır (`referans_dosyalari_hazirla`). Test: `tests/test_baglam_jira.py`.
- **Faz 2 — Ürün kalitesi:** tasarım sistemi `static/ds.css` (`ds-*`); ekranlar `screens/ciktilar.html`
  (`/api/oturum`, tazelik = mtime ≥ oturum başlangıcı), `delta.html` (Süreç'ten ayrıldı, `da-*` ID korundu),
  `yetki.html`; sidebar iş akışına göre gruplu (Analiz / Çıktılar & Revizyon / Jira / Kaynaklar / Yönetim 🔒).
  **Roller:** owner (AUTH kapalı → tek kullanıcı; açık → `ADMIN_USER`) / analist. Analist, owner'ın
  `gorunurluk.json`'da (repoda İZLENİR) gizlediği id'ler hariç her şeyi kullanır; sunucu tarafı
  `gorunurluk_kontrol` + UI `_rolUygula()`. (Denetim/audit kaydı v3'te kaldırıldı — üstteki UI v3 notuna bak.)
  **Analist kimliği — ZORUNLU şirket e-postası (agent kapısı, Adım 1):** Ayarlar'da ad-soyad + şirket
  e-postası (`analist.json`, YEREL+gitignore → ham e-posta git'e girmez). Domain zorunlu:
  `SIRKET_EPOSTA_DOMAIN` (koda gömülü default `sans-technology.com`, env ile ezilebilir — telemetri sink
  URL'i gibi operasyonel sabit). `_eposta_gecerli` (format + domain) + `_kimlik_tam_mi`. `before_request`
  **`kimlik_kontrol`**: kimlik tam değilse `_KIMLIK_GEREKLI_ONEKLER`'deki iş-başlatma uçları (upload/run/
  rerun/delta/mockup/jira-gorev/jira-fe-be/jira-hierarchy/approve-teknik/jira-kopru/sorular-uygula/adim-duzelt/geri-don) mutating isteklerde 403
  `kimlik_eksik` döner (GET/okuma + `/api/analist` serbest). `/api/analist` GET `{ad_soyad,eposta,domain,
  kimlik_tam}`, POST domain doğrular. Telemetri olayına `eposta` eklenir (Kullanım Raporu stabil atıf).
  UI: Ayarlar e-posta alanı + kimlik eksikse kırmızı uyarı bandı (`_kimlikBandiGuncelle`). Honor-system
  (lokal, kendi-beyan — teknik engelleme değil, düzen/atıf). Test: `smoke_test` kimlik kapısı kontrolleri.
  **Rol→ekran yetkisi (Adım 2-3, telemetri-güdümlü):** `roller.json` (repoda İZLENİR, **PII'siz**):
  `{kullanicilar: {<eposta_hash>: rol}, ekran_roller: {ekran_id: rol}}`, `eposta_hash = sha256(_ROLLER_SALT +
  küçük-harf e-posta)` → git'e ham e-posta GİRMEZ. **İsimler elle girilmez** — Kullanım Raporu'ndan
  (`telemetri.analistler_listesi`, e-posta ile) çekilir; owner yalnız **rol atar** (dropdown). Ekranlar rollere
  atanır (`ekran_roller`: o ekranı görebilecek EN DÜŞÜK rol). Roller rütbeli: `analist(0) < owner(1)`
  (`_ROL_RUTBE`). **ETKİN rol (`_etkin_rol`) — KRİTİK:** görünürlük `_owner_mi`'ye DEĞİL ETKİN role dayanır
  (yoksa AUTH-off pilotta herkes `_owner_mi`=True → roller HİÇ çalışmazdı). AUTH-off: `owner` = `owner_konsol.json`
  işareti, yoksa yerel e-postaya atanmış rol (default analist). AUTH-sunucu: `owner` = `ADMIN_USER` (`_admin_mi`);
  owner_konsol per-makine işareti sunucuda YOK SAYILIR. **Etkin görünürlük** `_etkin_gizli()`: ETKİN rol, ekranın
  gerektirdiği rolden DÜŞÜKSE ekran gizli; `_ekran_gerekli_rol` önceliği: `ekran_roller` > eski `gorunurluk.json`
  (gizli→'owner') > 'analist' (VARSAYILAN: hiçbir şey gizli değil — owner "Yalnız owner" atayana kadar). `_rol()` +
  `gorunurluk_kontrol` + `/api/auth/me.{rol,gizli,auth_aktif}` bunu kullanır → her istekte okunur, restart'sız.
  **UI `_rolUygula`:** `me.gizli` HER ZAMAN uygulanır; Yönetim grubunu wholesale gizleme YALNIZ AUTH-sunucu
  analistinde (AUTH-off analist Ayarlar/Güncelleme/Jira Ayarları'na erişmeli — e-posta ZORUNLU). **OKUMA vs YAZMA — app-sahibi
  ile owner-ROLÜ ayrımı (KRİTİK, GÜNCELLENDİ):** 'Uygulama bana ait; benim yerime kimse değişiklik yapamaz' kuralı.
  İki ayrı yetki: **(OKUMA)** `_usage_yetkili_mi() = _etkin_rol()=="owner"` → Yetki ekranından **owner rolü verilen kişi
  kendi localinde Kullanım Raporu'nu GÖRÜR + ekip verisini ÇEKER** (rapor okuma). **(YAZMA/YÖNETİM)** `_yetki_paneli_mi()
  = _super_owner_mi()` → rol atama / görünürlük / owner config YALNIZ **UYGULAMA SAHİBİNDE**. `_super_owner_mi()`:
  AUTH-off → `owner_konsol.json` yerel işareti (gerçek sahip kendi makinesinde açar), AUTH-sunucu → ADMIN_USER.
  **Owner ROLÜ atanmış kişi (Rozin) `_super_owner_mi`'yi KARŞILAMAZ** → Kullanım'ı okur ama app-sahibinin rollerini/
  bilgisini DEĞİŞTİREMEZ; Yetki ekranı nav'ı ona görünmez (`me.yetki_admin=_super_owner_mi`). `_etkin_rol` (OKUMA için)
  üç yol: (a) owner-konsol işaretli makine, (b) roller.json'da hash'le 'owner' atanan (per-user), (c) AUTH admin. Rol-YAZMA
  uçları (`/api/roller/*`, `/api/gorunurluk` POST) `yetki_gerekli` (`_super_owner_mi`); GET okuma da app-sahibinde.
  `/api/auth/me` alanları: `usage_admin` (OKUMA=owner rolü) · `yetki_admin`/`super_owner` (YAZMA=app-sahibi). Test:
  `tests/test_roller.py` (owner rolü → Kullanım okur ama `_super_owner_mi` False; app-sahibi owner_konsol → yönetir). Uçlar (owner-gate `yetki_gerekli`): `GET /api/roller` (çekili kullanıcılar +
  ekran-rolleri), `POST /api/roller/kullanici` (`{eposta, rol}` → hash→rol), `POST /api/roller/ekranlar`
  (`{ekran_roller}` topluca). UI: `screens/yetki.html` — "Kullanıcılar & Roller" (çekili isimler + rol dropdown,
  otomatik kayıt) + "Ekran Yetkileri" (her ekran → rol dropdown, Kaydet). `roller_yerel.json` KALDIRILDI
  (isimler telemetriden). **Kimlik bildirimi:** `POST /api/analist` (e-posta kaydı) arka planda
  `telemetri.kimlik_bildir()` → sink'e `kimlik` olayı (ad+e-posta) → analist, analiz çalıştırmadan
  e-posta girer girmez owner roster'ında görünür. `kimlik` olayı istatistikten HARİÇ (işlem sayılmaz).
  `/api/roller` roster'ı e-postası HENÜZ gelmemiş isimleri de gösterir (`atanabilir:false`, "e-posta
  bekleniyor" — eski sürümdeki/e-postasız analistler) + bu makinenin kendi kimliğini başa ekler (owner
  kendini hemen görür). `analistler_listesi` HEM `remote.jsonl` (ekip, Uzaktan Çek) HEM `events.jsonl`
  (yerel — owner kimlik olayı round-trip beklemeden) okur + dedup (aynı isim e-postalı+e-postasız tek kez).
  **SINK SINIRI + ÇÖZÜM (KANITLANDI):** telemetri sink'i (Apps Script/Sheet) yalnız bilinen sütunları saklar →
  `eposta` alanını DÜŞÜRÜR (pull'da `eposta` hep None; `baglam` bile sabit `{proje,dokuman}` şemasıyla döner).
  Bu yüzden `kimlik_bildir` e-postayı, sink'in AYNEN koruduğu **`analist` alanına `'Ad <eposta>'` biçiminde
  GÖMER**; `analistler_listesi` (`_ANALIST_EPOSTA_DESEN`) geri ayrıştırır. kimlik olayı istatistikten HARİÇ
  olduğundan Kullanım Raporu kirlenmez, Apps Script'e DOKUNMAYA GEREK YOK. Analistlerin roster'da e-POSTALI
  görünmesi için: (1) bu gömme-fix'li sürümde Ayarlar→Kaydet → (2) owner Uzaktan Çek → Yetki Yenile.
  Honor-system. Test: `tests/test_roller.py`.
  Yeni gizlenebilir ekran/aksiyon → `GIZLENEBILIR_KATALOG` (app.py). **Owner konsolu (Kullanım Raporu +
  Yetki ekranları) — kilit `.env`'de DEĞİL, gitignore'lu YEREL DOSYADA:** `_owner_konsol_aktif()` yalnız
  `reference/owner_konsol.json` (`{"owner_konsol": true}`) okur — AUTH-off app-sahibi işareti (`_super_owner_mi`'nin
  temeli). **OKUMA/YAZMA ayrımı:** `_usage_yetkili_mi()`=`_etkin_rol()=="owner"` (Kullanım OKUMA — owner rolü yeter) ·
  `_yetki_paneli_mi()`=`_super_owner_mi()` (Yetki YÖNETİMİ — yalnız app-sahibi). **Ekip verisi ÇEKME — SUNUCU-TARAFI E-POSTA KAPISI (birincil):**
  `uzaktan_cek` istemcide SIR TUTMAZ → kullanıcının şirket e-postasını (`analist_eposta_oku`) `?email=` ile sink'e
  geçer; **Apps Script yalnız OWNER e-posta listesindekilere veri döndürür** → anahtar dağıtımı YOK (güncelleme ile
  otomatik), yalnız owner okur (sunucu-taraf zorlama). Owner e-posta listesi Google Sheet'te bir tab'da tutulur
  (app-sahibi ekler). **Geri uyum:** okuma anahtarı (env `USAGE_SINK_KEY` VEYA yerel `reference/usage_sink.json`,
  gitignore/0600) varsa `?read=<key>` de gönderilir → eski Apps Script (e-posta kapısı eklenmemiş) owner'da çalışır.
  `telemetri._sink_key()` env+dosyayı okur; `GET/POST /api/usage/sink-key` (owner rolü) opsiyonel/eski yöntem. UI:
  Kullanım Raporu açılınca ekip verisi OTOMATİK çekilir (`_kuAutoPullYapildi`, anahtar GEREKMEZ); "Okuma anahtarı"
  alanı opsiyonel (eski yöntem). Yetkisizde çekme `⚠ e-postanız owner listesinde değil` mesajı döner (başlıkta kalıcı).
- **Task analizi SUNUCU DEPOSU + EĞİTİM TOPLAMA (Jira'sız da — `skills/gorev_deposu.py`):** Üretilen her Task
  analizi (`_adim_isle` başarı → `app._gorev_egitim_topla`) **(C)** `output/gorev-analizleri/<key>.json`'a yazılır
  (kalıcı; restart/yenileme kurtarması; **30 gün sonra `prune()` ile otomatik silinir**, `SAKLAMA_GUN`) **VE (A)**
  few-shot havuzuna yakalanır — **analist Jira'ya YAZMASA da** (kopyala-yapıştır kendi task'ını açsa da) analiz
  toplanır. **(B)** Task modalında **"Eğitime Ekle"** (`jgEgitimeEkle` → `POST /api/jira/gorev/egitime-ekle`) editördeki
  NİHAİ/düzenlenmiş içeriği havuza+depoya yazar. **KURTARMA:** içerik bellekte yoksa `jgIcerikJiradanCek` ÖNCE sunucu
  deposu (`GET /api/jira/gorev/analiz-kayit`), yoksa Jira açıklaması (`/getir`). `formatla` modu toplanmaz (eğitim
  değeri yok). **Per-task dedup:** `ornek_havuzu._ayni_key_temizle` aynı `jira_key`'in eski yerel örneğini siler →
  task başına EN GÜNCEL tek örnek (havuz şişmesin; owner yine kürasyonla siler).
  **Anahtar = UI entry anahtarı:** FE+BE ayrı analizde BE=`<key>`, FE=`<key>::FE` (depo + örnek `jira_key`) →
  dedup katman başına (FE, BE örneğini SİLMEZ) + kurtarma (`/analiz-kayit`) aynı anahtarla bulur; "Eğitime Ekle" de
  entry anahtarını gönderir (gerçek key'e çözmez). Test: `tests/test_gorev_egitim.py` (sink MOCK/0-token).
- **Onaylı Analiz Örnek Havuzu (few-shot — ORTAK EĞİTİM, `skills/ornek_havuzu.py`):** Analist bir analizi
  ONAYLAYINCA (`/api/approve` süreç · `/api/approve-teknik(-no-jira)` teknik → `app._ornek_yakala`) **VEYA bir
  görev analizini JİRA'YA YAZINCA** (`/api/jira/gorev/guncelle` · `/api/jira/gorev/fe-be-olustur` → `app._ornek_yakala_md`,
  tip='teknik') **VEYA Task analizi tamamlanınca (otomatik)** kaliteli çıktı bir "örnek" olur (hepsi arka plan, best-effort, akışı bloklamaz): (1) YEREL
  `reference/ornekler/<tip>_<id>.json` (gitignore), (2) merkezi sink'e `olay='ornek'` + İÇERİK push (`ornek_kaydet`
  → `_sink_push`; **analiz içeriğini merkeze taşır — app-sahibi bilinçli kararı**). `ornekleri_cek()` (günlük oto-sync
  + boot + `POST /api/ornekler/cek`) sink'ten `?ornekler=1&email=<şirket domaini>` ile **TÜM ekip örneklerini** yerel
  havuza indirir → ortak öğrenme. **ÖRNEĞE YÖNETİCİ ÖZETİ GİRMEZ** (`_temizle` → `yonetici_ozetini_cikar`): özetli
  örnekler modele stil olarak 'kendi özetini yaz'ı öğretti → analizde ÇİFT özet (regresyon). Ayrıca `yonetici_ozeti_olustur`
  modelin yazdığı özet maddelerini (`_model_ozet_maddeleri`) bizim deterministik sayaçlarla BİRLEŞTİRİR; süreç/teknik/görev
  çağıranlar gövdeyi `yonetici_ozetini_cikar` (TÜM blokları siler) ile temizleyip başa TEK özet koyar. Test:
  `tests/test_yonetici_ozeti.py`. **Few-shot:** `ornek_bloklari(sorgu, tip, n=2)` BM25 ile EN ALAKALI 2 örneği
  **süreç + teknik + GÖREV analizine** ("ONAYLI ÖRNEK — stil/derinlik referansı") enjekte eder (`surec_analizi_yap`
  /`teknik_analiz_yap`/`gorev_analiz_et`). `[K:]` temizlenir; örnek ≤45k (Sheet hücre limiti); havuz ≤80 (en yeni).
  Kürasyon/görünürlük: `GET /api/ornekler` (owner liste) · `GET /api/ornekler/durum` (owner — havuz adedi+tip+son çekim,
  `ornek_havuzu.durum`; `.durum.json` meta, `_oku_hepsi`/`_buda` nokta-dosyayı atlar) · `POST /api/ornekler/sil`. UI:
  Kullanım Raporu'nda **"Ortak Eğitim Havuzu"** paneli (`ornekDurumYukle`/`ornekCek` — adet + son çekim + "Şimdi Çek"
  + "Teşhis" `GET /api/ornekler/tani` ham sink yanıtı + '0 çekildi' nedeni). **ESKİ İŞLERİ KURTARMA:** (Yol 1) yerel
  örnekleri merkeze taşı — `ornekleri_paylas(mevcut_idler)` (`POST /api/ornekler/paylas` + `ornekleri_cek` içinde
  OTOMATİK: çekilen-id'de olmayan yerel örnekleri re-push → her analistin günlük sync'i havuzu birleştirir, sink
  id-dedup'lar). (Yol 2) `jira_gorevleri.jira_gecmis_import(projeler, gun, limit)` (`POST /api/ornekler/jira-import`
  arka plan + `/durum`): JQL ile geçmiş task açıklamalarından `_agent_analiz_ayikla` (marker '🤖' sonrası / analiz-şablonu
  sinyalli uzun gövde; junk eler) agent analizini ayıklayıp `ornek_kaydet`'e verir. UI: panelde "Jira'dan İçe Aktar" (proje+gün).
  **SUNUCU TARAFI (KRİTİK — unblock):** merkezi paylaşımın çalışması için Google Apps Script'te **'Ornekler' sekmesi
  (POST olay=='ornek' içerikle saklar, id-dedup) + GET `?ornekler=1` (şirket-domaini VEYA okuma-anahtarı kapısı → tüm
  analistler çeker)** gerekir — TAM KOD + deploy adımları `docs/telemetri-apps-script.md`'de (owner bir kez yapıştırır,
  Web App URL değişmez). Deploy edilene kadar push çalışır ama pull boş döner → YEREL few-shot (herkesin kendi işi)
  yine çalışır; ortak paylaşım deploy sonrası açılır. Test: `smoke_test` (liste/sil/durum deterministik uçlar). Eski `OWNER_KONSOL`/`YETKI_PANELI`/`USAGE_DASHBOARD` env bayrakları **ARTIK OKUNMAZ** (analiste
  kopyalanan owner `.env`'i bu ekranları açıyordu — kapatıldı). Dosya git'e gitmez, `.env` paylaşımıyla
  taşınmaz, `.example`'dan **false** seed edilir (`_runtime_config_seed`) → güncelleme sonrası owner
  HARİCİNDEKİ tüm agent'larda KAPALI. Owner kendi makinesinde dosyayı `true` yapar (tek seferlik; UI'da
  açığa çıkmaz). `auth/me.usage_admin`/`.yetki_admin` → `#nav-kullanim`/`#nav-yetki`; endpoint'ler
  `usage_gerekli`/`yetki_gerekli` (403). Kendi makinesine kuran analistin ETKİN rolü **atanmış rolüdür** (varsayılan
  'analist' — `_etkin_rol` `_owner_mi`'ye DEĞİL roller.json'a bakar) → owner-konsol işareti YOKKEN + owner rolü ATANMAMIŞKEN
  bu ekranları GÖRMEZ. Owner rolü atanınca (Yetki ekranı) GÖRÜR (yukarıdaki "Owner-console = ETKİN rol").
  **Otomatik güncelleme (2.5):** boot'ta `_oto_guncelleme_baslat()` — iş yokken `pull --ff-only` + restart;
  dirty tree / push edilmemiş commit varsa yalnız bildirir. `.env` `AUTO_UPDATE=false` kapatır,
  `AUTO_UPDATE_INTERVAL` (sn). Banner: `screens/_guncelleme.html`. `/api/update` elle akış aynen durur.
  **Referans oto-sync (günlük):** boot'ta `_referans_oto_sync_baslat()` → `_referans_oto_sync_dongusu`
  (saatlik kontrol) → **agent ilk aktif olduğunda + günde bir kez** Confluence/Jira + **servis Swagger'larını**
  çeker (`_referans_sync_calistir`, elle "Güncelle" butonu = `/api/sources/sync` ile ORTAK gövde). Bugün zaten
  sync olduysa (`sources.json last_sync` tarihi bugün → `_bugun_referans_sync_yapildi_mi`) ATLAR; iş sürüyor
  (`_mesgul_mu`) / sync çalışıyor → erteler. **Confluence/Jira `JIRA_CLOUD_ID` (OAuth) gerektirir** (yoksa uyarıyla
  atlanır); **servis Swagger'ları Cloud ID GEREKTİRMEZ** → yalnız servis varsa da sync çalışır. Saatlik kontrol
  gün-değişimi + sonradan kaynak/bağlantı ekleme durumunu yakalar. `.env` `AUTO_REF_SYNC=false` kapatır.
  **Servis Swagger (BFF/OpenAPI → `reference/services/`):** `/api/reference/fetch-be {name,url,auth?}` →
  `_swagger_spec_cek` (swagger-ui HTML'inden `/v3/api-docs` vb. çözer, OpenAPI doğrular) → `services/<name>.json`
  YAZAR **ve `sources.json` `services[]` listesine upsert eder** (`_servis_kaydet`) → günlük oto-sync onu tazeler
  (`_servisleri_sync_et`, best-effort: erişilemezse mevcut spec korunur). `DELETE /api/reference/services/<name>`
  (`_servis_sil`) kayıt + dosyayı siler. **EKİBE YAYIN (owner→analist):** `reference/servis_varsayilan.json`
  (TRACKED — owner'ın yayınladığı BFF `{name,url}` listesi, **auth YOK**) boot'ta yerel `sources.json`
  services[]'e merge edilir (`_servis_varsayilanlari_birlestir`: eksik olanı ekler, mevcut/auth'lu kaydı EZMEZ)
  → analistler URL'leri tek tek girmez, güncelleme+restart ile otomatik alır; yalnız gerekiyorsa auth token'ı
  yerel girer. UI: Referanslar → **tek birleşik servis listesi** (`ref-list-services`; URL + endpoint + Sil→
  `deleteBeService` = kayıt+dosya) + "Swagger URL ile Ekle" formu (eski ayrı `#be-service-list` KALDIRILDI —
  çoklama gitti). **Dosya listeleri katlanır** (`renderRefList` → `<details>`; >8 dosyada varsayılan kapalı →
  162+ Confluence sayfası ekranı boğmaz). NOT: iç ağ (`*.sanstech.dev`) adresleri **agent'ın çalıştığı
  makineden** erişilebilir olmalı (VPN/auth); auth token'ı `sources.json`'da (gitignore) yerelde, expire olabilir.
  **2.6:** Sistem Sağlığı `/api/saglik` + `screens/saglik.html`; komut paleti ⌘K `screens/_palet.html`.
  **Faz 3 — rol-duyarlı pano + disk temizliği:** `GET /api/pano` (herkes) → Ana Sayfa "Sıradaki iş" kartları
  (`_panoIs`: bekleyen onay adımı + "Onay adımına git" · açık/kritik soru · bekleyen revizyon · çalışan iş);
  onay kapılarında **karar bağlamı** satırı (`_onayBaglamYukle` → `#onay-baglam-surec/teknik`, 15 sn throttle).
  Sağlık kartları (owner): **Sürüm · AI/Kota · Güncelleme · İş akışı** (sadeleştirildi). **NOT (UI sadeleştirme):**
  "Veri kaynakları", "Disk" ve "Disk temizlik" kartları panodan KALDIRILDI (analiste gereksiz sistem gürültüsü;
  lokal disk kapasitesi göstermeye gerek yok, loglar Güncelleme ekranında; disk temizliği arka planda otomatik).
  **Backend duruyor (sessiz bakım):** `skills/disk_temizlik.py` (0 token; `plan()` kuru / `uygula()`;
  yalnız yeniden-üretilebilir/arşiv dosyaları — `output/ input/ logs/usage/` ve referans kaynakları ASLA) +
  `_disk_temizlik_dongusu` zamanlayıcı (`DISK_TEMIZLIK=true`, `DISK_TEMIZLIK_ARALIK=86400`; iş varken erteler).
  Endpoint'ler `/api/disk/durum` (GET) · `/api/disk/temizle` (POST, meşgulse 409) — artık UI'dan çağrılmıyor. Durum `logs/disk-temizlik-durum.json`.
  **Task Analizi / test düzeltmeleri (özet):** görev analizi akışı — JARVIS reaktör, ilişkili FE/BE **seçim paneli** (`_jgSecimGoster`), **gömülü** panel (`#jg-preview-card.jg-inline`), arka plan iş (`_gorev_is_calistir`) + **paralel** (ThreadPoolExecutor, `GOREV_PARALEL`), açık soru **yakınsaması** (`_gorev_acik_sorular_uret onceki_sorular`), **gerçek Durdur** (killpg).
  **BFF KEŞFİ (CRUD gözlemi — `skills/bff_kesif.py`; owner isteri: analist elle kayıt açıp güncelleyip silmesin):** Task
  Analizi'nde analizden ÖNCE agent hedef ekranda KENDİSİ liste → OLUŞTUR (`AI-TEST-<damga>`, kayıt KALIR) → doğrulama
  hatası (1 kez) → GÜNCELLE (kalır) → SİL (AYRI ikinci kayıt) → diğer aksiyonlar (yalnız kendi kaydı; geri alınamaz
  olanlar HARİÇ) → filtre/sayfalama yapar, her adımda method/path/payload/response/status yakalar → **BFF sözleşme
  raporu** `reference/live-app/bff/<anahtar>.md` (+`.json` meta; anahtar = hedef URL + ekran tarifi). **7 gün önbellek**
  (`ONBELLEK_GUN`; `taze_mi`): aynı ekrana gelen task'larda CRUD tekrarlanmaz. `_adim_isle` (analiz / fe-be-ayir): rapor
  yok/eski + `live_app_gorev.bff_otomatik` (vars. AÇIK; Task ekranı ayar kutusu) → `kesfet` → `rapor_blogu` →
  `gorev_analiz_et(bff_rapor=…)` (stable blok, canlı görevden önce; FE+BE ikisine de). Ekran bazlı işte (`canli_hedef`)
  miras `live_app` ANA adresi + ekran tarifi ('surec' kapsamı), yoksa `live_app_gorev` ('gorev'). **"BFF Keşfi (CRUD)"**
  butonu → iş modu `bff-kesif` (her zaman yeniden gözler; sonuç `sonuc.bff` → `_jgBffGoster` "Raporu gör"); eğitim
  havuzuna girmez. `/is/durum.aktif_not` → işlem başlığında "BFF keşfi — ekranda CRUD gözlemi". `reference/live-app/`
  RAG corpus'unda olduğundan raporlar TÜM analizlere referans olarak da girer. `<bff_rapor>` bloğu yoksa kaydedilmez;
  CREATE/servis bölümü eksikse `ok=False` (taze sayılmaz → otomatik tekrar). Test: `tests/test_bff_kesif.py` (AI enjekte, 0 token).
  **JİRA'YA GİDEN TASK GÖVDESİ — TEK TEMİZLEME KAPISI (`base.jira_icin_temizle`, owner geri bildirimi 2026-10-16: 'task'ta olmaması gereken bilgiler Jira'ya gidiyor, elle düzeltiyoruz'):** TÜM Jira yazım yolları (`gorev_jiraya_yaz` gövde · `gorev_fe_be_task_olustur` FE · `_analiz_adf` yeni task · köprü `_govdeye_yaz`) bu fonksiyondan geçer: Yönetici Özeti + Canlı Gözlem Kapsamı + `<!-- RAG: … -->` HTML yorumu + `[K:]` etiketleri (backtick'li `` `[K: …]` `` biçimi dahil — eskiden boş `` `` `` kalıyordu) + **kaynak alıntısı cümleleri** ('Analist notu bunu doğrular: "…"', 'Confluence: "…"', tamamı alıntı olan `- **… kaynakta tanımlı:** "…"` maddesi) + 'Confluence'a göre' öneki + **meta-gerekçe** ('… yaklaşımına kıyasla en doğrudan çözümdür', '… kontrolü dışıdır' parantezi) + boş kalan madde + **atlanan bölümler sonrası ardışık numaralama** (1,2,3,7,11 → 1…5; `### N.M` alt başlıkları ve `bkz. N.M`/`(N.M)` atıfları aynı haritayla; numarasız başlık dokunulmaz). Analiz dosyası/ekran DEĞİŞMEZ, yalnız Jira kopyası. Prompt tarafı (`gorev_teknik_analiz` '# JİRA TASK DİLİ'): kaynak alıntısı / yaklaşım savunması / hedge parantezi / başka task'ı kanıt diye anlatma YASAK — kaynak yalnız `[K:]` etiketiyle. Test: `tests/test_jira_temizle.py` (sentetik örnek, 0 token).
  **CANLI UYGULAMA GİRİŞ KAPISI (`skills/canli_giris.py` — owner: 'URL'e giriş yapılmadıysa uyar ve analizi başlatma; URL yoksa gözlemsiz analiz bilgisi ver, öyle başla'):** Task Analizi'nde canlı gözlemli iş modları (`_JG_CANLI_MODLAR`: analiz · fe-be-ayir · bff-kesif · kabul-kontrol) `_jgIsBaslat` içinde `_jgCanliKapi` kapısından geçer: `GET /api/live-app/giris-durum?kapsam=gorev|surec` (ekran bazlı adım `canli_hedef` → 'surec' = Süreç'in miras hedefi) → hedef YOKSA toast 'canlı gözlem YAPILMADAN üretilecek' + başla; hedef VAR ve taze başarılı sonuç yoksa `POST /api/live-app/giris-test {kapsam}` (arka plan iş `_giris_isler`, `GET …/giris-test/durum`) → 1 CLI/Playwright giriş denemesi (`canli_giris.test_et`: ana adres + kayıtlı hesap, `<giris_sonuc>`) → başarılıysa analiz başlar; başarısızsa panelde ⛔ neden + 'Girişi tekrar dene ve başlat' (`jgCanliTekrar`, bekleyen adımlar `_jgBekleyenBaslat`) + 'Ayarlara git'; ANALİZ BAŞLAMAZ. Sonuç `output/.giris-durum-<kapsam>.json`'da İMZALI (URL+kullanıcı+şifre sha1) ve `GIRIS_TEST_GECERLILIK` (vars. 3600 sn) boyunca taze → her analizde tekrar denenmez; Bağlam Filtresi'nde URL/şifre değişince otomatik geçersiz. Task ekranı canlı-app durum satırında **'Girişi Doğrula'** düğmesi + son giriş durumu (`_jgGirisDurumGoster`). İnteraktif Analiz 'Girişi Test Et' AYNI çekirdeği kullanır (`sohbet_analiz.giris_testi` → `test_et('surec')`) → sonuç paylaşılır. `_arka_plan_isleri_calisiyor` giriş işini de görür. Test: `tests/test_canli_giris.py` + smoke (AI MOCK, 0 token).
  **AÇIK SORU ÖZ-ÇÖZÜMLEME (`skills/soru_cozumleme.py` — owner: 'bu soruları referanslardan ve canlı gözlemden agent çözemez mi?'):** `gorev_analiz_et` açık soruları ürettikten SONRA (Aşama 2b) her soruyu analist görmeden agent araştırır: (1) 0-token kanıt — sorunun metniyle referans corpus'unda BM25 (`_ref_dokuman_metinleri` + `retrieval.en_alakali_corpus`, soru başına ~7k), sorudaki endpoint/alan adları (`_adaylar`: `/path|alt` ayrımı, son segment, camelCase/snake, backtick) için `degisiklik_etkisi.tuketici_tara`, Kod Kaynağı bağlıysa `kod_kaynagi.ara`; (2) TEK AI çağrısı (`<soru_cozum>` JSON): `cevaplandi|kismi|karar_gerekli` + kısa cevap + `[K:]` kanıt + `gozlem_gerekli/gozlem_adimi`; (3) gözlem gereken ve cevaplanmamış sorular için TEK odaklı canlı tur (`live_app_gorev`, yoksa `live_app` ANA adresi; `<gozlem_cozum>`; 'cevaplandi' → durum yükselir, bulgu+kanıt birleşir; hata yutulur); (4) soru bloğuna `- Agent durumu / Agent cevabı / Agent kanıtı / Agent gözlemi` satırları eklenir (eski satırlar yenilenir, çözümlü blok atlanır → cevap turunda idempotent). **(5) OTOMATİK İŞLEME (owner 2026-10-19: 'cevabı bulduysa neden analize işlemedi — ekstra süre/token'):** `cevaplandi` sorular `cozulenleri_ayir` ile ayrılır → `gorev_analiz_duzelt(gorev, gövde, uygulama_talimati)` TEK ucuz hedefli düzeltme (referans/gözlem YOK; `_rag_yorum_ayir` RAG yorumunu gövdeden ayırıp geri koyar; çıktı gövdenin %50'sinden kısaysa RED) → cevaplar ilgili bölümlere işlenir, `[K: ❓ Belirsiz]` kalkar; bu sorular listeden DÜŞER ve `## 🤖 Agent'ın çözüp analize işlediği sorular` şeffaflık bölümü olarak eklenir (UI `_jgCozulenBolumu` katlanmış yeşil kutu, 'onay gerekmez'; parser Q- başlığı olmadığı için saymaz → ZORUNLU kapısına takılmaz). Yalnız `kismi` (kutu ön-dolu) + `karar_gerekli` (boş + agent notu) analiste kalır. Düzeltme hata verirse eski davranış (kutu ön-dolu). `SORU_COZUMLEME_UYGULA=onay` → otomatik işleme kapalı (eski: 'Cevapları İşle' = TAM yeniden üretim, pahalı). UI `_jgSorulariAyristir` Agent alanlarını okur → `_jgSorulariRender` kalan sorularda rozet `🤖 agent kısmen buldu / kararınız gerekli` + özet bandı; analist düzeltir → 'Cevapları İşle' aynı akış. Köprü yorumu aynı md'yi yazdığı için agent satırları Jira'da da görünür. Kapatma: `SORU_COZUMLEME=false` / `HIZLI_MOD`. Hata → orijinal sorular. Test: `tests/test_soru_cozumleme.py` (AI/retrieval/tüketici MOCK, 0 token).
  **ÇIKTIYI İŞ BOYUTUNA GÖRE ÖLÇEKLE (hata/basit iş = KISA):** `gorev_analiz_et` `_hata_gorev_mi(gorev)` (issuetype Bug/Hata VEYA başlıkta hata/fix/çalışmıyor/düzelt… sinyali) ise prompt'a **"ÇIKTI MODU: HATA/BASİT İŞ — KISA-NET"** direktifi enjekte eder → yalnız `## Sorun` + `## Çözüm` (+gerekirse `## Kabul Kriterleri`); 11-bölüm şablonu, gereksiz servis/endpoint/DB dökümü, arka plan, "şöyle de yapılabilir" ÖNERİLERİ YAZILMAZ. Amaç: küçük iş task'ta koca iş gibi durmasın, geliştirici 20 sn'de ne yapacağını anlasın. Ek olarak `gorev_teknik_analiz` promptuna (base.py) genel "boyuta göre ölçekle + hata ise Sorun+Çözüm yeter" kuralı eklendi. `gorev_analiz_et` tüm task-bazlı yolları kapsar (Task Analizi · Jira Köprüsü · FE/BE ayrı).
  **TEK TASK → FE+BE AYRI ANALİZ (Option A — aynı içeriğin 2 taskta kopyalanması sorununun çözümü):** bir görev hem FE hem BE işi içeriyorsa "FE+BE Ayrı" (`jgFeBeAyir` → job `mode:'fe-be-ayir'`) → `gorev_fe_be_analiz`: ÖNCE `gorev_analiz_et(katman='be')` (sözleşmeyi tanımlar), SONRA `gorev_analiz_et(katman='fe', iliskili=[BE sözleşmesi])` → **iki AYRI katman-özel içerik** (FE, BE'nin iç işini tekrarlamaz; yalnız arayüz sözleşmesi ortak). İş sonucu `sonuclar[key]={fe_be:{be,fe}}` → UI iki switcher entry (BE=orijinal · FE=`key::FE` "yeni") + geçişte editör içeriği VE açık soru cevapları korunur (`_jgSonucGoster` geçiş öncesi `_jgCevaplariTopla()` ile `entry.cevaplar`'a kaydeder, `_jgSorulariRender(md, cevaplar)` geri yükler → iki iş için cevapları aynı anda girip işleyebilirsin). **FE entry anahtarı SENTETİKTİR (`key::FE`, Jira'da YOK)** → `jgCevaplariIsle`/`jgAnalizDuzelt` backend'e giderken `_jgGorevCoz`/`_jgGercekKey` ile GERÇEK göreve (feBeKaynak) çözer (yoksa `gorev_getir("...::FE")` → "Görev okunamadı"); routing için sentetik key korunur (sonuç FE entry'sine döner). **Set SAYFA YENİLEMESİNE DAYANIKLI:** `_jgAnalizSeti`+aktif key `localStorage['jg-analiz-seti']`'ye yazılır (`_jgSetKaydet` — `_jgSonucGoster`/poll-bitiş/`beforeunload`), boot'ta `_jgSetYukle` geri yükler; çalışan iş yoksa `_jgReattach` "✓ Önceki analiz hazır — Göster" chip'i gösterir (`_jgChipGoster` paneli doldurur). 24s'ten eski set atılır; yeni analiz (temizle) ve panel kapanışı kalıcı seti temizler. **VERİ KAYBI KORUMASI:** tüm editör→set kaydetme noktaları `_jgEditorKaydet(key)` kullanır — BOŞ editör ("İçerik yükleniyor" hâli) DOLU markdown'ı ASLA ezmez (güncelleme/yenileme sonrası analiz silinmesini önler). **KURTARMA:** içerik bellekte yoksa `_jgSonucGoster` "Jira'dan içeriği çek" sunar → `GET /api/jira/gorev/getir?key=X` (`gorev_getir`) task açıklamasını editöre yükler (analiz Jira'ya yazıldıysa geri gelir; `jgIcerikJiradanCek`). Onay (`jgFeBeOnayla` → `POST /api/jira/gorev/fe-be-olustur` → `gorev_fe_be_task_olustur`): **BE analizi ORİJİNAL task'a yazılır** (başlık `BE - ` önekli), **FE analizi YENİ Task açılır** (`FE - `, `_issue_olustur`), **BE→FE Blocks bağı** (`_blocks_bagla`+`_blocks_link_tipi`). Aynı `_katman_prefix`/temizleyiciler (`yonetici_ozetini_cikar`/`canli_gozlem_kapsamini_cikar`/`kanit_etiketlerini_temizle`). Ayrı FE/BE **Jira task'ı** zaten varsa eski `_jgSecimGoster` yolu (her biri kendi katmanına göre) korunur — bu yeni yol tek task'ın içindeki FE+BE içindir. Ayrıca: soru mezar-taşı, `/api/oturum` `aktif` bayrağı, CLI hesabı bilgisi, Jira Ayarları sadeleştirme (site otomatik), UAT key link'leri, bağlam-filtresi kaydı (`_jgFiltreKaydet`). **Tam akış + tüm alt-düzeltmeler → `docs/MIMARI.md` "Task Analizi" + `docs/DEGISIKLIK-ARSIV.md`.**
  **AKSİYON ÇUBUĞU — 3 ADIM (owner 2026-10-19: 'hangisi hangi işi yapıyor belli değil'):** `.jg-modal-aksiyon.jg-aksiyon-gruplu` → `#jg-ak-iyilestir` (1 · Analizi iyileştir: Düzelt kutusu · BFF Keşfi · Akışı Kapat) → `#jg-ak-jira` (2 · Jira'ya aktar, ikisinden biri: Onayla = BU task'ın açıklaması · Yeni Task Aç = yeni task, bu task'a dokunmaz · Ekran Mockup'ı = isteğe bağlı ek; katman kutuları burada) → `#jg-ak-sonra` (3 · Sonrası: Kabul Kontrolü · Eğitime Ekle · İptal). Her düğme `.jg-ak-btn` + `.jg-ak-alt` kısa açıklama; TÜM id/onclick'ler korundu. Yeni Task Aç proje listesi: `_agent_jira_projeleri` sırası = Jira Köprüsü çalışma projeleri (`jira_kopru.json` projeler — ekip varsayılanı MBSTRADE) → ANA proje (`JIRA_PROJECT_KEY`) → kalanlar alfabetik.
  **KATMAN SEÇİMLİ JİRA YAZIMI (owner isteri 2026-10-16: 'bazen yalnız FE ya da yalnız BE task'ı açabilmeliyim'):** FE+BE setinde onay satırında iki kutu `jg-kat-be` ('BE → <kaynak>'a yaz') / `jg-kat-fe` ('FE → yeni task aç'); varsayılan = bakılan sekmenin katmanı, agent `**Bu katmanda iş:** YOK` dediyse o katman işaretsiz (`isVar`, not 'agent: BE/FE tarafında iş yok'), daha önce yazılan katman işaretsiz (`entry.jiraYazildi {be, fe:KEY}`, sette kalıcı). Düğme metni seçime göre (`_jgKatmanEtiketGuncelle`: 'yalnız FE task'ı aç' / 'yalnız BE'yi … yaz' / 'BE'yi yaz + FE task'ı aç'). `POST /api/jira/gorev/fe-be-olustur {…, katmanlar:['be','fe']}` → `gorev_fe_be_task_olustur(katmanlar)`: 'be' → orijinal 'BE - ' ile güncellenir · 'fe' → yeni 'FE - ' task · ikisi → BE→FE Blocks · YALNIZ FE → yeni task kaynak task'a **Relates** (Blocks yok) · yalnız BE → task açılmaz; yalnız seçilen katmanlar few-shot'a. Kısmi yazım sonrası diğer katman aynı setten sonra yazılabilir (içerik değişince tekrar analiz gerekmez). **Yeni Task Aç** panelinde FE+BE setinde radyo `jg-yt-katman` (BE+FE / Yalnız BE / Yalnız FE) → `mode:'fe-be'|'be'|'fe'` (`gorev_yeni_task_olustur` mode be|fe: tek önekli task + üst/kaynak Relates). **Agent önerisi:** `gorev_analiz_et` katman promptu analizin başına `**Bu katmanda iş:** VAR|YOK — gerekçe` satırını ister; `katman_is_var_mi` parse eder, `gorev_fe_be_analiz` sonucu `is_var` taşır (`_jgSonucGoster`/Yeni Task paneli ön-işaret). Test: `tests/test_katman_secimi.py` (Jira MOCK, 0 token).
  **YENİ TASK AÇ (analiz OK → kaynak task'a dokunmadan ilişkili yeni task):** analiz önizleme modalında **"➕ Yeni Task Aç"** düğmesi (`jgYeniTaskPanelAc`) → gömülü panel (`#jg-yenitask-panel`): **Proje/board dropdown** (`GET /api/jira/projeler` → `_agent_jira_projeleri`: YALNIZ agent'a eklenmiş projeler = sources.json `jira_projects` [Kaynaklar→Senkronla] + `JIRA_PROJECT_KEY` + Jira Köprüsü projeleri — tüm Jira instance'ı DEĞİL; adlar eklenen key'ler için hedefli `project/{key}` ile zenginleştirilir; varsayılan = kaynak task'ın projesi listedeyse o, değilse ana proje/ilk, `_jgProjelerCache`) + **üst öğe** Epic/Story/Task key (opsiyonel, `jgYtUstDogrula` → `GET /api/jira/issue-ozet` tip+başlık doğrular) + başlık (kaynak başlıktan FE-/BE- öneki çıkarılmış). `jgYeniTaskAc` → `POST /api/jira/gorev/yeni-task` → `gorev_yeni_task_olustur`: **hep Task tipinde** (`_proje_bilgi.task_id`; analist sonra tipini değiştirir) yeni task açar, verilen üst öğeye **Relates** ile bağlar (hiyerarşi 'parent' DEĞİL — 'ilişkili' istendi; Task, Story child'ı olamaz) + kaynak analiz task'ına Relates (izlenebilirlik). **FE+BE aktif analizdeyse (`_jgYtFebeSet` → `feBeKaynak`) mode='fe-be' → İKİ yeni task (BE + FE, `_katman_prefix` önekli), ikisi birbirine `Blocks` (yoksa `Relates`) ile bağlanır (ASLA atlanmaz) + her ikisi de üst öğeye Relates.** `fe-be-olustur`'dan FARKI: orada BE **orijinal** task'a yazılır; burada kaynak task'a DOKUNULMAZ, hepsi YENİ task. Analiz değişince/modal kapanınca panel kapanır (`_jgSonucGoster`/`jgPreviewKapat` → `jgYeniTaskKapat`); hata/boş içerikte düğme pasif. Aynı temizleyiciler (`_analiz_adf` → TL;DR/gözlem/`[K:]` çıkar). Test: `smoke_test` (proje/içerik doğrulaması, jira-bağlantı kontrolünden önce).
  **EKRAN MOCKUP'I (Task Analizi → yeni isteye göre HTML mockup — Adım 1):** analiz önizleme modalında **"🎨 Ekran Mockup'ı"** düğmesi (`jgMockupPanelAc`) → gömülü panel (`#jg-mockup-panel`, Yeni Task Aç deseni): analist **yeni iste / ekran açıklaması** yazar → `POST /api/jira/gorev/mockup {iste, analiz, baslik, hedef_tarif}` → ARKA PLAN iş (`_gorev_mockup_isler`, `{job_id}`) → `GET /api/jira/gorev/mockup/durum/<job_id>` polling (`gecen_sn`/`adim_gecen_sn` + 180sn takılma uyarısı). `skills/html_mockup.gorev_mockup_uret(analiz_md, iste, baslik, hedef_tarif)`: görev analizini + yeni isteyi + **Task akışının KENDİ `live_app_gorev` hedefini** (`canli_uygulama_baglami_hazirla(gorev=True, hedef_tarif=iste)`, kapsam="gorev") baz alır → **mevcut uygulamanın tasarım dilini birebir koruyan** çalışan HTML üretir (`output/gorev-mockup.html`, Süreç `mockup.html`'inden AYRI). Canlı hedef yoksa jenerik fallback (`tasarim_kaynagi: "jenerik"` → UI "Bağlam Filtresi → Task canlı uygulama hedefini gir" uyarısı). Önizleme: tam-ekran sandbox'lı iframe (`#gorev-mockup-modal`/`#gorev-mockup-iframe`, `allow-scripts allow-forms`, `srcdoc` — `allow-same-origin` YOK). **Analizden AYRI düzeltme:** `POST /api/jira/gorev/mockup/duzelt {talimat}` → `gorev_mockup_duzelt` yalnız `gorev-mockup.html`'i değiştirir (analize dokunmaz) + `.../geri-al` (yedek `_gorev-mockup.bak.html`). İndir: tarayıcı Blob (`ekran-mockup.html`). `gorev-mockup.html` → `IZIN_VERILEN_CIKTILAR`; store → `_arka_plan_isleri_calisiyor` (restart/kapanma kesmez); kimlik-gate `/api/jira/gorev` öneki; telemetri `mockup` olayı. **Adım 2 — analiz↔mockup bağı (staleness):** mockup hangi entry/analiz/isteye göre üretildiyse izlenir (`_jgMockupEntryKey`/`_jgMockupIste`/`_jgMockupBaseAnaliz`); o entry'nin analizi değişince (job-güdümlü düzelt/cevap → `_jgSonucGoster` içinde `_jgMockupStaleKontrol`; manuel editör düzenlemesi → `#jg-preview-editor` input listener) mockup **"eski"** işaretlenir → panelde **"⚠ Analiz değişti — Mockup'ı güncelle"** (`jgMockupTazele`: AYNI iste + GÜNCEL analizle yeniden üretir). BE/FE aynı gerçek görevin mockup'ını paylaşır (`_jgGercekKey` kıyası). **Adım 3 — Jira'ya EK olarak açma:** `skills/atlassian.atlassian_attach(issue_key, dosya_adi, icerik_bytes, content_type, cloud_id)` (multipart + `X-Atlassian-Token: no-check`; JSON helper'ları attachment yapamaz). `POST /api/jira/gorev/mockup/jira {key, mode, baslik, ust}` → mode=`ek` (varsayılan): `gorev-mockup.html`'i kaynak task'a attachment ekler · mode=`yeni-task`: `gorev_yeni_task_olustur` ile ilişkili "Tasarım - …" Task açıp mockup'ı ona ekler (kaynak task'a dokunmaz). UI: mockup sonuç satırında **"Jira'ya Ekle"** + **"Tasarım Task'ı"** (`jgMockupJira('ek'|'yeni-task')`; stale'se uyarı+onay; `/browse/<key>` link döner). HTML Jira'da inline render EDİLMEZ (kaynak gösterir) → **önce PNG görsel eklenir** (`skills/html_render.html_to_png`: kurulu Google Chrome/Chromium/Edge/Brave `--headless --screenshot`; PNG oluşunca süreç PROCESS GRUBUYLA öldürülür — Chrome updater yüzünden asılı kalmaz; ~1-2 sn; tarayıcı yoksa best-effort False → HTML-only), **sonra HTML** (indirip interaktif açmak için). `gorev-mockup.png` → `IZIN_VERILEN_CIKTILAR`; yanıt `eklenenler`/`gorsel`. **Ek yükleme dayanıklılığı:** her attach AYRI try — `yeni-task`'ta task açıldıysa ek hatası task'ı KAYBETMEZ, kısmi başarı (`attach_ok:false` + gerçek HTTP neden; `atlassian_attach` 4xx/5xx gövdesini yükseltir) döner → UI "Mockup'ı <key>'e tekrar ekle" (`jgMockupEkTekrar`) + "belirli task'a ekle" input'u (`jgMockupEkKeyGonder`) ile mode='ek' retry sunar. `GET /api/jira/gorev/mockup/mevcut` panel açılınca diskteki son mockup'ı yükler (restart/yenileme sonrası sonuç bloğu + Jira'ya ekle etkin). Test: `smoke_test` (boş iste/dosyasız düzelt/bilinmeyen job/boş key doğrulamaları, AI'sız).
  **Ray görünümü (tek kolon adım akışı, geri dönüşlü):** `#surec-ray` (6 adım) / `#brd-ray` (4 adım) — `_RAY` konfig,
  `_rayInit/_rayRender/_rayTasi/_rayUygula/gorunumDegistir` (index.html). Klasik paneller `.gorunum-klasik` (DOM'da
  KORUNUR, `body.gorunum-ray` gizler); aksiyon blokları `surec-act-*`/`brd-act-*` aktif adımın `.ray-body`'sine
  TAŞINIR (kopya DEĞİL → onay/adım sohbeti/prototip sohbeti/Sadece Teknik/Durdur/Jira aynı DOM+fonksiyon). Durum
  makinesine dokunma; `_rayRender` `updateUI` sonunda + `resetWorkflowUI`'de çağrılır. "Klasik görünüm" düğmesi
  (localStorage `gorunum`) blokları orijinal panele geri taşır. Git yedeği: tag `klasik-surec-ekrani-yedek`.
  Yeni aksiyon bloğu eklersen `_RAY[p].nodes`'a da ekle; yeni workflow durumu → `_RAY[p].idx/run/turn`.
  **Faz 4 — analist-dostu hata:** `skills/hatalar.py` (`insanlastir(ham)` — 0 token, regex `_KURALLAR` sıralı:
  durduruldu/cli_limit/cli_oturum/api_key/zaman_asimi/disk/ag/mcp/model/dosya/dokuman/json/alt_surec/bilinmeyen;
  base.py import ETMEZ → run.py/workflow.py'de ucuz). `workflow.ozet()` → `hata_ozet`; UI `_hataKartiHtml`
  (başlık · ne oldu · **Ne yapmalı** · `<details>` teknik iz), toast `_hataBaslik`. Yeni hata türü → `_KURALLAR`'a
  satır ekle (ilk eşleşen kazanır; genel desenleri sona koy).
- **Test (v2):** `venv/bin/python tests/smoke_test.py` (Flask test client, deterministik uçlar) +
  `venv/bin/python tests/test_revizyon.py` + `tests/test_auth_roller.py` (AUTH açık Owner/Analist
  enforcement; env + USERS_PATH geçici) — commit öncesi ruff ile birlikte çalıştır. AI/kota harcamaz.
  Yeni deterministik endpoint → smoke_test'e bir satır ekle. Ayrıca `test_auth_roller.py`, `test_kod_kaynagi.py`,
  `test_jira_kopru.py` (Jira Köprüsü komut→taslak→onay + silent-skip + self-scope + sağlık, offline/0-token),
  `test_bildirim.py` (bildirim kaçış/redaksiyon/no-op), `test_bildirim_akis.py` (analiz bildirim geçiş+dedup),
  `test_sorular.py` (soru defteri oturum-aidiyeti — bayat cevap taşınmaz + aynı-oturum koruma, offline/0-token),
  `test_baglam_jira.py` (bağlam filtresi Jira key'leri yerel export'ta yoksa uzaktan bulkfetch — yalnız eksik, hata yutulur; ağ MOCK/0-token),
  `test_soru_hedefli.py` (soru cevabı hedefli düzeltme yönlendirmesi — süreç/teknik kendine, bölüm bulunamazsa tam üretim; AI MOCK/0-token),
  `test_roller.py` (kullanıcı-bazlı ekran yetkisi — hash/PII'siz, etkin rol/görünürlük, owner sınırı, CRUD; offline/0-token),
  `test_yonetici_ozeti.py` (çift Yönetici Özeti regresyonu — model özeti birleştirme, tümünü çıkarma, few-shot temizliği; offline/0-token),
  `test_sohbet_bff.py` (İnteraktif Analiz BFF keşfi — bff_kesfet/oturum kaydı/sistem mesajı, raporların sohbet+üretime girişi, tazelik, uçlar; AI enjekte/0-token),
  `test_bff_kesif.py` (BFF Keşfi — önbellek/tazelik, plan kuralları, ekran-bazlı vs görev hedefi, blok yoksa kaydetme, analiz motoruna rapor girişi, app modu; AI enjekte/0-token),
  `test_sohbet_ekran.py` (İnteraktif Analiz ekran bazlı iş — gözlemli tur, cevaplanan sorular bağlamı, giriş testi, ekran envanteri/görevleri, iş başlatma + sentetik kayıt korumaları; AI enjekte/0-token),
  `test_sohbet_tazelik.py` (İnteraktif Analiz bayat çıktı tazeliği + ön-söz/iç-konuşma kırpma; offline/0-token),
  `test_kabul_kontrolu.py` (Kabul Kontrolü — liste normalize, karar mantığı [eksik→geri, bildirilmeyen→doğrulanamadı], canlı hedef yok, rapor, köprü komutu, **kriter bazlı toplama + talimat URL + ilgili task + analist rapor yapısı + tur bütçesi/devam/tamamlama turu**; AI enjekte/0-token),
  `test_uat_senkron.py` (UAT Durum Senkronu — plan kuralları, geçiş bulma, rapor modunda Jira'ya yazma YOK, otomatik taşıma + geçmiş, uçlar; Jira MOCK/0-token),
  `test_backlog_analiz.py` (UAT Mutabakat — analiz durumu/takip hunisi/toplam denklemleri/epic kapsam dışı/Excel Özet; Jira MOCK/0-token),
  `test_akis_kapatma.py` (akış kapatma — düzeltme/korumalar/soru blokları/dosya+revizyon/Task/motor bağlantısı; AI enjekte/0-token),
  `test_degisiklik_etkisi.py` (değişiklik sinyali/tüketici taraması/bütünlük kuralları/zorunlu soru/akış bütünlük denetimi + motor bağlantısı; AI MOCK/0-token),
  `test_gorev_egitim.py` (Task analizi depo + eğitim toplama — egitime-ekle, dedup, FE+BE anahtarları; sink MOCK/0-token),
  `test_telemetri_olcum.py` (ekip kota ölçümü — token gömme/çözme, okuma+sink normalize, öncesi/sonrası karşılaştırma; offline/0-token),
  `test_kota_faz23.py` (kota Faz 2+3 — katman→model çözümü + env, katman türetme (model sabiti/açık), önbellek anahtarı katmanlı, yardımcı çağrı noktaları, `gorev_cevap_uygula` hedefli/RAG korunur/yakınsama/ValueError, app iş modu `cevap` hedefli + boş editörde tam üretim; CLI/AI MOCK/0-token),
  `test_gozlem_fazi.py` (kota Faz 0+1 — gözlem fazı rapor/önbellek/yeniden, motorlar tarayıcısız analiz + rapor bloğu, FE+BE tek gözlem, --max-turns + error_max_turns resume, cagri.jsonl + cagri_ozeti, aşama etiketleri; CLI/AI MOCK/0-token),
  `test_katman_secimi.py` (katman seçimli Jira yazımı — yalnız FE/yalnız BE/ikisi, mode be|fe yeni task, 'Bu katmanda iş' parse, uç doğrulamaları; Jira MOCK/0-token),
  `test_live_app_slot.py` (profil havuzu — farklı slot, bırak/yeniden al, bayat kilit devralma, canlı süreç atlama, dolu havuzda bekleme, slot başına MCP config, finally ile serbest bırakma, oturum kopyalama + damga, pgrep tam eşleşme; offline/0-token),
  `test_canli_giris.py` (canlı giriş kapısı — durum/gerekli, imzalı önbellek ve geçerlilik, URL yoksa AI yok, gorev/surec kapsamı, app+UI bağlantısı; AI MOCK/0-token),
  `test_soru_cozumleme.py` (açık soru öz-çözümleme — bloklar/adaylar, sınıflandırma→md, tek canlı tur + durum yükseltme, idempotent, bayraklar, entegrasyon; MOCK/0-token),
  `test_jira_temizle.py` (Jira'ya giden task gövdesi temizliği — HTML yorumu/alıntı/meta-gerekçe/etiket/ardışık numaralama + tüm yazım yolları tek kapı; offline/0-token),
  `test_canli_tekrar.py` (canlı gözlem — prompt sonu zorunlu ilk-eylem direktifi, model araç çağırmazsa otomatik tekrar, neden alanı, kilit temizliği; CLI MOCK/0-token),
  `test_jira_hiyerarsi.py` (hiyerarşi oluşturma KISMİ HATA dayanıklılığı — bir issue reddedilse de kalanlar açılır + hatalar raporlanır; Jira MOCK/0-token).
- **Faz 3.a — Kod kaynağı:** `skills/kod_kaynagi.py` salt-okuma yerel git/dosya arayüzü (yol repo köküne
  hapsedilir; yazma/komut yok). Config `reference/kod_kaynagi.json` (gitignore + `.example` seed, seed listesinde).
  `/api/kod/*` (config owner-only) + `screens/kod.html` (Kaynaklar). Gerçek repo bağlantısı analiste bırakıldı;
  bağlı değilken analiz normal çalışır. Yeni adaptör (MCP/uzak) aynı arayüzü uygular.
- **Faz 3.b — Etki analizi:** `skills/etki_analizi.py` (çıktı varlıkları → kod isabeti) + `/api/etki/<dosya>`.
- **Faz 3.c — Retrieval + MCP:** `skills/retrieval.py` BM25 (`base._keyword_odakli_metin` içinde fallback'li;
  Türkçe-i düzeltmeli). `skills/analiz_mcp.py` Postgres/Jira MCP'yi `claude -p`'ye bağlar (config
  `reference/analiz_mcp.json` gitignore+`.example`+seed; üretilen `.mcp-analiz.json` gitignore; VARSAYILAN
  KAPALI; `_api_cagri_cli`'de canlı-app aktif değilse eklenir). `/api/analiz-mcp` owner (bağlantı maskeli).
- **Jira Köprüsü (Jira'yı web-chat gibi kullan):** `skills/jira_kopru.py` + `_jira_kopru_dongusu` (app.py).
  Analist bir Jira task'ının YORUMUNA `/analyst_agent <komut>` yazar → app **polling** (JQL taraması,
  inbound/webhook YOK — lokal + OAuth) ile bulur, işler, sonucu Jira **yorumu** olarak geri yazar
  (`jira_yorum_ekle`, canonical `atlassian_post` + `markdown_to_adf`). **Yapılandırma (`ayarlar()`):
  öncelik `reference/jira_kopru.json` (git'te İZLENMEZ; `.example`'dan boot'ta `_runtime_config_seed` ile
  seed — analistler `.env` YAZMAZ, güncelleme/pull ile ekip varsayılanını alır) > `.env` (yedek/eski) > kod
  varsayılanı; boş liste/dize "set edilmemiş" sayılır (False korunur). `.example` VARSAYILANI: `aktif:true` +
  `projeler:["MBSTRADE"]` → güncelleme sonrası analistlerde otomatik açık (self-scope ile güvenli).** UI uçları (`/api/jira-kopru/durum|tara|liste|is`) **analist-erişimli** (bridge self-scope ile kendi Jira kimliğine kilitli); owner **Yetki** ekranından `kopru`'yu gizleyebilir → `gorunurluk_kontrol` `/api/jira-kopru` yolunu sunucu tarafında engeller.
  **Komutlar:** `analiz [talimat]` → `_bridge_uret` (→`gorev_getir`+`gorev_analiz_et`) sonucu **task
  GÖVDESİNE (açıklama) yazar** (`_govdeye_yaz`: `## 📌 Orijinal Talep` + orijinal KORUNUR + `## 🤖 Teknik
  Analiz`; tekrar analizde `_orijinal_talep_ayikla` orijinali korur — analiz GİRDİSİ hep orijinal talep,
  `_orijinal_gorev` ile özyineleme önlenir); açık sorular + RAG kelimeleri **yoruma** yazılır. **Jira'ya
  YAZILMAYAN:** Yönetici Özeti + Canlı Gözlem Kapsamı + **`[K: kaynak]` kanıt etiketleri**
  (`kanit_etiketlerini_temizle`, base.py) — etiketler agent çıktısında/UI çipinde durur, Jira'ya sadece
  gerçek task analizi gider; iki yazım sınırında da temizlenir (gövde `gorev_jiraya_yaz` = köprü+ana app,
  yorum `jira_yorum_ekle`). Çıktı+açık sorular
  `son_analiz` önbelleğine (`_ANALIZ_TAZE_DK`=60dk) · `cevap <metin>` → açık sorulara cevap: analizi cevaplarla
  YENİDEN üretir (`onceki_sorular` ile soruları YAKINSAR), gövde güncellenir, kalan sorular yoruma · `düzelt
  <talimat>` → yalnız ilgili kısmı `gorev_analiz_duzelt` ile düzeltir · `güncelle` → son analizi gövdeye yeniden
  yazar (taze varsa 0-token) · `ilişkili-aç` → ilişkili YENİ task **önerir (taslak)** (`_iliskili_task_onerileri`
  AI ≤`_MAX_ILISKILI`=5) → `onayla` UYGULAR (`_issue_olustur`+`jira_issue_link` Relates, aynı proje) · `iptal`/`yardım`.
  **KENDİ KENDİNE YETERLİ bağlam** (`gorev_analiz_et(ekran_baglami=False)`): Jira'dan komut veren birinin
  ekranındaki filtreyi/analist notunu göremez → bridge bunları YOK SAYAR. Bağlam: **(#3)** task'tan çıkarılan
  keyword'lerle RAG (`_task_keywords`→`rag_ctx`→`referans_dosyalari_hazirla(ctx_override)`) · **(#2)** canlı
  gözlem sabit ekran yerine kayıtlı live-app URL'inden türetilen **ANA giriş (base)** + `live_app_auth` login +
  task'tan hedef ekran (`_canli_gorev_baglam`→`canli_uygulama_baglami_hazirla(base_url_override, hedef_tarif)`) ·
  steering `analiz <talimat>`. (Ekran akışları `ekran_baglami=True` ile aynen korunur.) **Korkuluk:** yorum=KOMUT ·
  YENİ task açma yalnız `onayla` sonrası · çift-uygulama önlemi · eşzamanlı `_TUR_LOCK` · döngü koruması (kendi
  `🤖` yanıtı prefiksle başlamaz + işlenen yorum id'leri `output/jira-kopru/durum.json`) · **Yetki (`_etkin_allowlist`):
  elle `JIRA_KOPRU_YAZAR_ALLOWLIST` (yalnız accountId; merkezi/çok-kullanıcılı override) YOKSA SELF-SCOPE —
  agent kendi Jira kimliğine (`myself.accountId`, `_owner_id_cache`) otomatik kilitlenir → per-user kurulumda
  analist yalnız KENDİ komutlarını işler, çakışma yok. Hiçbiri belirlenemezse fail-closed (işlenmez). displayName
  yetkiye sokulmaz.** **YETKİSİZ/entegrasyonsuz yazar → TAM SESSİZLİK** (Jira'ya yanıt YOK, işlenen-id'ye eklenmez;
  yorum düz girdi olarak kalır — agent varlığı sızmaz). UI kanalı **analist-erişimli** (varsayılan görünür;
  owner **Yetki**'den `kopru`'yu gizleyebilir — `GIZLENEBILIR_KATALOG`'a eklendi; `gorunurluk_kontrol`
  sunucu-taraf engel). Eskiden owner-only idi (v3'te açıldı — per-user bridge modeli).
  **Durum göstergesi:** `saglik_guncelle`/`saglik()` (runtime, süreç-içi) → `son_durum`/`liste` `saglik{bagli,son_hata,kontrol}`;
  `kopru.html` "Jira bağlı · son tarama HH:MM" / "⚠ bağlantı yok". Env: `JIRA_KOPRU_PROJELER` (zorunlu) / `_ARALIK` /
  `_PENCERE_DK` / `_KOMUT`. **Agent UI kanalı** (2. kanal):
  `screens/kopru.html` (nav "Jira Köprüsü", **analist-erişimli**; owner Yetki'den gizleyebilir) — açık sorular arayüzde görünür + **tüm işlemler UI'da**
  (analiz · cevap · düzelt · **güncelle** (Task Güncelle) · ilişkili-aç · onayla · iptal → `kopruIs(komut,key)`);
  Jira yorumu ile AYNI beyin (`jira_kopru.ui_komut`→`_komut_uygula`+`jira_yorum_ekle`, `_TUR_LOCK`);
  `GET /api/jira-kopru/liste` + arka plan iş `POST /api/jira-kopru/is`→`GET /api/jira-kopru/is/<id>` (`_kopru_isler`).
  Test: `tests/test_jira_kopru.py` (offline durum-makinesi, 0 token). Tam uç dökümü → `docs/ENDPOINTS.md` "Jira Köprüsü".
  **Ekip/kullanıcı hızlı rehberi + SSS → `docs/JIRA-KULLANIM.md` (`kontrol [URL/odak]` dahil); uygulama-içi kılavuz `KILAVUZ.html`
  §6.7 adım 5 (Task Analizi aksiyonları: FE+BE Ayrı · Yeni Task · BFF Keşfi · Kabul Kontrolü · Akışı Kapat · Mockup · Eğitime Ekle +
  'Jira'ya ne gider' kutusu) · §6.9 (İnteraktif Analiz) · §10 (canlı gözlem rozeti) · §16 (gözlem yapılamadı) · §18 (Jira Köprüsü) + §19 (Bildirimler).**
- **FE/BE düz Task bölme (`skills/jira_fe_be.py` — süreç ekranı onay→Jira):** Süreç→Teknik akışında
  teknik analiz onaylanınca "Evet — FE/BE Task'larını Öner" (`teknikOnaylaFeBe`) → **önizleme modalı**
  (`#febe-modal`) açılır; workflow YALNIZ task'lar açıldıktan sonra bitirilir (auto tek-Task YOK) — iptal
  edilirse teknik-onay adımı korunur (tekrar denenebilir / "Atla"). **PROMPT-ÖNCE, iki durumlu modal
  (`_febeView('prompt'|'preview')`):** açılışta AUTO-SPLIT YOK → önce **PROMPT ekranı** (`#febe-prompt-view`):
  analist "kaç task / nasıl bölünsün" yazar (`#febe-talimat` textarea; ör. "sadece 2 task: 1 FE + 1 BE",
  "ekran bazlı böl", "ödeme ve sipariş olarak ayır"; boş = doğal kırılım) → **"Task'lara Böl"** (`febeBol` →
  `/preview` `talimat` ile). **Önizleme ARKA PLAN işi (uzun AI çağrısı):** `POST /api/jira/fe-be/preview`
  senkron değil — `{job_id}` döner, `febeBol` `GET /api/jira/fe-be/preview/durum/<job_id>`'yi 2 sn'de bir
  polling'ler (client-abort YOK; 10 dk güvenlik tavanı). Eskiden senkron istek 120s `AbortController`'a
  takılıp büyük analizde "Zaman aşımı (120s)" veriyordu (backend biter+cache'lerdi, tekrar deneme çalışırdı).
  `_febe_preview_isler` job store (son 24) + `_febeAktifJob` (iptal/yeniden-böl polling'i geçersiz kılar).
  Sonra **ÖNİZLEME ekranı** (`#febe-preview-view`): `d.plan` özeti + task listesi
  (seç/düzenle) + her satırda **"🔍 Görüntüle"** (`febeGoruntule`) → **tam-sayfa task görüntüleyici**
  (`#task-viewer-modal` / `taskViewerAc`): Jira'ya gidecek TAM gövde (başlık FE-/BE- önekli + şablon
  açıklaması + Kabul Kriterleri) `marked.parse` ile Jira'daki gibi render. Aynı görüntüleyici Epic/Story
  hiyerarşi modalında da (`jiraNodeGoruntule`, `_jiraNodeHTML`'e "Görüntüle" butonu) → TÜM task açma
  ekranlarında ortak tam-içerik önizleme.
  Beğenmezse **"◂ Bölmeyi değiştir"** (`febePromptaDon`) ile prompt ekranına dönüp talimatı
  değiştirir → yeniden böler (yinelemeli). `_gorevler_uret(talimat)` talimatı prompt'a EN YÜKSEK ÖNCELİK
  olarak enjekte eder. Onaylayınca (`febeOnayla`) seçilenler Task olarak açılır. **İkinci giriş noktası —
  Çıktı Dosyaları:** teknik-analiz.md görüntülenirken Jira satırında **"FE/BE Task Aç"** butonu (`jira-febe-btn`
  → `febeModalAc`) aynı prompt-önce akışı açar; yanındaki **"Hiyerarşik (Epic/Story)"** butonu klasik
  `jira_tasks.py` hiyerarşi akışını (alternatif) açar. `febeOnayla`'nın workflow-bitirme çağrısı teknik-onay
  dışındaki durumda 409 döner (yakalanır, no-op) → Çıktı ekranından açmak güvenli. `jira_fe_be_uret` teknik-analiz.md'yi (TL;DR +
  Canlı Gözlem çıkarılmış) AI ile DÜZ FE/BE görev listesine böler (`<fe_be_gorevler>` JSON: her görev
  `{id, katman:FE|BE, summary, description, acceptance_criteria, bagimli_be:[BE-id…]}`). `_gorevleri_normalize`
  katmanı FE/BE'ye indirger (`_katman_indirge`: Frontend→FE, Backend→BE, varsayılan BE) + hayalet bağımlılığı
  (var olmayan BE id) düşürür. Analist seçer/düzenler → `jira_fe_be_olustur`: **tümü görev(Task) tipinde**
  (`_proje_bilgi.task_id`, Epic/Story/Subtask YOK), BE'ler ÖNCE açılır, sonra FE'ler; `bagimli_be` haritasına
  göre **BE→FE Blocks bağı** (`_blocks_bagla`: outwardIssue=BE bloklar, inwardIssue=FE bloklanan; link tipi
  `_blocks_link_tipi` runtime'da doğrulanır, yoksa `link_uyari` ile atlanır). Bağ YALNIZ ikisi de seçilen
  görevler arası (UI + backend çift-filtre). **Task içeriği (KENDİ KENDİNE YETERLİ):** prompt description'ın
  ÖZET değil, geliştiricinin BAŞKA belgeye bakmadan uygulayabileceği GERÇEK teknik detay (BE: endpoint+metod,
  request/response alanları, DB, validasyon, hata kodları; FE: ekran/bileşen, etkileşim, veri kaynağı, UX)
  MARKDOWN olarak yazmasını ister (`MAX_TOKENS_FE_BE`=8000). Task gövdesi `_gorev_govde_adf` ile **markdown→ADF**
  (`markdown_to_adf`; alt başlık/madde/kod render olur, düz paragraf değil) + "### Kabul Kriterleri"; UI önizleme
  panelinde de `marked.parse` ile render (Jira'daki gibi). **ZORUNLU TASK ŞABLONU (tek ortak, FE+BE):** prompt
  description'ı sabit `###` başlıklarla ve BU SIRAYLA yazdırır — Amaç · Kapsam/Kapsam Dışı · Etkilenen
  Endpoint'ler (API) · Ekran/Bileşen Kırılımı · İş Mantığı & Kurallar · Etkileşim & Akış · Veri/DB
  Değişiklikleri · Hata Yönetimi & Boş Durumlar · Rol/Yetki · Bağımlılıklar & Riskler (+ kod tarafı sonda
  "### Kabul Kriterleri" ekler, `acceptance_criteria`'dan). Her başlık teknik analizin ilgili bölümünden
  DOLDURULUR, o görev için içeriksizse başlık ATLANIR; hazır "Jira Task Taslakları" özeti KOPYALANMAZ. **Başlık öneki (TÜM task açma yolları):**
  `jira_tasks._katman_prefix(katman, summary)` → FE görevleri **"FE - …"**, BE **"BE - …"**, FE+BE "FE+BE - …",
  Genel önek yok (idempotent). Uygulanır: FE/BE düz (`jira_fe_be_olustur`), Epic/Story hiyerarşi
  (`jira_hiyerarsi_olustur` story+subtask; UI `jiraHiyerarsiOnayla` `katman` taşır), Jira Köprüsü ilişkili-aç
  (`jira_kopru`) → açılan task'lar başlıktan ayrışır. Endpoint: `POST /api/jira/fe-be/preview` + `/create` (owner-gate
  değil; `_jira_baglanti_eksik` kapısı). Eski tek-monolitik-Task yolu (`jira_agent.main` / `/api/approve-teknik`)
  hâlâ DURUYOR ama süreç ekranı artık FE/BE akışını kullanır. Epic/Story/Subtask hiyerarşi akışı
  (`jira_tasks.py`, `/api/jira/hierarchy/*`) ayrı; **o da AYNI zorunlu şablonu** kullanır (base.py
  `jira_tasks` promptu story/subtask description'ı şablon başlıklarıyla üretir; `jira_hiyerarsi_olustur`
  story+subtask gövdesini ortak `jira_tasks._gorev_govde_adf` = markdown→ADF ile yazar). Test: `smoke_test` (giriş doğrulama +
  normalize + katman). **`bagimli_be` yönü: FE, ihtiyaç duyduğu BE'ye bağımlı (BE 'blocks' FE).**
- **Bildirimler (`skills/bildirim.py` — YEREL masaüstü):** `gonder(baslik, metin[, alt])` → macOS `osascript display
  notification` (0 bağımlılık, 0 token, best-effort — hata YUTAR; `BILDIRIM=false`/macOS-değil → no-op; redaksiyon +
  AppleScript kaçışı; base.py IMPORT ETMEZ). **Analiz yaşam döngüsü:** `app._analiz_bildirim_dongusu` (UI polling'inden
  BAĞIMSIZ arka plan gözlemci) workflow `onay_bekleniyor`/`teknik_onay_bekleniyor`/`hata` durumuna GEÇİŞTE **bir kez**
  (dedup) yerel bildirim — "«doküman» süreç/teknik analizi tamamlandı — N açık soru…". Her analist kendi makinesinde →
  yerel (veri çıkmaz). **Köprü (İstek 2 — hem lokal hem Jira kanalı):** her komut işlenince yerel bildirim
  (`_kopru_komut_bildir` — yorum-kanalı döngüsü steady-state + UI-kanalı `_kopru_is_calistir` ortak); Jira
  bağlantı hatası → bildirim (bir kez); açılış catch-up → çevrimdışı komutlar işlenince özet bildirim.
  Test: `tests/test_bildirim.py` (kaçış/redaksiyon/no-op) + `tests/test_bildirim_akis.py` (analiz geçiş+dedup + köprü komut bildirimi).

## Komutlar
- Kurulum: `bash setup.sh` · Başlat: `./start.sh` (veya Analyst Studio.app)
- Çalışma GUI üzerinden (subprocess `run.py`); ayrı terminal test komutu yok.
- **Backend kod değişince süreç yeniden başlatılmalı** (`use_reloader=False`; sekme kapatıp açmak/sayfa yenilemek Python sürecini yeniden başlatmaz — modüller `sys.modules`'ta cache'li). UI: Güncelleme sekmesi → **"Yeniden Başlat"** (`/api/restart`, koşulsuz). "Güncelle" (`/api/update`) yalnız `git pull` yeni commit çekerse restart eder → yerelde düzenlenen dosyalarda "zaten güncel" deyip restart ETMEZ. **`git pull` hem manuel hem AUTO_UPDATE'de EXPLICIT (`pull --ff-only origin <dal>`, dal = `rev-parse --abbrev-ref HEAD`) — upstream takibine BAĞIMLI DEĞİL; takip bilgisi (ör. history rewrite sonrası) silinse bile "no tracking information" hatası vermez.** Restart mekanizması: `_yeniden_baslat_zamanla()` (app.py) — os.execv DEĞİL (execv dinlenen socket FD'sini devralır → "Address already in use"); mevcut süreç `os._exit` ile kapanır, ayrık yeni süreç ~1.5 sn gecikmeyle aynı komutla başlar. **Frontend (index.html) tek dosya + `TEMPLATES_AUTO_RELOAD=True` → şablon her istekte diskten okunur (restart GEREKMEZ, sayfa yenilemek yeter); ayrıca `index()` `Cache-Control: no-cache/no-store` döner → tarayıcı ASLA bayat SPA kabuğu sunmaz.** Çalışan sürüm doğrulaması: `GET /api/version` (git commit) + sidebar'da `v2.1 · <hash>` damgası → "güncelledim ama eski ekran" durumunda damga eskiyse pull inmemiştir (backend değişikliği ise Yeniden Başlat şart). **IRAKSAMA kurtarma:** `_guncelleme_kontrol` `merge-base --is-ancestor HEAD origin/<dal>` ile ff-mümkün mü bakar; HEAD atası DEĞİL + behind>0 ise `iraksama=True` (tipik: eski klon + uzakta geçmiş yeniden yazımı → `pull --ff-only` başarısız, yerel commit'ler uzakta yok). Bu durumda `engel` net mesaj verir + Güncelleme ekranında **"Uzak Sürümle Eşitle (sıfırla)"** düğmesi (`POST /api/guncelleme/sifirla` → `git reset --hard origin/<dal>` + pip + restart; YALNIZ ıraksama var + tracked ağaç TEMİZKEN, gitignore'lu `.env`/`reference/*` korunur). NOT: geçmiş yeniden yazımından ÖNCE klonlanan makineler bu düğmeyi ancak yeni koda geçtikten sonra görür → ilk kurtarma terminalden `git fetch origin && git reset --hard origin/main`.
- **Kapanma modeli (DESKTOP_MODE watchdog) — AÇIK-KAPANIŞ, heartbeat-sessizliği DEĞİL:** Sunucu ömrü artık
  idle sekmenin timer'ına BAĞLI DEĞİL. ESKİ model "KAPAT_SURE(180s) heartbeat gelmezse kapat" idi → Chrome
  arka plandaki idle sekmeyi 5+ dk sonra DONDURUR/atar → heartbeat durur → sunucu kendini kapatırdı → analist
  gün boyu AÇIK ama idle tutunca "Failed to fetch". YENİ model: sayfa GERÇEKTEN kapanınca `pagehide` beacon'ı
  `navigator.sendBeacon('/api/bye')` gönderir; watchdog `BYE_GRACE`(15s) içinde heartbeat geri DÖNMEZSE (=gerçek
  kapanış, yenileme değil) kapatır. Yenileme/çoklu-sekme: herhangi bir heartbeat `_client_bye_at`'ı sıfırlar →
  iptal. Idle/donmuş sekme beacon GÖNDERMEZ → sunucu açık kalır (başlatıcı `_start.sh` zaten curl ile canlı
  sunucuyu yeniden kullanır, port sorunu yok). **Idle "heartbeat yok" ile kapatma VARSAYILAN KAPALI**
  (`DESKTOP_IDLE_KAPAT_SAAT`=0=asla; >0 verilince saat-bazlı güvenlik ağı, yalnız iş yokken). Watchdog +
  `_mesgul_mu` + manuel `/api/restart` (iş sürerken 409 `onay_gerekli` → UI onayı → `force:true`) + AUTO_UPDATE +
  disk-temizlik artık bellek-içi arka plan işlerini de görür (`_arka_plan_isleri_calisiyor`: `_gorev_isler`/
  `_febe_preview_isler`/`_kopru_isler`/`_sohbet_isler` "calisiyor") → iş sürerken ne restart ne otomatik-kapanma
  keser. Uçlar: `POST /api/heartbeat` (bye iptal eder) · `POST /api/bye` (CSRF muaf, pagehide beacon). Test: `smoke_test`.
- Test paketi yok. **Lint: `venv/bin/ruff check .`** — commit öncesi çalıştır, TEMİZ çıkmalı (F821 gibi gerçek bug'ları yakalar; legacy stil istisnaları `ruff.toml`'da). Ayrıca app'i başlatıp boot logunu kontrol et.

## AI modu (KRİTİK — her analiz çağrısını etkiler)
Pilot ekip **CLI modu**: `.env` `USE_CLAUDE_CLI=true` (Claude.ai aboneliği, per-token yok).
CLI **görsel BRD analiz EDEMEZ** (PDF/DOCX/TXT/MD olmalı). API modu (`ANTHROPIC_API_KEY`) ikincil.
**429 dayanıklılığı (P1-B):** CLI kullanım limiti (429) `base.CliLimitError` fırlatır; `_api_cagri` bunu
yakalar ve **ANTHROPIC_API_KEY varsa** o çağrıyı otomatik API moduyla tamamlar (analistin işi kesilmez).
Anahtar yoksa (analist CLI makinesi) net hata yükselir. `CLI_LIMIT_API_FALLBACK=false` ile kapatılır
(maliyet kontrolü). `_api_cagri_direct` CLI modunda `anthropic`'i tembel import eder. Limit durumu +
sıfırlanma saati `/api/cli/durum` header göstergesinde görünür (`cli_durum_oku`).

## Klasör yapısı
- `app.py` Flask sunucu (~86 endpoint) · `run.py` orchestrator (subprocess) · `workflow.py` durum makinesi · `jira_agent.py` Jira OAuth+ADF
- `skills/` iş mantığı (`agent.py` = import bridge): `base.py` (sabitler/RAG/`_api_cagri`/promptlar), `atlassian.py` (**CANONICAL** OAuth helper), `surec_analizi` `teknik_analiz` `sohbet_analiz` (**İnteraktif Analiz** — doküman yüklemeden SOHBETLE süreç/teknik; aşağı bak) `delta_analizi` `brd_analizi` `kapsam_analizi` `jira_tasks` `jira_gorevleri` `kabul_kontrolu` (**Kabul Kontrolü** — ANALIZ CHECK task'ını test ortamında testçi gibi CANLI doğrular: 1 AI çağrısı kabul maddeleri (**kabul kriteri AC-n birincil**, her kriter ≥1 madde) → Playwright ile her madde fiilen denenir (BE kriterleri ENDPOINT'ten: network method/path/status; FE ekrandan; GET/POST/PUT/DELETE AI-TEST ile serbest) → **kriter bazlı** ✅/❌/⚠ rapor (analist formatı: Task·Konu·Ortam·İlgili task → Doğrulama Sonucu sayımı → Genel değerlendirme → Öne çıkan bulgular → kriter tablosu → Netleştirilmesi gereken konular → Sonuç cümlesi); ≥1 eksik = Geliştirmeye geri; Jira durumu DEĞİŞMEZ, rapor yorum; opsiyonel `talimat` (ekran URL + odak — UI prompt / köprü `kontrol <talimat>`; URL varsa gözlem o ekrandan başlar); Task Analizi **liste kartında '🧪 Kabul Kontrolü' düğmesi** (`jgKabulKontrolBaslat` — teknik analiz ÜRETMEDEN, mode `kabul-kontrol` + `markdown:''`; statü ANALIZ CHECK/kontrol/test ise vurgulu 'Başlat'; sonuç `kabulOnly` → panel başlığı 'Kabul Kontrolü', editörde rapor, Jira yazımı/eğitim/düzelt kapalı, 'Raporu Jira'ya yorum olarak yaz' açık) + analiz panelindeki "Kabul Kontrolü" + köprü `kontrol`; ayrıntı `docs/MIMARI.md`) `uat_durum_senkron` (**UAT Durum Senkronu** — TRADE/OPS task'ı geliştirmeye alınınca doğrudan linkli Backlog/Yapılacaklar UAT task'ını 'Devam Ediyor'a taşır + yorum; vars. KAPALI + önce rapor modu; 2 saatte bir, uygulama açıkken; ayar `reference/uat_senkron.json` gitignore; ayrıntı `docs/MIMARI.md`) `backlog_senkron` (**UAT Mutabakat** — 0-token deterministik; UAT takip hunisi + task analiz durumu `analiz_durumu`/`takip_asamasi`, geliştirmeye atanmamış = Backlog; Story analiz edilmez → alt task'larından (kapsam dışı Story genişletilir); ekran ORİJİNAL hâlinde (huni/analiz alanları yalnız Excel'de); ayrıntı `docs/MIMARI.md` "UAT Mutabakat") `jira_fe_be` (**FE/BE düz Task bölme** — teknik analiz → görev(Task) tipinde ayrı FE ve BE task'ları + ilişkili BE→FE **Blocks** bağı; aşağı bak) `confluence_yaz` `html_mockup` (canlı-app baz'lı prototip + sohbetle düzeltme; **Task Analizi → Ekran Mockup'ı**: `gorev_mockup_uret`/`gorev_mockup_duzelt` → `output/gorev-mockup.html`; aşağı bak) `sorular` `gozlem` (**Gözlem Fazı** — canlı gözlem analizden ayrı küçük promptla rapor + 6 sa önbellek; aşağı bak) `canli_giris` (**Canlı Giriş Kapısı** — analiz öncesi kayıtlı hesapla giriş doğrulaması, imzalı önbellek; aşağı bak) `soru_cozumleme` (**Açık Soru Öz-Çözümleme** — Task açık sorularını referans/kod/tüketici taraması + tek canlı gözlemle agent cevaplar, UI ön-dolu; aşağı bak) `bff_kesif` (**BFF Keşfi** — agent'ın kendi CRUD gözlemiyle ekran servis sözleşmesi raporu, 7 gün önbellek; aşağı bak) `akis_kapatma` (**Akış Kapatma** — boşluk tespiti + minimal bölüm düzeltme / açık soru, tek revizyon) `degisiklik_etkisi` (**Değişiklik Etkisi** — veri değişikliği sinyali + Swagger/Confluence/Jira tüketici taraması, 0 token) `telemetri` (**Kullanım İzleme** + token/maliyet kaydı; owner-gate **`reference/owner_konsol.json`** işaret dosyası — `_owner_konsol_aktif`, env DEĞİL; `_sink_gonder` SENKRON; çift-sayım önleme `remote.jsonl`) `ornek_havuzu` (**Onaylı Analiz Örnek Havuzu** — few-shot eğitimi: onaylı analizler → yerel+sink → en alakalı örnek prompt'a; aşağı bak) `hatalar` `disk_temizlik` `bildirim` (**yerel masaüstü bildirimi** — osascript, 0 token; aşağı bak) `jira_kopru` (**Jira Köprüsü** — Jira'yı web-chat gibi kullan; aşağı bak) `kod_kaynagi` `etki_analizi` `retrieval` `analiz_mcp`. **Modül sorumlulukları + telemetri/backlog/mockup tam ayrıntı → `docs/MIMARI.md`.**
- `templates/index.html` SPA · `reference/` RAG kaynakları (Atlassian sync) · `output/ input/ history/ logs/` runtime · `backlog/` UAT Mutabakat üretilen .xlsx raporları (gitignore) · `docs/` detaylı referans
- **Bağımlılıklar** (`requirements.txt`): Flask, anthropic, requests, python-dotenv, PyMuPDF, Pillow, python-docx, ruff + **openpyxl** (UAT Mutabakat .xlsx rapor yazımı). `lxml` hâlâ kurulu (genel kullanım).
- `reference/live-app` Claude MCP/Chrome ekran+network gözlem çıktıları içindir (gitignore); bağlam filtresinde ana URL + 5 alt URL ve "Örnek ekran olarak kullan" seçeneği süreç/teknik analize canlı uygulama görevi olarak eklenir.
- **Canlı uygulama ÇALIŞMASI için `claude -p`'ye MCP + izin geçmek ZORUNLU** — bkz. `docs/MIMARI.md` "Canlı Uygulama (Chrome MCP)". `--allowedTools` verilmezse headless modda tarayıcı araçları sessizce reddedilir.
  **CANLI GÖZLEM = MEVCUT DURUM → ÖNBELLEK OKUMAZ (KRİTİK):** canlı gözlemli analiz çağrıları
  (`canli_baglam`/`canli_uygulama_kapsami` doluyken) `_api_cagri(onbellek=False)` ile yapılır → "yeniden analiz"
  her seferinde uygulamayı **TAZE gözler**; bayat/eski-ortam (ör. DEV→UAT değişiminde eski) sonucu DÖNMEZ.
  Uygulanan: `gorev_analiz_et` (`onbellek=not canli_baglam`), `surec_analizi` (aynı), `teknik_analiz._teknik_uret_tam`
  (`onbellek=(deneme==1 and not canli_uygulama_kapsami)`). Cache anahtarı zaten URL/gözlem-kapsamını (mesaj içeriğinde)
  içerir; bu ek kural aynı ortamda tekrar çalıştırmada da güncel durumu yakalamak içindir. Gözlem YOKSA cache normal.
  Task Analizi canlı hedefi `live_app_gorev` (Süreç/Teknik `live_app`'ten AYRI alan) — doğru alanı düzenle.
  **Sağlamlaştırma (Faz 7):** (a) `@playwright/mcp` **sürüm PİNLİ** (`@0.0.80`, `@latest` DEĞİL — araç-adı kırılmalarına karşı). (b) **Sessiz-düşüş tespiti:** canlı gözlem istendi ama `num_turns<=1` (hiç araç kullanılmadı) VEYA **`LIVE_APP_ALLOWED_TOOLS` içindeki (izinli) bir tarayıcı aracı** reddedildiyse `_api_cagri_cli` net uyarı loglar + subprocess çıktısına yazar. **İzin listesi DIŞINDAKİ** yardımcı araçların (`browser_evaluate`/`browser_take_screenshot`/`Bash`) reddi BEKLENEN/zararsızdır → `_browser_reddi`'yi TETİKLEMEZ (yoksa çekirdek gözlem 29-57 tur başarıyla yapılsa da yanlış "yapılmadı" damgası basılıyordu). Ayrıca canlı-gözlem sonrası ajanın rapor ÖNCESİ sızdırdığı düşünme/ön-söz cümlesi `_onsoz_kirp` ile temizlenir (yalnız ilk markdown-yapısal satırdan önceki kısa düz-metin ön-söz; JSON/uzun gövde ASLA kırpılmaz). (c) **Şifre redaksiyonu:** `_canli_app_sifre_redakte` yapılandırılmış giriş şifresini çıktıdan deterministik temizler (prompt kuralına ek). (d) Odaklı gözlem modu (`gozlem_kapsami`) artık `use_as_sample` örnek-ekran notunu da içerir. (e) `/api/live-app/status` `hazir` = npx+url+profil **+ CLI modu + claude CLI** (yalnız CLI yolunda çalışır); `cli_modu`/`claude_var` alanları eklendi. (f) **Model araç çağırmama tespiti + OTOMATİK TEKRAR (teşhis 2026-10-16):** MCP sunucusu BAĞLI olduğu hâlde (CLI MCP logu `hasTools=true`) model büyük promptlarda (referans+few-shot+domain) tarayıcı talimatını atlayıp tek turda araçsız yanıt üretebiliyor (`num_turns=1`, 7/7 koşu). Çözüm: canlı kapsamlı her çağrıda promptun EN SONUNA `_LIVE_APP_ZORUNLU_ILK_ADIM` (recency — "yanıt yazmadan önce `browser_navigate`") eklenir; `num_turns<=1` ise `_api_cagri_cli(..., _tekrar=True)` sertleştirilmiş `_LIVE_APP_TEKRAR_UYARISI` ile BİR KEZ daha dener (`.env` `LIVE_APP_TEKRAR=false` kapatır). `.gozlem-durum.json` `neden` alanı (araç reddi / model araç çağırmadı; tekrar denendi) → rozet tooltip'i. Teşhis kaynağı: `~/Library/Caches/claude-cli-nodejs/<cwd-slug>/mcp-logs-playwright/*.jsonl`. (g) `live_app_kilidi_temizle` SingletonLock'a ek `pgrep -f --user-data-dir=<profil>` ile profili tutan Chrome'u da kapatır ("Browser is already in use" → gözlem düşmesin). (h) `bff_kesif.kesfet`: `<bff_rapor>` etiketi atlanmış ama `## Ekran/Açılış/CREATE` gövdesi varsa rapor KAYBEDİLMEZ; blok hiç yoksa ham yanıt `bff/<anahtar>.ham.txt`'ye yazılır (teşhis). Test: `tests/test_canli_tekrar.py`. (i) **PROFİL HAVUZU — paralel canlı gözlem (owner isteri 2026-10-16: Task Analizi + İnteraktif + Kabul Kontrolü + Süreç analizi AYNI ANDA, farklı analistler dahil):** Chrome aynı `--user-data-dir`'i ikinci kez açamaz ("Browser is already in use") → `_live_app_cli_argumanlari` artık ana profili kapatmak yerine `_slot_al()` ile `.live-app-profiles/slot-N` (N ≤ `LIVE_APP_PARALEL`, vars. 6) kilitler: pid'li `slot-N.lock` (`O_EXCL`, süreçler arası — run.py alt-süreci + Flask thread'leri; aynı süreçte `_SLOT_SAHIPLI`), ölü pid'li kilit devralınır (`_profil_sureclerini_kapat` yetim headless'ı kapatır, pgrep TAM eşleşme `(\s|$)` — `.live-app-profile` deseni `…profiles/slot-1`'i yakalamaz), ana profilin ("Tarayıcıda Giriş Yap") Cookies/Login Data/Local Storage/Session Storage/IndexedDB'si slota kopyalanır (`_slot_oturum_kopyala`, `.oturum-damga` ile yalnız ana yenilenince) → elle giriş slotlarda da geçerli; MCP config slot başına `.live-app-profiles/mcp.slot-N.json`; `_api_cagri_cli` `_cli_calistir`'ı try/finally ile sarar → slot HER DURUMDA serbest (tekrar denemesi yeni slot alır). Havuz doluysa `LIVE_APP_SLOT_BEKLE` (300 sn) bekler, sonra net hata (sessiz düşüş yok). `slot_durumu()` → `/api/live-app/status.slotlar`. `.gitignore`: `.live-app-profiles/`, `.mcp.live-app.*.json`. Test: `tests/test_live_app_slot.py`. (j) **OTURUM KALICILIĞI — agent girişi bir kez, tüm akışlar oturumlu (owner isteri 2026-10-19: 'her seferinde tarayıcıdan giriş yapmak zorunda kalmasın'):** agent slotta kayıtlı hesapla giriş yapınca slotun çerez/Login Data/Local+Session Storage/IndexedDB'si ana profilden YENİ olur → `_slot_birak` → `_slot_oturum_geri_yaz(slot)` ana profile GERİ yazar (`.oturum-son-giris` {ts, slot, kaynak:'agent'}; ana profil başlı Chrome'da açıksa ATLANIR; slot damgası güncellenir) → diğer slotlar `_slot_oturum_kopyala` ile devralır → Task/İnteraktif/Kabul/Süreç analizleri girişsiz başlar; oturum düşerse agent prompttaki OTOMATİK GİRİŞ ile yeniden girer (prompt: 'oturum zaten açıksa giriş adımını ATLA, asla logout yapma'). `oturum_durumu()` → `/api/live-app/status.oturum {var, son_giris, kaynak agent|tarayici, yas_dk}`; iki ekranın durum satırı 'Oturum kayıtlı (agent girişi · N dk önce) — analizler yeniden giriş yapmadan başlar' / 'Kayıtlı oturum yok — agent ilk analizde kendisi giriş yapar'. 'Tarayıcıda Giriş Yap' düğmesi **'Elle giriş (ayrı Chrome)'** oldu (`la-ikincil`, soluk; iki ekranda): tıklanınca `_laElleGirisOnay` kayıtlı oturum varsa bunu söyler ve 'agent'ın KENDİ profiliyle AYRI bir Chrome penceresi açılır (kişisel Chrome değil — agent kişisel oturumu kullanamaz); yalnız 2FA/captcha' onayı ister. Owner notu 2026-10-19: 'tarayıcıda giriş yap deyince yeni Chrome açıyor' → beklenen davranış, artık açıkça söyleniyor. Test: `tests/test_live_app_slot.py` §6. Kalan öneriler (düşük öncelik): TimeoutExpired için dostça mesaj, live-app cache bypass.
  **KOTA FAZ 0+1 — ÖLÇÜM + GÖZLEM FAZI AYRIMI (2026-10-19, `docs/KOTA-OPTIMIZASYON-PLANI.md`; owner onaylı):** Teşhis: canlı gözlem analiz çağrısının İÇİNDE agentik döngüyle yapılıyordu → her araç turu referans+few-shot+domain+task (~40k token) bağlamı yeniden okuyordu (tek çağrıda 5.9M cache okuma). **Faz 0 ölçüm:** `base.asama_ayarla(ad)` (thread-local etiket: gozlem · gorev:analiz/sorular/duzelt · surec:analiz · teknik:analiz · soru:cozum/gozlem · bff · giris · kabul:liste/dogrula) + `_api_cagri_cli` her çağrıyı `logs/usage/cagri.jsonl`'a yazar (`_cagri_kaydet`: model, canlı, kapsam, tur, girdi/çıktı/cache_yaz/cache_oku, süre, tekrar, max_tur_takildi, prompt_kc — içerik YOK) → `cagri_ozeti(gun)` → `GET /api/usage/cagri-ozet` (usage-gate) → Kullanım Raporu 'Aşama bazlı tüketim' paneli (`kuCagriOzetYukle`). **Faz 1 gözlem fazı (`skills/gozlem.py`):** `rapor_al(canli_blok, kapsam, gorev_ozet, yeniden)` KÜÇÜK promptla (canlı görev bloğu + ≤3k özet + rapor biçimi; referans/few-shot/domain YOK) `<gozlem_raporu>` üretir (Ekran/Alanlar/Aksiyon→İstek-Yanıt/Validasyon/Boş-Hata/Gezilemeyen, kanıt etiketli, ≤12k char) → `reference/live-app/gozlem/<sha1(kapsam|blok)>.md+.json`; `ok` = makine-doğrulanmış gözlem (`.gozlem-durum.json` yapildi) + kanıt var. **Motorlar** (`gorev_analiz_et` · `gorev_fe_be_analiz` · `surec_analizi_yap` · `teknik_analiz_yap`) canlı blok varken önce `rapor_al`, sonra analiz çağrısını `rapor_blogu` ile ve **TARAYICISIZ** (`canli_uygulama_kapsami` yok, önbellek normal — rapor metni anahtarda) yapar; gözlem başarısızsa `gozlem_yok_blogu` ile gözlemsiz üretir (rozet 'YAPILAMADI'). **FE+BE ayrı = TEK gözlem, iki analiz** (`gozlem_rapor` paylaşılır). **A1.3 önbellek:** `yeniden=False` (cevap turu / düzelt — `cevaplar|onceki_sorular` dolu) ise taze rapor (`GOZLEM_RAPOR_GECERLILIK`, vars. 6 sa) yeniden kullanılır; yeni analiz (`yeniden=True`) hep taze gözler → 'canlı gözlem = mevcut durum' kuralı korunur. **A1.4 tur tavanı:** `_api_cagri(max_turns)` → canlı çağrılarda `--max-turns` (`LIVE_APP_MAX_TUR`, vars. 40); CLI `subtype=error_max_turns` dönerse aynı oturum `--resume <session_id> --max-turns 3` + `_MAX_TUR_TAMAMLA` ('araç kullanma, raporu şimdi yaz') ile tamamlatılır (çıktı kaybolmaz); canlı prompta 'TUR DİYETİ' kuralları (aynı sayfayı ikinci kez snapshot alma, önce `browser_find`, 1-3 istek detayı). **YALIN CLI (ölçüldü):** `claude -p` varsayılan sabit bağlamı ~98k token (yerleşik araç şemaları ~35k + profil MCP'leri); analizler araç kullanmadığından `_yalin_cli_argumanlari` HER çağrıya `--tools "" --disable-slash-commands`, canlı/analiz-MCP yoksa `--mcp-config .mcp.bos.json --strict-mcp-config` ekler → gözlemsiz çağrıda sabit bağlam 62k. **CANLI çağrıda `--tools ""` KULLANILMAZ** (soğuk süreçte ilk tur araçsız gidiyordu; 2 gerçek koşuda ilk deneme düştü, araçları açık tekrar başardı) → canlı turda yalnız slash kapalı (~99k); `CLI_YALIN=false` tümünü kapatır (`.mcp.bos.json` gitignore). **ARAÇSIZ İLK TUR (teşhis 2026-10-19):** başarısız giriş testlerinde model araç çağrısını METİN olarak yazmış (`tool_use: browser_navigate`) = araçlar ilk turda modele ulaşmamış; hatalar hep yeniden başlatmadan hemen sonra (soğuk npx → MCP bağlantısı yavaş) → `_api_cagri_cli` araçsız tek-tur/pseudo-araç sonucunda `_LIVE_APP_TEKRAR_SAYISI`=2 ek deneme (2 sn gecikme; canlı çağrılarda yerleşik araçlar zaten açık), `neden`'de 'araç çağrısını metin olarak yazdı'; `base.mcp_isit()` boot'ta Playwright MCP'yi arka planda GERÇEKTEN ısıtır (sunucuyu başlatıp JSON-RPC `initialize`+`tools/list` el sıkışması, `isit-profil`, Chrome açılmaz, ≤25 sn) — gerçek koşuda doğrulandı: restart sonrası ilk çağrı araçsız düştü, 1. tekrar 5 turda başarılı. **TEST KURALI:** motorlara (`gorev_analiz_et`/`gorev_fe_be_analiz`/süreç/teknik) giren her test `canli_uygulama_baglami_hazirla`'yı mock'lamalı (`lambda *a, **k: ""`) — yoksa gözlem fazı GERÇEK CLI/Playwright açar. Test: `tests/test_gozlem_fazi.py`. **KOTA FAZ 2+3 (2026-10-19, owner onaylı — plan §7, `docs/MIMARI.md` "Kota Faz 2+3"):** **Faz 2 — "Cevapları İşle" HEDEFLİ:** `jira_gorevleri.gorev_cevap_uygula(gorev, mevcut_md, cevaplar, onceki_sorular)` → cevaplar `gorev_analiz_duzelt` ile ilgili bölümlere işlenir (`_CEVAP_TALIMAT`: belirsiz/varsayım işaretleri kalkar, `[K: Analist cevabı]`, ilgisiz bölüme dokunma; aşama `gorev:cevap`) + `_gorev_acik_sorular_uret(cevaplar, onceki)` kalan soruları yakınsar; RAG yorumu korunur; gözlem/RAG/öz-çözümleme TEKRARLANMAZ (eski tam zincir ≈4 büyük çağrı → 2 küçük). Task Analizi iş modu **`cevap`** (`_adim_isle`: adım `markdown`=editör içeriği doluysa hedefli, boşsa/`CEVAP_HEDEFLI=false` ise `mode="analiz"` tam üretim); UI `jgCevaplariIsle` → `mode:'cevap'` ("Cevapları İşle → Analize Uygula"), `jgCevaplariBastanUret` bilinçli tam üretim; köprü `cevap` komutu mevcut analiz (önbellek/gövde) varsa aynı hedefli yol. **Faz 3 — MODEL KATMANLARI (yalnız CLI):** `base.cli_model_katman(k)`: `ana`→CLAUDE_CLI_MODEL · `yardimci`→`CLI_MODEL_YARDIMCI` (vars. `sonnet`) · `hafif`→`CLI_MODEL_HAFIF` (vars. `haiku`). `_api_cagri(..., katman="")`: açık katman > model sabiti (`MODEL_HAFIF`→hafif, `MODEL_YARDIMCI`=`claude-sonnet-5-5`→yardimci; MODEL_ANALIZ ile aynı id OLAMAZ) > ana → `_api_cagri_cli(katman)` `--model`; önbellek anahtarı + `cagri.jsonl` katmanı taşır. Yardımcı: gözlem fazı · giriş testi · BFF keşfi · kabul liste+doğrulama · soru sınıflandırma+çözüm gözlemi · `gorev_analiz_duzelt` (cevap/öz-çözümleme işleme dahil) · sohbet ekran envanteri. Hafif: formatla · test senaryoları · açık soru toplama. Ana (Opus): süreç/teknik/görev analizi · denetçi · FE/BE bölme · akış kapatma · sohbet turu. **CLI ≥ 2.1.303 gerekir** (alias'lar `sonnet`→Sonnet 5.5, `haiku`→Haiku 5.5, `opus`→Opus 5.5; 2.1.267 `claude-opus-5-5`'i reddeder → analistler `claude update`). Karşılaştırma (aynı canlı prompt): Opus 5.5 = Opus 4.8 ile aynı çıktı, daha az tur, ~%30 ucuz; Sonnet 5.5 onun yarısı → owner `.env` `CLAUDE_CLI_MODEL=claude-opus-5-5`. Yeni yardımcı/hafif AI çağrısı eklerken `katman="yardimci"` ya da `model=MODEL_HAFIF` geç. Test: `tests/test_kota_faz23.py`.
  **KABUL KONTROLÜ EKSİKSİZ TAMAMLAMA (owner 2026-10-19: 'canlı gözlem olmasına rağmen işaretli maddeleri check yapamamış, eksik bırakmamalı'):** Teşhis (app.log): 21 maddelik kontrol 40 turluk genel `LIVE_APP_MAX_TUR` tavanına 4 kez takıldı → `_MAX_TUR_TAMAMLA` 'araç kullanma, raporu yaz' dedi → agent kalan maddeleri 'oturum sona erdi / test edilemedi' diye bıraktı. Çözüm (3 katman): (1) `kabul_kontrolu.tur_butcesi(n)` = `KABUL_TUR_TABAN`(40) + `KABUL_TUR_MADDE`(6)×denenebilir madde, `KABUL_TUR_TAVAN`(160) ile sınırlı → `canli_dogrula` `_api_cagri(max_turns=butce, tur_devam=KABUL_TUR_DEVAM(2))`. (2) **Tur devamı (`base._api_cagri_cli(tur_devam)`):** `error_max_turns` gelince çıktıyı zorlamak yerine AYNI oturum `--resume` + aynı `--max-turns` ile `_TUR_DEVAM_MESAJI` ('bütçen yenilendi, çıktıyı yazma, kaldığın maddeden devam; giriş düştüyse yeniden gir') `tur_devam` kez sürdürülür; haklar bitince eski araçsız tamamlatma (`_MAX_TUR_TAMAMLA` artık 'tur bütçesi doldu — denenmedi' demesini ister, 'oturum sona erdi' DEĞİL). Genel env `LIVE_APP_TUR_DEVAM` (vars. 0 — gözlem fazı etkilenmez). (3) **Tamamlama turu (`tamamlama_turu`, `KABUL_TAMAMLAMA`=1):** ilk tur sonucunda `_tamamlama_adayi` (durum dogrulanamadi + neden boş/bildirmedi/tur bütçe/oturum sona/test edilemedi/denenmedi — `_BUTCE_NEDENI`; yetki/veri/ekran yok gibi gerçek engel HARİÇ) maddeler YALNIZ kendileriyle taze bütçeli ikinci `canli_dogrula`'ya gider ('TAMAMLAMA TURU' notu), sonuçlar birleşir (`_sonuc_normalize` yeniden; bulgular/yazma/gezilemeyen eklenir), `sonuc.tamamlama {denenen,kurtarilan,kalan}` raporda '_Tamamlama turu: …_' satırı; hata → ilk tur korunur. Talimata eklendi: 'EKSİK BIRAKMA — sırayla her maddeyi dene, bütçe yenilenir, erken rapor yazma' + 'OTURUM DÜŞERSE kayıtlı hesapla yeniden gir ve kaldığın maddeden devam et'. Test: `tests/test_kabul_kontrolu.py` §4b.
  **KOTA TARAMASI 2 (2026-10-19 akşam, plan §8 — ekip 'kota çabuk doluyor'):** (1) **BUG:** tavana takılıp `--resume` ile tamamlatılan canlı çağrının JSON'u yalnız tamamlatma turunu gösteriyordu → `cagri.jsonl` yanlış (40 tur → '1'), ve `num_turns<=1` 'araç çağırmadı' tekrarı yanlış tetiklenip gözlem 2 kez daha koşuyordu (BFF 3×40 tur). `_api_cagri_cli` tavan/devam/tamamlatma koşularının usage/tur'unu `_onceki_koşular` ile BİRİKTİRİR, tespit birikimli tura bakar. (2) **Canlı çağrıda `--tools ""` İLK denemede** (tur başına ~100k→73k; MCP boot ısıtması sonrası 4/4 başarılı), `_tekrar>0`'da yerleşik araçlar açık; `LIVE_APP_YERLESIK_ARACLAR=true` eski davranış. (3) **Giriş testi atlama:** `canli_giris.durum` agent kaynaklı taze `oturum_durumu()` varsa `gerekli=False` (0 token); başarısız taze sonuç atlamayı ezer. (4) `bff_kesif` `BFF_MAX_TUR`(70) + `tur_devam=1`. Test: `test_gozlem_fazi` (birikim/devam/tools/tekrar), `test_canli_giris` (`oturum_durumu` mock ZORUNLU). **EKİP KOTA ÖLÇÜMÜ:** sink `token` alanını DÜŞÜRÜR → `telemetri.olay_yaz` token özetini `baglam.dokuman`'a `⟨tok g,c,cy,co,n,usd⟩` GÖMER (`_tok_gom`), `olaylari_oku`/`uzaktan_cek` `_olay_normalize` (`_tok_coz`) ile geri çözer + dokümanı temizler (Apps Script değişmez; `docs/telemetri-apps-script.md` opsiyonel sütun yolu). `kota_karsilastirma` olay bazında `KOTA_OLCUM_BASLANGIC` (vars. 2026-10-19T18:00) öncesi/sonrası ortalama okuma/süre/Δ% → `ozet().karsilastirma` → Kullanım Raporu "Kota ölçümü" tablosu. Test: `tests/test_telemetri_olcum.py`.
  **Takılma/erişim geri bildirimi (Faz 8 — "bir saat sessiz bekleme" sorunu):** analiz uzun sürerse analist ekranda bilgilensin + iş yarıda kalmasın diye TÜM analiz/task akışlarında geçen-süre + takılma uyarısı eklendi. (1) `workflow.ozet()` → `aktif_adim_zaman` + `gecen_sn` (aktif adımın sunucu-tarafı süresi; sayfa yenilense de doğru). (2) Süreç/Teknik + BRD `.hazirlaniyor` bloklarına `#surec-stall-uyari`/`#brd-stall-uyari`: `updateUI` geçen süreyi `max(s.gecen_sn, yerel _stepStart)`'tan gösterir, `_JG_STALL_SN`=180 sn aşılınca "beklenenden uzun sürüyor · VPN/ağ kontrol · iş arka planda sürüyor, Durdur'a basıp tekrar deneyebilirsin" uyarısı. (3) Task Analizi: `/api/jira/gorev/is/durum` → `gecen_sn`+`adim_gecen_sn` (job `aktif_bas`=`_adim_isle` başı), `#jg-proc-uyari` aynı 180 sn eşikli uyarı. (4) **Polling dayanıklılığı (VPN kopması):** `pollState` 3 hatadan sonra ARTIK `stopPoll()` YAPMAZ — 5 sn'lik yavaş aralığa düşüp "Bağlantı yok — yeniden deneniyor…" banner'ı gösterir; bağlantı geri gelince banner temizlenir + normal aralığa döner (iş arka planda sürdüğü için ekran kendiliğinden toparlar). (5) Task/FE-BE hataları `skills.hatalar.insanlastir` ile insanlaştırılır (`job.sonuclar[key].hata` = `baslik — oneri`, `hata_ozet` saklanır) → analist ham traceback yerine "ne oldu + ne yapmalı" görür. (6) Canlı-gözlemli CLI çağrısı `LIVE_APP_CLI_TIMEOUT` (default 720 sn) ile daha kısa timeout → sonsuz bekleme yerine erken dostça hata.

## Hard kurallar
1. **Türkçe** yaz (print/yorum/hata); teknik terimler İngilizce kalır.
2. Asla commit etme: `.env` (chmod 600) + makineye özel `reference/{context_filter,prompts,sources,kod_kaynagi,analiz_mcp,jira_kopru,uat_senkron}.json` + `reference/domain-kurallari.md` (gizli el kitabından damıtılan domain bilgisi) (gitignore'da; `*.example` izlenir, açılışta `_runtime_config_seed()` ile seed). **`*.example` dosyaları JENERİK kalır — GERÇEK şirket verisi (Jira proje anahtarı, Confluence space, accountId, URL, e-posta) KONMAZ; yapı gösterir, gerçek liste yerel `reference/*.json`'a (git'e gitmez) yazılır.** **Gizlilik güvenlik duvarı:** `.githooks/pre-commit` (setup.sh `core.hooksPath .githooks` yapar) sır/PII/şirket bilgisi (API anahtarı, kimlikli bağlantı dizesi, Jira accountId, iç IP, kişisel e-posta) + **canlı-gözlem snapshot'ları** (playwright `[ref=]` erişilebilirlik ağacı — şirket UI içeriği) + yasak dosyaların commit'ini ENGELLER; bilinçli istisna `git commit --no-verify`. Canlı-gözlem dump'ları (`nav.yml`/`*-modal.yml`/`resp*.json`) gitignore'da. **KURAL: yüklenen doküman / canlı gözlem / analiz çıktısı İÇERİĞİ (BRD metni, ekran ağacı, gerçek servis/endpoint, kişi adı) tracked dosyaya ASLA yapıştırılmaz** — input/output/history/backlog + snapshot'lar gitignore'da tutulur. **Bilinçli istisna:** `reference/servis_varsayilan.json` (TRACKED) owner'ın ekibe yayınladığı BFF `{name,url}` varsayılanlarını içerir (iç ağ hostname'i; **sır/auth/PII YOK** — auth per-analist yereldir). Owner kararıyla eklenir; sır/token ASLA konmaz.
3. Atlassian helper → her zaman `skills/atlassian.py`'den import (duplicate tanım yok).
4. Yeni output dosyası → `IZIN_VERILEN_CIKTILAR` (app.py). Yeni Jira field → `jira_agent.py` + `skills/jira_tasks.py`.
5. Prompt önceliği: ekrandaki **Özel Prompt** (`context_filter.json → ozel_prompt`, analiz-bazlı, varsayılanın YERİNE geçer) > `reference/prompts.json` (kalıcı override, **gitignore/makine-yerel** — tüm skill promptunu EZER, fork riskli) > `VARSAYILAN_PROMPTLAR` (base.py). **Domain kuralları (MBS eğitim):** `reference/domain-kurallari.md` (**GİTIGNORE** — gizli el kitabı/BRD'den damıtılan domain bilgisi içerir; `.md.example`'dan `_runtime_config_seed` ile seed) → `base._domain_kurallari_oku()` HER analiz promptuna (`_EK_KURAL_SKILL_IDS` + süreç/teknik özel-prompt yolları) `_ORTAK_EK_KURALLAR`'dan SONRA otomatik ekler. `rsplit`'le SON `<!-- KURALLAR-BASLANGIC -->` işaretinden sonrası alınır; boş/yorum iken enjekte edilmez (güvenli no-op → `.example` seed'i davranış değiştirmez). Terim sözlüğü + değişmez KURALLAR buraya (PII/sır YASAK); GERÇEK VERİ (tablo/örnek/Kafka/endpoint) RAG corpus'una (`reference/confluence`, `reference/services`). Yol haritası + kürasyon: `docs/AGENT-EGITIM.md`.
6. `sys.executable` kullan, Python yolu hard-code etme. `env_oku()` tırnakları strip eder.
7. **GÜVENLİK: canlı-uygulama parolası** (`context_filter.json` `live_app_auth.password`) **`GET` ve `POST /api/context-filter` yanıtında** TARAYICIYA GÖNDERİLMEZ — maskeli (`has_password` bool); diske gerçek parola yazılır, yanıt maskelenir. POST'ta boş parola gelirse mevcut KORUNUR (maskeli UI silmesin); `sifre_temizle:true` açıkça boşaltır. Diskte 0600+gitignore. **Sır redaksiyonu (P1-D):** `base.sir_kaydet/sir_redakte` + `app._SirRedaksiyonFiltre` tüm loglardan API anahtarı/şifre/`sk-…` desenlerini «sır» ile maskeler; açılışta `_hassas_dosya_izinlerini_sertlestir` `.env`+`context_filter.json`'ı 0600 yapar. API anahtarı kullanıcı tercihiyle düz metin kalır (keychain uygulanmadı — bilinçli).

## İlgili dosyalar — TÜM REPOYU TARAMA
Görev başında geniş dizinleri (`reference/`, `venv/`, `logs/`, `output/`) tarama. İhtiyaca göre:
- Mimari / sabitler / RAG / promptlar / workflow / 3-aşamalı teknik analiz / Jira Görevleri / **Task Analizi akış detayı** / **telemetri + skills modül sorumlulukları (tam metin)** / cache / TL;DR → **`docs/MIMARI.md`**
- Tam endpoint kataloğu (~80) → **`docs/ENDPOINTS.md`**
- Auth / CSRF / güvenlik / dağıtım / onboarding → **`docs/GUVENLIK-DAGITIM.md`**
- Faz / değişiklik geçmişi → **`docs/DEGISIKLIK-GECMISI.md`** (özet index + son işler); eski işlerin tam metni → **`docs/DEGISIKLIK-ARSIV.md`**
- Agent'ı MBS (spor bahsi) domain'i için eğitme (context-engineering) yol haritası + kürasyon günlüğü → **`docs/AGENT-EGITIM.md`**
- **Akış çıkarma (flow analizi):** bir uygulamayı **Claude in Chrome** ile ekran-ekran gezip kullanıcı akışlarını adım tablosu + Mermaid diyagram olarak çıkarıp Confluence'a yayınlayan **düzenlenebilir skill** → `.claude/skills/akis-cikarma/` (SKILL.md + şablonlar). Agent sürer, **analist parola/OTP/hassas girişi yapar** (agent yazmaz). Analistler skill'i kullandıkça geliştirir (edit + commit). Yayın: Atlassian MCP ya da `/api/confluence/publish`.
- Belirli iş mantığı → ilgili tek `skills/<modül>.py` (önce o dosyayı oku, base.py'yi sadece gerekirse).

## CLAUDE.md / docs bakımı (zorunlu)
Dosya yapısı, skill sorumluluğu, endpoint, sabit/limit/model, prompt, workflow veya hard kural değişince
ilgili `docs/*` + bu özeti aynı/takip commit'inde güncelle. Sadece CSS/typo atlanabilir.
`.claude/hooks/post-commit-reminder.py` hatırlatır; nihai sorumluluk Claude'da.
