# Merkezî Sink — Google Apps Script (kullanım telemetrisi + ortak örnek havuzu)

Analistlerin lokal Analyst Studio'ları iki şey gönderir:
1. **Kullanım olayları** (yalnız metadata — BRD/analiz içeriği YOK) → owner raporu.
2. **Kaliteli analiz ÖRNEKLERİ** (içerikle) → **ortak few-shot havuzu**: her analistin agent'ı
   diğerlerinin onaylı/Jira'ya yazılmış analizinden öğrenir (`ornekleri_cek` günlük indirir).

Sheet senin Google hesabında. **Owner yetkisi 'Owners' sekmesinden** (A sütunu e-posta listesi)
okunur → owner eklemek için redeploy gerekmez. Örnek ÇEKME ise tüm **şirket domaini** (@sans-technology.com)
analistlerine açıktır (ortak dağıtım için). Örnek sekmesi = **'Ornekler'**, veri sekmesi = ilk (Owners/Ornekler olmayan) sekme.

## Tam kod (Uzantılar → Apps Script → yapıştır)

```javascript
const OKUMA_ANAHTARI = 'BURAYA-UZUN-RASTGELE-ANAHTAR';   // owner .env USAGE_SINK_KEY ile aynı (geri-uyum)
const SIRKET_DOMAIN  = 'sans-technology.com';            // örnek çekme: bu domainli HER analist
const YAZMA_TOKEN    = '';                               // opsiyonel: doluysa POST'ta ?t=<token>

// Veri sayfası = 'Owners' ve 'Ornekler' OLMAYAN ilk sayfa (sekmeler başa taşınsa da veri bozulmaz)
function _sheet() {
  var shs = SpreadsheetApp.getActiveSpreadsheet().getSheets();
  for (var i = 0; i < shs.length; i++) {
    var ad = shs[i].getName();
    if (ad !== 'Owners' && ad !== 'Ornekler') return shs[i];
  }
  return shs[0];
}
function _basliklar(sh) {
  if (sh.getLastRow() === 0) {
    sh.appendRow(['ts','analist','olay','durum','sure_ms','model','ai_modu',
                  'jira_toplam','proje','dokuman','makine','app_versiyon']);
  }
}
function _ornekSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName('Ornekler');
  if (!sh) sh = ss.insertSheet('Ornekler');
  if (sh.getLastRow() === 0) {
    sh.appendRow(['ts','id','tip','analist','eposta','proje','jira_key','ozet','icerik']);
  }
  return sh;
}
// 'Owners' sekmesindeki (A sütunu) e-posta listesinde mi? → owner-rolü okuma
function _ownerMi(email) {
  email = (email || '').toString().trim().toLowerCase();
  if (!email) return false;
  var sh = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Owners');
  if (!sh || sh.getLastRow() < 1) return false;
  var vals = sh.getRange(1, 1, sh.getLastRow(), 1).getValues();
  for (var i = 0; i < vals.length; i++) {
    if ((vals[i][0] || '').toString().trim().toLowerCase() === email) return true;
  }
  return false;
}
function _domainMi(email) {
  email = (email || '').toString().trim().toLowerCase();
  return email.indexOf('@') !== -1 &&
         email.slice(-(SIRKET_DOMAIN.length + 1)) === ('@' + SIRKET_DOMAIN);
}

function doPost(e) {
  try {
    if (YAZMA_TOKEN && (!e.parameter || e.parameter.t !== YAZMA_TOKEN)) {
      return ContentService.createTextOutput('forbidden');
    }
    const o = JSON.parse(e.postData.contents || '{}');

    // Few-shot örneği (içerikli) → ayrı 'Ornekler' sekmesi, id-dedup
    if (o.olay === 'ornek') {
      var osh = _ornekSheet();
      if (o.id && osh.getLastRow() > 1) {
        var ids = osh.getRange(2, 2, osh.getLastRow() - 1, 1).getValues();
        for (var k = 0; k < ids.length; k++) {
          if (ids[k][0] === o.id) return ContentService.createTextOutput('dup');
        }
      }
      osh.appendRow([o.ts||'', o.id||'', o.tip||'', o.analist||'', o.eposta||'',
                     o.proje||'', o.jira_key||'', o.ozet||'', o.icerik||'']);
      return ContentService.createTextOutput('ok');
    }

    // Kullanım olayı (yalnız metadata) → veri sekmesi
    const sh = _sheet(); _basliklar(sh);
    const jira = o.jira && typeof o.jira === 'object' ? (o.jira.toplam || 0) : '';
    const baglam = o.baglam || {};
    sh.appendRow([o.ts||'', o.analist||'', o.olay||'', o.durum||'', o.sure_ms||'',
                  o.model||'', o.ai_modu||'', jira,
                  baglam.proje||'', baglam.dokuman||'', o.makine||'', o.app_versiyon||'']);
    return ContentService.createTextOutput('ok');
  } catch (err) {
    return ContentService.createTextOutput('error');
  }
}

function doGet(e) {
  var p = (e && e.parameter) ? e.parameter : {};

  // Örnek havuzu çekme: şirket domaini VEYA owner VEYA okuma anahtarı → tüm analistler iner
  if (p.ornekler) {
    if (!(_domainMi(p.email) || _ownerMi(p.email) || p.read === OKUMA_ANAHTARI)) {
      return ContentService.createTextOutput(JSON.stringify({error: 'Yetkisiz'}))
             .setMimeType(ContentService.MimeType.JSON);
    }
    var osh = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Ornekler');
    if (!osh || osh.getLastRow() < 2) {
      return ContentService.createTextOutput('[]').setMimeType(ContentService.MimeType.JSON);
    }
    var ov = osh.getDataRange().getValues();
    var ob = ov.shift();
    var out = ov.map(function(r) { var o = {}; ob.forEach(function(k, i) { o[k] = r[i]; }); return o; });
    return ContentService.createTextOutput(JSON.stringify(out))
           .setMimeType(ContentService.MimeType.JSON);
  }

  // Ekip kullanım raporu: (1) okuma anahtarı [geri-uyum] VEYA (2) e-posta Owners listesinde
  var yetkili = (p.read === OKUMA_ANAHTARI) || _ownerMi(p.email);
  if (!yetkili) {
    return ContentService.createTextOutput(JSON.stringify({error: 'Yetkisiz: e-posta owner listesinde degil'}))
           .setMimeType(ContentService.MimeType.JSON);
  }
  const sh = _sheet();
  const veri = sh.getDataRange().getValues();
  const bas = veri.shift() || [];
  const olaylar = veri.map(function(r) {
    const o = {}; bas.forEach(function(k, i) { o[k] = r[i]; });
    return {ts:o.ts, analist:o.analist, olay:o.olay, durum:o.durum,
            sure_ms:o.sure_ms, model:o.model, ai_modu:o.ai_modu,
            jira:{toplam:o.jira_toplam||0},
            baglam:{proje:o.proje, dokuman:o.dokuman},
            makine:o.makine, app_versiyon:o.app_versiyon};
  });
  return ContentService.createTextOutput(JSON.stringify(olaylar))
         .setMimeType(ContentService.MimeType.JSON);
}
```

## Yayınla (URL'yi DEĞİŞTİRMEDEN)
Dağıt → **Dağıtımları yönet** → kalem (düzenle) → **Sürüm: Yeni sürüm** → Dağıt. Web App URL
aynı kalır → analistlerde değişiklik gerekmez (client zaten o URL'e yazıyor; URL kodda gömülü:
`skills/telemetri.py → VARSAYILAN_SINK_URL`).

## Owner `.env`
```
USAGE_DASHBOARD=true
USAGE_SINK_URL=<Web App URL>
USAGE_SINK_KEY=<OKUMA_ANAHTARI ile aynı>
```
Yeniden başlat → **Kullanım Raporu**'nda **Uzaktan Çek** (ekip metadata) + **Ortak Eğitim Havuzu**
paneli (few-shot adedi/son çekim + "Şimdi Çek").

## Analistler — hiçbir şey yapmaz
Güncelleme (AUTO_UPDATE) yeni client kodunu çeker → **günlük oto-sync** (`ornekleri_cek`) sink'ten
örnekleri `reference/ornekler/`'e indirir → sonraki süreç/teknik/görev analizinde few-shot olarak girer.

## Akış özeti
`Analist onaylar / görevi Jira'ya yazar` → `ornek_kaydet` → (a) yerel `reference/ornekler/`, (b) sink
'Ornekler' sekmesi (push). `ornekleri_cek` (günlük + "Şimdi Çek") → `?ornekler=1&email=<domain>` ile TÜM
örnekleri indirir. `ornek_bloklari` → her analizde EN ALAKALI 2 örneği (BM25) "ONAYLI ÖRNEK — stil/derinlik"
olarak prompt'a enjekte eder. Havuz ≤80 (en yeni), örnek ≤45k (Sheet hücre limiti). İçerik git'e GİRMEZ
(yalnız sink üzerinden paylaşılır).

## Notlar
- Kullanım olaylarında içerik YOK. Örnek havuzunda İÇERİK var (owner'ın bilinçli kararı) — Sheet owner'da,
  çekme domain/owner/anahtar kapılı.
- Kötü/eski örnek: Kullanım Raporu → Ortak Eğitim Havuzu → (yerel) Sil; merkezden kalıcı silmek için
  'Ornekler' sekmesinden satırı sil.
