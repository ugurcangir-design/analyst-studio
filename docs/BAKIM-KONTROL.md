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

### <!-- TARIH --> — İlk kapsamlı denetim (bu oturumda başlatıldı)
_Bulgular denetim ajanları tamamlanınca sentezlenip buraya önceliklendirilerek eklenecek._

- **P0 (bozuk/riskli):** _(doldurulacak)_
- **P1 (önemli):** _(doldurulacak)_
- **P2 (iyileştirme):** _(doldurulacak)_
- **Tasarım önerileri (UI):** _(gerçek uygulama örnekleriyle — doldurulacak)_
