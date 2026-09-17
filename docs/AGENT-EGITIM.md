# Agent Eğitimi — MBS (Merkezi Bahis) Domain Yol Haritası

> **Canlı doküman.** Bu, agent'ı spor bahsi / merkezi bahis domain'i için sürekli
> iyileştirme (context-engineering) çalışmasının yol haritası + kürasyon günlüğüdür.
> Araya bug/iyileştirme işleri girse de bu çalışma **kaldığı yerden** devam eder.
> Her tur: yapılanı "Kürasyon Günlüğü"ne işle, "Sıradaki iş"i güncelle.

## 0. Temel ilke — "eğitim" değil, kürasyon

Model (Claude Opus) fine-tune EDİLMİYOR. Doküman yüklemek modeli eğitmez. Çıktı
kalitesini belirleyen tek şey **inference anında kurulan bağlam + talimat**. Bu iyi
haber: ML/bütçe gerektirmez, tamamen bizim kontrolümüzdeki dosya + kurallarla ilerler.

**Üç kaldıraç:**
1. **Talimat katmanı** — prompt zinciri: ekran Özel Prompt > `reference/prompts.json` (skill override, gitignore/makine-yerel) > `VARSAYILAN_PROMPTLAR` (base.py) → + `_ORTAK_EK_KURALLAR` + **`reference/domain-kurallari.md`** (yeni, aşağı bak).
2. **Kaynak katmanı (RAG)** — kanonik öncelik: `Swagger > Canlı Uygulama > Confluence > BRD/Süreç > Jira > UI`.
3. **Retrieval** — `context_filter` keyword/sayfa seçimi neyin çekileceğini belirler (BM25).

## 1. Durum tablosu (2026-09-17)

| Kaldıraç | Yol | Durum | Sahip |
|---|---|---|---|
| Domain kuralları + sözlük | `reference/domain-kurallari.md` (tracked) | ✅ mekanizma kuruldu, **doldurulacak** | Owner doldurur |
| Skill prompt override | `reference/prompts.json` (gitignore) | `{}` — opsiyonel, fork riskli, önerilmez | — |
| Swagger/OpenAPI | `reference/services/` (gitignore) | ❌ boş | Owner/MCP |
| Confluence corpus | `reference/confluence/` (gitignore) | ⚠️ tek PDF; **MBS El Kitabı** hazırlanıyor | Owner |
| Jira export + yorumlar | `reference/jira/` + `context_filter.jira_keys` | ❌ boş (mekanizma çalışıyor) | Owner |
| Canlı uygulama gözlemi | `context_filter.live_app` | ✅ yapılandırılmış (dev-sky-panel) | Owner |
| Few-shot (onaylı+task) | `reference/ornekler/` (öneri) | ❌ hat yok (history budanıyor + task-linkage yok) | Kod + owner |

## 2. Domain kuralları dosyası — `reference/domain-kurallari.md`

**Kuruldu ve devrede.** MBS'ye özgü terminoloji + iş kuralları + değişmezler (invariants)
buraya yazılır; `skills/base.py → _domain_kurallari_oku()` bunu HER analiz promptuna
(süreç/teknik/BRD/kapsam/Jira + özel-prompt yolları) otomatik ekler.

- **Git'te İZLENİR** → pull ile tüm ekibe iner (ortak domain bilgisi).
- **PII/sır YASAK.** Yalnız kural + terminoloji. Gerçek veri (tablo dökümü, örnek satır,
  Kafka payload, endpoint listesi) buraya DEĞİL → RAG corpus'una (`confluence/`, `services/`).
- **Güvenli varsayılan:** `<!-- KURALLAR-BASLANGIC -->` işaretinden sonrası boş/yorum iken
  hiçbir şey enjekte edilmez → doldurana kadar davranış değişmez.
- Doldurduktan sonra **Yeniden Başlat** (backend taze okusun).

Önerilen bölümler: (1) Terim Sözlüğü TR/EN, (2) Domain Değişmezleri, (3) Süreç/Durum
kuralları, (4) Kaynak/İsimlendirme notları. Şablon dosyanın içinde örneklerle var.

## 3. MBS El Kitabı (Confluence) — corpus spesifikasyonu

El kitabı `reference/confluence/`'a girecek ana RAG kaynağı. **Retrieval BM25 →
atomik, başlıklı bölümler** (tek dev anlatı değil); tablo/kolon/topic adları düz
metinde geçsin. İçerik checklist'i:

- [ ] **Domain model / ontoloji** — entity tanımları + ilişkiler (event, program, market, selection, oran, kupon/kupon kalemi, bet, settlement, wallet, sales open/closed, cashout, void/refund, risk/limit).
- [ ] **DB şeması** (altın değer) — her tablo → amaç · kolonlar (tip+anlam+kısıt) · PK/FK · **örnek satırlar** · hangi süreçte yazılır/okunur.
- [ ] **Kafka topics** — topic → amaç · producer/consumer · mesaj şeması (alan+tip) · **örnek mesaj** · tetikleyen olay · sıralama/idempotency garantileri.
- [ ] **Süreç akışları / state machine** — kupon yaşam döngüsü, settlement, sales open→closed geçişleri (izinli/yasak durumlar).
- [ ] **İş kuralları & değişmezler** — para/yuvarlama, void/refund, limit/risk, idempotency.
- [ ] **Ekran → veri eşlemesi** — MCP ile gezilen ekranların JSON'ları; hangi ekran hangi API/tabloyu kullanıyor (izlenebilirlik).
- [ ] **Terim sözlüğü** (TR/EN) — kısa kritik terimler `domain-kurallari.md`'ye de kopyalanır.

**Ayrı referans dokümanları** (`reference/services/`, gitignore, en yüksek fayda):
- [ ] Servislerin OpenAPI/Swagger dosyaları (kanonik #1 kaynak).
- [ ] Kritik SQL şema/DDL dump'ı.
- [ ] Örnek gerçek Kafka payload'ları.

## 4. Swagger vs MCP — ikisi birden

MCP canlı bağlantı, Swagger'ı ELEMİYOR; TAMAMLIYOR. Swagger = deterministik, 0-token,
tam sözleşme baseline (`reference/services/`). MCP (`skills/analiz_mcp.py`, şu an KAPALI)
= canlı doğrulama + boşluk doldurma, ama tur/kota harcar ve tekrarlanabilir değil.
**Hedef:** app bir `swagger.json` serve ediyorsa periyodik `reference/services/`'e çek;
MCP de üstüne gerçek davranışı doğrulasın.

## 5. Few-shot — onaylı + task açılmış analizler

En yüksek sinyal (analist onayı + task açılması = çift doğrulama). **Ama iki engel:**
1. `history/` `HISTORY_LIMIT=5` ile budanıyor → kalıcı arşiv yok. İyi olanlar budanmadan
   küratörlü `reference/ornekler/`'e (gitignore) terfi edilmeli.
2. `history/meta.json`'da task-linkage YOK ("task açıldı mı / hangi key" bilinmiyor).
   → Küçük kod eklentisi: FE/BE/hiyerarşi task'ları açılınca history meta'ya açılan
   key'leri damgala.

**İlke:** ham çıktı gerçek endpoint/tablo/olası PII içerir → `domain-kurallari.md`'ye
birebir KONMAZ. Few-shot yapısal iskelet olarak damıtılır (derinlik/yapı/kaynak disiplini).

## 6. Süreklilik modeli

- **Git'te (paylaşılır, kalıcı):** `reference/domain-kurallari.md`, `docs/AGENT-EGITIM.md`.
- **Gitignore corpus (yerel/PII):** `reference/{services,confluence,jira,ornekler}/`.
- **Claude hafızası:** `mbs-egitim-girisimi` memory → her gelecek oturum kaldığı yerden devam eder.
- **Ritim:** her tekrar eden düzeltme → `domain-kurallari.md`'ye kural terfi; periyodik kürasyon turu.

## 7. Sıradaki iş

1. **Owner:** `domain-kurallari.md`'yi doldur (terim sözlüğü + ilk değişmezler) → Yeniden Başlat.
2. **Owner:** MBS El Kitabı'nı Confluence'ta bitir → `reference/confluence/`'a al; Swagger'ı `reference/services/`'e koy.
3. **Agent:** history meta'ya task-linkage ekle + `reference/ornekler/` few-shot hattını kur (owner onayıyla).
4. **Agent:** corpus geldikçe `domain-kurallari.md`'yi corpus'a atıfla zenginleştir.

## Kürasyon Günlüğü

- **2026-09-17** — Yol haritası + `reference/domain-kurallari.md` mekanizması kuruldu
  (`_domain_kurallari_oku` → tüm analiz promptlarına otomatik enjeksiyon; şablonken no-op).
  Teşhis: prompts.json boş + gitignore, services/jira boş, confluence tek PDF. Memory yazıldı.
