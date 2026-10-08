# Merkezî Sink — Google Apps Script (kullanım telemetrisi + ortak örnek havuzu)

Analistlerin lokal Analyst Studio'ları iki şey gönderir:
1. **Kullanım olayları** (yalnız metadata — BRD/analiz içeriği YOK) → owner raporu.
2. **Onaylı/kaliteli analiz ÖRNEKLERİ** (içerikle) → **ortak few-shot havuzu**: her analistin
   agent'ı diğerlerinin kaliteli analizinden öğrenir (`ornekleri_cek` ile günlük iner).

> **Örnek havuzu, analiz İÇERİĞİNİ merkeze taşır** (owner'ın bilinçli kararı). Sheet senin
> Google hesabında; yazma herkese açık, okuma kapıdan geçer (aşağıda).

---

## 1. Google Sheet
https://sheets.google.com → yeni boş sheet (ör. **"Analyst Studio"**). Sheet sende kalır.
Sekmeler script tarafından otomatik açılır: ilk sekme = **kullanım**, **"Ornekler"** = örnek havuzu.

## 2. Apps Script — TAM KOD (mevcut içeriği SİL, bunu yapıştır)

**Uzantılar → Apps Script** → editöre:

```javascript
// ===================== YAPILANDIRMA (sadece bu 4 satırı düzenle) =====================
const OKUMA_ANAHTARI = 'BURAYA-UZUN-RASTGELE-ANAHTAR';          // owner .env USAGE_SINK_KEY ile AYNI
const SIRKET_DOMAIN  = 'sans-technology.com';                   // örnek çekebilen e-posta domaini (tüm ekip)
const OWNER_EMAILS   = ['ugur.cangir@sans-technology.com'];     // EKİP KULLANIM raporunu çekebilenler
const YAZMA_TOKEN    = '';                                      // opsiyonel: doluysa POST'ta ?t=<token> beklenir
// =====================================================================================

const _KULLANIM_BAS = ['ts','analist','olay','durum','sure_ms','model','ai_modu',
                       'jira_toplam','proje','dokuman','makine','app_versiyon'];
const _ORNEK_BAS    = ['ts','id','tip','analist','eposta','proje','jira_key','ozet','icerik'];

function _kullanimSheet() {
  // Mevcut veriyi KORU: ilk sekme kullanım verisidir (adı ne olursa olsun).
  const sh = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
  if (sh.getLastRow() === 0) sh.appendRow(_KULLANIM_BAS);
  return sh;
}
function _ornekSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName('Ornekler');
  if (!sh) { sh = ss.insertSheet('Ornekler'); sh.appendRow(_ORNEK_BAS); }
  if (sh.getLastRow() === 0) sh.appendRow(_ORNEK_BAS);
  return sh;
}
function _json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
         .setMimeType(ContentService.MimeType.JSON);
}
function _emailDomainOk(em) {
  em = (em || '').toString().toLowerCase().trim();
  return em.indexOf('@') !== -1 && em.slice(-(SIRKET_DOMAIN.length + 1)) === ('@' + SIRKET_DOMAIN);
}
function _ownerOk(p) {
  if (p.read && p.read === OKUMA_ANAHTARI) return true;
  const em = (p.email || '').toString().toLowerCase().trim();
  return OWNER_EMAILS.map(function (x) { return x.toLowerCase(); }).indexOf(em) !== -1;
}

function doPost(e) {
  try {
    if (YAZMA_TOKEN && (!e.parameter || e.parameter.t !== YAZMA_TOKEN)) {
      return ContentService.createTextOutput('forbidden');
    }
    const o = JSON.parse((e.postData && e.postData.contents) || '{}');

    // --- Örnek (few-shot içerikli) → ayrı 'Ornekler' sekmesi, id ile tekilleştir ---
    if (o.olay === 'ornek') {
      const sh = _ornekSheet();
      if (o.id && sh.getLastRow() > 1) {
        const ids = sh.getRange(2, 2, sh.getLastRow() - 1, 1).getValues();
        for (var i = 0; i < ids.length; i++) {
          if (ids[i][0] === o.id) return ContentService.createTextOutput('dup');
        }
      }
      sh.appendRow([o.ts || '', o.id || '', o.tip || '', o.analist || '', o.eposta || '',
                    o.proje || '', o.jira_key || '', o.ozet || '', o.icerik || '']);
      return ContentService.createTextOutput('ok');
    }

    // --- Kullanım olayı (yalnız metadata) → ilk sekme ---
    const sh = _kullanimSheet();
    const jira = o.jira && typeof o.jira === 'object' ? (o.jira.toplam || 0) : '';
    const baglam = o.baglam || {};
    sh.appendRow([o.ts || '', o.analist || '', o.olay || '', o.durum || '', o.sure_ms || '',
                  o.model || '', o.ai_modu || '', jira,
                  baglam.proje || '', baglam.dokuman || '', o.makine || '', o.app_versiyon || '']);
    return ContentService.createTextOutput('ok');
  } catch (err) {
    return ContentService.createTextOutput('error');
  }
}

function doGet(e) {
  const p = (e && e.parameter) || {};

  // --- Örnek havuzu çekme: TÜM şirket analistleri (domain) + owner ---
  if (p.ornekler) {
    if (!(_emailDomainOk(p.email) || (p.read && p.read === OKUMA_ANAHTARI))) {
      return _json({ error: 'forbidden' });
    }
    const sh = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Ornekler');
    if (!sh || sh.getLastRow() < 2) return _json([]);
    const veri = sh.getDataRange().getValues();
    const bas = veri.shift();
    const out = veri.map(function (r) { const o = {}; bas.forEach(function (k, i) { o[k] = r[i]; }); return o; });
    return _json(out);
  }

  // --- Ekip kullanım raporu: owner (read anahtarı VEYA owner e-posta) ---
  if (!_ownerOk(p)) return ContentService.createTextOutput('forbidden');
  const sh = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
  if (!sh || sh.getLastRow() < 2) return _json([]);
  const veri = sh.getDataRange().getValues();
  const bas = veri.shift();
  const olaylar = veri.map(function (r) {
    const o = {}; bas.forEach(function (k, i) { o[k] = r[i]; });
    return { ts: o.ts, analist: o.analist, olay: o.olay, durum: o.durum,
             sure_ms: o.sure_ms, model: o.model, ai_modu: o.ai_modu,
             jira: { toplam: o.jira_toplam || 0 },
             baglam: { proje: o.proje, dokuman: o.dokuman },
             makine: o.makine, app_versiyon: o.app_versiyon };
  });
  return _json(olaylar);
}
```

**Doldur:** `OKUMA_ANAHTARI` (uzun rastgele; owner `.env` `USAGE_SINK_KEY` ile birebir aynı) ·
`OWNER_EMAILS` (kullanım raporunu çekecek owner e-posta(ları)) · `SIRKET_DOMAIN` (ekip domaini —
bu domainli her analist ÖRNEK çeker, kullanım raporunu çekemez).

## 3. Yayınla (URL'yi DEĞİŞTİRMEDEN güncelle)
- **İlk kez:** Dağıt → Yeni dağıtım → tür **Web uygulaması** → "çalıştır: ben" · "erişim: Herkes" → Dağıt → **Web App URL**'ini al.
- **Zaten varsa (URL korunur):** Dağıt → **Dağıtımları yönet** → kalem (düzenle) → **Sürüm: Yeni sürüm** → Dağıt.
  URL AYNI kalır → analistlerde hiçbir değişiklik gerekmez (kod zaten o URL'e yazıyor).

> Web App URL kodda gömülü (`skills/telemetri.py → VARSAYILAN_SINK_URL`). Farklıysa owner
> `.env`'de `USAGE_SINK_URL=` ile override eder; URL'yi değiştirdiysen gömülüyü de güncelle.

## 4. Owner `.env` (yalnız sen)
```
USAGE_DASHBOARD=true
USAGE_SINK_URL=<Web App URL>
USAGE_SINK_KEY=<OKUMA_ANAHTARI ile aynı>
```
Yeniden başlat → **Kullanım Raporu**'nda **Uzaktan Çek** (ekip metadata) + **Örnek Havuzu** paneli
(few-shot durumu + "Şimdi Çek").

## 5. Analistler — hiçbir şey yapmaz
- **Kullanım:** zaten gönderiyorlar (metadata). Değişiklik yok.
- **Örnek havuzu:** güncelleme (AUTO_UPDATE) yeni client kodunu çeker → **günlük oto-sync**
  (`ornekleri_cek`) sink'ten örnekleri `reference/ornekler/`'e indirir → sonraki analizlerde
  few-shot olarak prompt'a girer. Elle: Ayarlar/Referanslar → Güncelle. Ek `.env` GEREKMEZ.

## Nasıl çalışır (özet)
`Analist onaylar / Jira'ya yazar` → `ornek_kaydet` → (a) yerel `reference/ornekler/`, (b) sink
'Ornekler' sekmesi (push). `ornekleri_cek` (günlük + elle) → sink'ten `?ornekler=1&email=<domain>` ile
TÜM örnekleri indirir. `ornek_bloklari` → her süreç/teknik/görev analizinde EN ALAKALI 2 örneği
(BM25) "ONAYLI ÖRNEK — stil/derinlik referansı" olarak prompt'a enjekte eder. Havuz ≤80 (en yeni),
örnek başına ≤45k (Sheet hücre limiti).

## Notlar
- Kullanım olaylarında içerik YOK. Örnek havuzunda İÇERİK var (bilinçli) — Sheet owner'da, çekme
  domain/owner kapılı.
- Transport başarısız olursa (ağ yok) kullanım olayı lokal `logs/usage/events.jsonl`'de kalır; örnek
  yereli yine dolar.
- Kötü/eski örnek: Kullanım Raporu → Örnek Havuzu → Sil (yerel); merkezden kalıcı silmek için
  'Ornekler' sekmesinden satırı sil.
