# brd-analyst-agent (Analyst Studio) — Claude Code Context

macOS masaüstü uygulaması. BRD/süreç dokümanı → RAG destekli analiz → Jira Epic/Story/Subtask.
Flask + Python **3.10+** (`str|None`), tarayıcı SPA `http://localhost:5003` (v2; v1 = 5002, ayrı dizin/süreç).
İki akış: **Süreç → Teknik → Jira** (ana, FE/BE ayrımı) · **BRD → Kapsam**.

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
  görünmez (tüm analiz tipleri). `/api/sorular` her zaman filtreli döner. (10) **Ekran adları:** "Çıktılar" →
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
  **otomatik `revizyon.onayla`** (sürüm oluşur, Revizyon ekranından Geri Al). Bölüm bulunamazsa
  `tam_uretim_gerekli` döner → UI analiste ID eklemesini ya da "Tam yeniden üret" (eski `/api/rerun`, artık
  `<details>` içinde SON ÇARE) önerir; asla sessizce tümü yeniden yazılmaz. **"◂ Süreç analizine dön"**
  (`POST /api/geri-don` → `wf.surec_adimina_geri_don()`, yeni geçiş TEKNIK_ANALIZ_ONAY_BEKLENIYOR→
  ONAY_BEKLENIYOR): süreç analizi YENİDEN ÇALIŞMAZ, teknik-analiz.md silinmez; analist süreçte hedefli
  düzeltir, "Devam Et" teknik analizi yeniden üretir. **Soru cevapları hedefli:** `/api/sorular/uygula` →
  `_sorulari_hedefli_uygula`: `bagli_id` bölümü analiz dosyasında (`_SORU_HEDEF_ANALIZ`: acik-sorular→
  teknik-analiz, brd-sorular→brd-analizi) bulunursa yalnız o bölüm düzenlenir; bulunamayanlar toplanıp
  `yeniden_calistir`'a düşer (`sonuclar[].hedefli/tam_uretim`). **`revizyon_ai.bolum_bul` iki aşamalı:**
  (1) başlık eşleşmesi (teknik analiz — ID başlıkta), (2) başarısızsa **gövde-içi ID fallback** (süreç analizi —
  ID gövdede satır-içi `**PA-003:** …`; `anahtar`'daki ID token'ını içeren EN DERİN bölüm) → süreç Q&A cevapları da
  hedefli/ucuz uygulanır, tam-regenerasyona düşmez. ID yoksa/bulunmazsa None (tam-regen — doğru davranış).
- **Kaynak-öncelik sırası (KANONİK, tek liste — `_ORTAK_EK_KURALLAR` + 4 rol promptu hizalı):**
  `Swagger > Canlı Uygulama Gözlemi > Confluence > BRD/Süreç > Jira > UI`. İlke: **gözlemlenen/doğrulanabilir
  gerçek veri (Swagger sözleşmesi + MCP canlı gözlem), tarif edilen istekten (BRD) ÜSTÜNDÜR** — BRD
  hatalı/güncel-olmayan olabilir. Olgusal çelişkide (endpoint/alan/tip/gerçek davranış) gerçek veri kazanır,
  çelişki yine Açık Sorular/Tutarsızlıklar'a raporlanır. Ana doküman analizin KONUSU/izlenebilirlik çapası olarak durur.
- **Faz 2 — Ürün kalitesi:** tasarım sistemi `static/ds.css` (`ds-*`); ekranlar `screens/ciktilar.html`
  (`/api/oturum`, tazelik = mtime ≥ oturum başlangıcı), `delta.html` (Süreç'ten ayrıldı, `da-*` ID korundu),
  `yetki.html`; sidebar iş akışına göre gruplu (Analiz / Çıktılar & Revizyon / Jira / Kaynaklar / Yönetim 🔒).
  **Roller:** owner (AUTH kapalı → tek kullanıcı; açık → `ADMIN_USER`) / analist. Analist, owner'ın
  `gorunurluk.json`'da (repoda İZLENİR) gizlediği id'ler hariç her şeyi kullanır; sunucu tarafı
  `gorunurluk_kontrol` + UI `_rolUygula()`. (Denetim/audit kaydı v3'te kaldırıldı — üstteki UI v3 notuna bak.)
  Yeni gizlenebilir ekran/aksiyon → `GIZLENEBILIR_KATALOG` (app.py). **Owner konsolu (Kullanım Raporu +
  Yetki ekranları) — kilit `.env`'de DEĞİL, gitignore'lu YEREL DOSYADA:** `_owner_konsol_aktif()` yalnız
  `reference/owner_konsol.json` (`{"owner_konsol": true}`) okur; `_usage_yetkili_mi()` + `_yetki_paneli_mi()`
  buna bağlı. Eski `OWNER_KONSOL`/`YETKI_PANELI`/`USAGE_DASHBOARD` env bayrakları **ARTIK OKUNMAZ** (analiste
  kopyalanan owner `.env`'i bu ekranları açıyordu — kapatıldı). Dosya git'e gitmez, `.env` paylaşımıyla
  taşınmaz, `.example`'dan **false** seed edilir (`_runtime_config_seed`) → güncelleme sonrası owner
  HARİCİNDEKİ tüm agent'larda KAPALI. Owner kendi makinesinde dosyayı `true` yapar (tek seferlik; UI'da
  açığa çıkmaz). `auth/me.usage_admin`/`.yetki_admin` → `#nav-kullanim`/`#nav-yetki`; endpoint'ler
  `usage_gerekli`/`yetki_gerekli` (403). Kendi makinesine kuran analist AUTH kapalıyken 'owner' rolündedir
  ama işaret dosyası olmadığından bu ekranları GÖRMEZ.
  **Otomatik güncelleme (2.5):** boot'ta `_oto_guncelleme_baslat()` — iş yokken `pull --ff-only` + restart;
  dirty tree / push edilmemiş commit varsa yalnız bildirir. `.env` `AUTO_UPDATE=false` kapatır,
  `AUTO_UPDATE_INTERVAL` (sn). Banner: `screens/_guncelleme.html`. `/api/update` elle akış aynen durur.
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
  **Task Analizi / test düzeltmeleri (özet):** görev analizi akışı — JARVIS reaktör, ilişkili FE/BE **seçim paneli** (`_jgSecimGoster`), **gömülü** panel (`#jg-preview-card.jg-inline`), arka plan iş (`_gorev_is_calistir`) + **paralel** (ThreadPoolExecutor, `GOREV_PARALEL`), açık soru **yakınsaması** (`_gorev_acik_sorular_uret onceki_sorular`), **gerçek Durdur** (killpg). Ayrıca: soru mezar-taşı, `/api/oturum` `aktif` bayrağı, CLI hesabı bilgisi, Jira Ayarları sadeleştirme (site otomatik), UAT key link'leri, bağlam-filtresi kaydı (`_jgFiltreKaydet`). **Tam akış + tüm alt-düzeltmeler → `docs/MIMARI.md` "Task Analizi" + `docs/DEGISIKLIK-ARSIV.md`.**
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
  `test_bildirim.py` (bildirim kaçış/redaksiyon/no-op), `test_bildirim_akis.py` (analiz bildirim geçiş+dedup).
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
  **Ekip/kullanıcı hızlı rehberi + SSS → `docs/JIRA-KULLANIM.md`; uygulama-içi kılavuz `KILAVUZ.html`
  §18 (Jira Köprüsü) + §19 (Bildirimler).**
- **FE/BE düz Task bölme (`skills/jira_fe_be.py` — süreç ekranı onay→Jira):** Süreç→Teknik akışında
  teknik analiz onaylanınca "Evet — FE/BE Task'larını Öner" (`teknikOnaylaFeBe`) → **önizleme modalı**
  (`#febe-modal`) açılır; workflow YALNIZ task'lar açıldıktan sonra bitirilir (auto tek-Task YOK) — iptal
  edilirse teknik-onay adımı korunur (tekrar denenebilir / "Atla"). **PROMPT-ÖNCE, iki durumlu modal
  (`_febeView('prompt'|'preview')`):** açılışta AUTO-SPLIT YOK → önce **PROMPT ekranı** (`#febe-prompt-view`):
  analist "kaç task / nasıl bölünsün" yazar (`#febe-talimat` textarea; ör. "sadece 2 task: 1 FE + 1 BE",
  "ekran bazlı böl", "ödeme ve sipariş olarak ayır"; boş = doğal kırılım) → **"Task'lara Böl"** (`febeBol` →
  `/preview` `talimat` ile). Sonra **ÖNİZLEME ekranı** (`#febe-preview-view`): `d.plan` özeti + task listesi
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
- `skills/` iş mantığı (`agent.py` = import bridge): `base.py` (sabitler/RAG/`_api_cagri`/promptlar), `atlassian.py` (**CANONICAL** OAuth helper), `surec_analizi` `teknik_analiz` `delta_analizi` `brd_analizi` `kapsam_analizi` `jira_tasks` `jira_gorevleri` `backlog_senkron` (**UAT Mutabakat** — 0-token deterministik) `jira_fe_be` (**FE/BE düz Task bölme** — teknik analiz → görev(Task) tipinde ayrı FE ve BE task'ları + ilişkili BE→FE **Blocks** bağı; aşağı bak) `confluence_yaz` `html_mockup` (canlı-app baz'lı prototip + sohbetle düzeltme) `sorular` `telemetri` (**Kullanım İzleme** + token/maliyet kaydı; owner-gate **`reference/owner_konsol.json`** işaret dosyası — `_owner_konsol_aktif`, env DEĞİL; `_sink_gonder` SENKRON; çift-sayım önleme `remote.jsonl`) `hatalar` `disk_temizlik` `bildirim` (**yerel masaüstü bildirimi** — osascript, 0 token; aşağı bak) `jira_kopru` (**Jira Köprüsü** — Jira'yı web-chat gibi kullan; aşağı bak) `kod_kaynagi` `etki_analizi` `retrieval` `analiz_mcp`. **Modül sorumlulukları + telemetri/backlog/mockup tam ayrıntı → `docs/MIMARI.md`.**
- `templates/index.html` SPA · `reference/` RAG kaynakları (Atlassian sync) · `output/ input/ history/ logs/` runtime · `backlog/` UAT Mutabakat üretilen .xlsx raporları (gitignore) · `docs/` detaylı referans
- **Bağımlılıklar** (`requirements.txt`): Flask, anthropic, requests, python-dotenv, PyMuPDF, Pillow, python-docx, ruff + **openpyxl** (UAT Mutabakat .xlsx rapor yazımı). `lxml` hâlâ kurulu (genel kullanım).
- `reference/live-app` Claude MCP/Chrome ekran+network gözlem çıktıları içindir (gitignore); bağlam filtresinde ana URL + 5 alt URL ve "Örnek ekran olarak kullan" seçeneği süreç/teknik analize canlı uygulama görevi olarak eklenir.
- **Canlı uygulama ÇALIŞMASI için `claude -p`'ye MCP + izin geçmek ZORUNLU** — bkz. `docs/MIMARI.md` "Canlı Uygulama (Chrome MCP)". `--allowedTools` verilmezse headless modda tarayıcı araçları sessizce reddedilir.
  **Sağlamlaştırma (Faz 7):** (a) `@playwright/mcp` **sürüm PİNLİ** (`@0.0.80`, `@latest` DEĞİL — araç-adı kırılmalarına karşı). (b) **Sessiz-düşüş tespiti:** canlı gözlem istendi ama `num_turns<=1` (hiç araç kullanılmadı) VEYA **`LIVE_APP_ALLOWED_TOOLS` içindeki (izinli) bir tarayıcı aracı** reddedildiyse `_api_cagri_cli` net uyarı loglar + subprocess çıktısına yazar. **İzin listesi DIŞINDAKİ** yardımcı araçların (`browser_evaluate`/`browser_take_screenshot`/`Bash`) reddi BEKLENEN/zararsızdır → `_browser_reddi`'yi TETİKLEMEZ (yoksa çekirdek gözlem 29-57 tur başarıyla yapılsa da yanlış "yapılmadı" damgası basılıyordu). Ayrıca canlı-gözlem sonrası ajanın rapor ÖNCESİ sızdırdığı düşünme/ön-söz cümlesi `_onsoz_kirp` ile temizlenir (yalnız ilk markdown-yapısal satırdan önceki kısa düz-metin ön-söz; JSON/uzun gövde ASLA kırpılmaz). (c) **Şifre redaksiyonu:** `_canli_app_sifre_redakte` yapılandırılmış giriş şifresini çıktıdan deterministik temizler (prompt kuralına ek). (d) Odaklı gözlem modu (`gozlem_kapsami`) artık `use_as_sample` örnek-ekran notunu da içerir. (e) `/api/live-app/status` `hazir` = npx+url+profil **+ CLI modu + claude CLI** (yalnız CLI yolunda çalışır); `cli_modu`/`claude_var` alanları eklendi. Kalan öneriler (düşük öncelik): TimeoutExpired için dostça mesaj, live-app cache bypass, iki akışın profil serileştirmesi.

## Hard kurallar
1. **Türkçe** yaz (print/yorum/hata); teknik terimler İngilizce kalır.
2. Asla commit etme: `.env` (chmod 600) + makineye özel `reference/{context_filter,prompts,sources,kod_kaynagi,analiz_mcp,jira_kopru}.json` (gitignore'da; `*.json.example` izlenir, açılışta `_runtime_config_seed()` ile seed). **`*.example` dosyaları JENERİK kalır — GERÇEK şirket verisi (Jira proje anahtarı, Confluence space, accountId, URL, e-posta) KONMAZ; yapı gösterir, gerçek liste yerel `reference/*.json`'a (git'e gitmez) yazılır.** **Gizlilik güvenlik duvarı:** `.githooks/pre-commit` (setup.sh `core.hooksPath .githooks` yapar) sır/PII/şirket bilgisi (API anahtarı, kimlikli bağlantı dizesi, Jira accountId, iç IP, kişisel e-posta) + **canlı-gözlem snapshot'ları** (playwright `[ref=]` erişilebilirlik ağacı — şirket UI içeriği) + yasak dosyaların commit'ini ENGELLER; bilinçli istisna `git commit --no-verify`. Canlı-gözlem dump'ları (`nav.yml`/`*-modal.yml`/`resp*.json`) gitignore'da. **KURAL: yüklenen doküman / canlı gözlem / analiz çıktısı İÇERİĞİ (BRD metni, ekran ağacı, gerçek servis/endpoint, kişi adı) tracked dosyaya ASLA yapıştırılmaz** — input/output/history/backlog + snapshot'lar gitignore'da tutulur.
3. Atlassian helper → her zaman `skills/atlassian.py`'den import (duplicate tanım yok).
4. Yeni output dosyası → `IZIN_VERILEN_CIKTILAR` (app.py). Yeni Jira field → `jira_agent.py` + `skills/jira_tasks.py`.
5. Prompt önceliği: ekrandaki **Özel Prompt** (`context_filter.json → ozel_prompt`, analiz-bazlı, varsayılanın YERİNE geçer) > `reference/prompts.json` (kalıcı override) > `VARSAYILAN_PROMPTLAR` (base.py).
6. `sys.executable` kullan, Python yolu hard-code etme. `env_oku()` tırnakları strip eder.
7. **GÜVENLİK: canlı-uygulama parolası** (`context_filter.json` `live_app_auth.password`) `GET /api/context-filter`'da TARAYICIYA GÖNDERİLMEZ — maskeli (`has_password` bool). POST'ta boş parola gelirse mevcut KORUNUR (maskeli UI silmesin); `sifre_temizle:true` açıkça boşaltır. Diskte 0600+gitignore. **Sır redaksiyonu (P1-D):** `base.sir_kaydet/sir_redakte` + `app._SirRedaksiyonFiltre` tüm loglardan API anahtarı/şifre/`sk-…` desenlerini «sır» ile maskeler; açılışta `_hassas_dosya_izinlerini_sertlestir` `.env`+`context_filter.json`'ı 0600 yapar. API anahtarı kullanıcı tercihiyle düz metin kalır (keychain uygulanmadı — bilinçli).

## İlgili dosyalar — TÜM REPOYU TARAMA
Görev başında geniş dizinleri (`reference/`, `venv/`, `logs/`, `output/`) tarama. İhtiyaca göre:
- Mimari / sabitler / RAG / promptlar / workflow / 3-aşamalı teknik analiz / Jira Görevleri / **Task Analizi akış detayı** / **telemetri + skills modül sorumlulukları (tam metin)** / cache / TL;DR → **`docs/MIMARI.md`**
- Tam endpoint kataloğu (~80) → **`docs/ENDPOINTS.md`**
- Auth / CSRF / güvenlik / dağıtım / onboarding → **`docs/GUVENLIK-DAGITIM.md`**
- Faz / değişiklik geçmişi → **`docs/DEGISIKLIK-GECMISI.md`** (özet index + son işler); eski işlerin tam metni → **`docs/DEGISIKLIK-ARSIV.md`**
- Belirli iş mantığı → ilgili tek `skills/<modül>.py` (önce o dosyayı oku, base.py'yi sadece gerekirse).

## CLAUDE.md / docs bakımı (zorunlu)
Dosya yapısı, skill sorumluluğu, endpoint, sabit/limit/model, prompt, workflow veya hard kural değişince
ilgili `docs/*` + bu özeti aynı/takip commit'inde güncelle. Sadece CSS/typo atlanabilir.
`.claude/hooks/post-commit-reminder.py` hatırlatır; nihai sorumluluk Claude'da.
