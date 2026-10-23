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

### UAT / izin-dışı board örneklerini merkezden temizle (owner 2026-10-23)
Uygulama tarafı artık UAT (`MBSUATEAM`) ve trade/ops dışı board örneklerini few-shot havuzuna SOKMUYOR
(yakalama + çekme + enjeksiyonda elenir — `ornek_havuzu._egitime_uygun_mu`), bu yüzden Sheet'teki eski satırlar
ZARARSIZ. Yine de kalıcı temizlemek istersen: Apps Script editöründe aşağıdaki fonksiyonu bir kez **Run** et
(web deploy GEREKMEZ; `jira_key` projesi izin listesinde olmayan satırları — keysiz/doküman satırlarını KORUYARAK — siler):

```javascript
// Tek seferlik bakım — 'Ornekler' sekmesinden izin-dışı board (UAT vb.) örneklerini siler.
// İzinli: MBSTRADE, MBSOPS + keysiz (doküman). Çalıştır: editörde seç → Run. Geri alınamaz (önce File → Make a copy önerilir).
function temizleUatOrnekleri() {
  var IZINLI = ['MBSTRADE', 'MBSOPS'];           // trade + ops; gerekirse ekle
  var osh = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Ornekler');
  if (!osh || osh.getLastRow() < 2) { Logger.log('Ornekler boş'); return; }
  var basliklar = osh.getRange(1, 1, 1, osh.getLastColumn()).getValues()[0];
  var kol = basliklar.indexOf('jira_key');        // G sütunu (0-tabanlı index)
  if (kol < 0) { Logger.log('jira_key sütunu yok'); return; }
  var veri = osh.getRange(2, 1, osh.getLastRow() - 1, osh.getLastColumn()).getValues();
  var silinecek = 0;
  for (var i = veri.length - 1; i >= 0; i--) {     // alttan yukarı → satır indeksleri kaymaz
    var jk = (veri[i][kol] || '').toString().trim();
    if (!jk) continue;                             // keysiz (doküman) → KORU
    var proje = jk.split('-')[0].toUpperCase();
    if (proje === 'EKRAN') continue;               // sentetik → zaten girmez, dokunma
    if (IZINLI.indexOf(proje) === -1) { osh.deleteRow(i + 2); silinecek++; }
  }
  Logger.log('Silinen izin-dışı örnek: ' + silinecek);
}
```
Hızlı alternatif (manuel): 'Ornekler' sekmesi → `jira_key` (G) sütununa filtre → `MBSUATEAM`/`CORE`… satırlarını seç → sil.

## Token tüketimi ekip verisinde (2026-10-19) — script değişikliği GEREKMEZ
Script yalnız yukarıdaki sütunları sakladığından `token` alanı düşüyordu (ekip verisinde token hep boştu). Uygulama artık
token özetini `dokuman` sütununa `⟨tok g=…,c=…,cy=…,co=…,n=…,usd=…⟩` olarak gömer; Uzaktan Çek bunu geri ayrıştırıp
dokümandan siler. Sheet'te `dokuman` hücresinde bu işaret görünür (zararsız). İsteğe bağlı temiz yol: `_basliklar`'a
`'girdi','cikti','cache_yaz','cache_oku','cagri','maliyet_usd'` sütunlarını ekleyip `doPost`'ta `o.token||{}` alanlarını
yazmak ve `doGet`'te `token:{…}` döndürmek — o zaman uygulama `token` alanını doğrudan kullanır (gömme yine zararsız kalır).

## Güvenlik sertleştirme (2026-10-20 denetimi) — script tarafı değişiklikleri
Mevcut kod iki zayıflık taşır: (a) `doPost` tokensiz çalışırken Web App URL'ini bilen HERKES Sheet'e satır/örnek
yazabilir; (b) `doGet` örnek çekmede `_domainMi` kapısı yalnız `?email=…@sans-technology.com` dizesine bakar —
e-posta DOĞRULANMAZ, domain tahmin edilebilir → örnek içeriği (analiz metni) dışarı sızabilir. Önerilen değişiklikler
(client tarafı **geri uyumlu**: token boşken eski davranış):

1. **Paylaşılan sır HEM `doGet` HEM `doPost` için zorunlu** (Apps Script header okuyamaz → header'sız taşınır:
   GET'te `?t=<sır>` parametresi, POST'ta gövde alanı `t`). Client `.env` `USAGE_SINK_TOKEN=<sır>` ile aynı değeri
   POST gövdesine (`t`) ve GET isteklerine (`?t=`) otomatik ekler (`telemetri._yazma_token`).
   ```javascript
   const PAYLASILAN_SIR = 'BURAYA-UZUN-RASTGELE-SIR';     // owner .env USAGE_SINK_TOKEN ile aynı
   function _sirOk(p, o) { return PAYLASILAN_SIR && ((p && p.t === PAYLASILAN_SIR) || (o && o.t === PAYLASILAN_SIR)); }
   // doPost başı:  const o = JSON.parse(e.postData.contents || '{}');
   //               if (!_sirOk(e.parameter, o)) return ContentService.createTextOutput('forbidden');
   //               delete o.t;   // sır Sheet'e yazılmasın
   // doGet başı:   if (!_sirOk(p, null)) return ContentService.createTextOutput(JSON.stringify({error:'Yetkisiz'})).setMimeType(ContentService.MimeType.JSON);
   ```
2. **`_domainMi` okuma kapısını KALDIR** — domain soneki tahmin edilebilir. Örnek çekme (`?ornekler=1`) ve kullanım
   raporu YALNIZ `Owners` listesindeki e-posta **VE** paylaşılan sır ile açılır:
   ```javascript
   // doGet — ornekler: if (!(_ownerMi(p.email) || p.read === OKUMA_ANAHTARI)) → Yetkisiz   (artık _domainMi YOK)
   ```
   Ekip few-shot dağıtımı için (owner olmayan analistlerin örnek çekmesi) `Owners` yerine ayrı bir **`Analistler`**
   sekmesi (A sütunu e-posta) tutulup `_listedeMi('Analistler', p.email)` ile kontrol edilebilir — ama bu da yalnız
   sırla birlikte (madde 1) anlamlıdır; e-posta tek başına kimlik DEĞİLDİR.
3. **Token sütunları opsiyonel:** `_basliklar`'a `'girdi','cikti','cache_yaz','cache_oku','cagri','maliyet_usd'` eklenip
   `doPost`'ta `(o.token||{}).girdi …` yazılabilir; eklenmezse uygulama `dokuman` sütunundaki `⟨tok …⟩` gömmesiyle
   çalışmaya devam eder (yukarıdaki bölüm). Sır alanı `t` ASLA sütun olarak saklanmaz.

**Okuma anahtarı (`?read=`) hakkında:** client şimdilik GET sorgu dizesinde gönderir (Apps Script header
okuyamadığı için). Sorgu dizesi proxy/erişim loglarına düşebilir → script `op:"read"` POST'u destekleyince anahtar
gövdeye taşınacak (client değişikliği: `uzaktan_cek`/`ornekleri_cek`/`tani` tek yerde). Bu geçişe kadar client hata
mesajlarına URL/sorgu dizesini KOYMAZ (yalnız istisna türü + ipucu).

**Dağıtım sırası (güncel — owner kararı 2026-10-20, analist dokunmaz):** sır `reference/ekip_sink_token.json` (TRACKED) dosyasında;
(1) owner dosyadaki değeri Apps Script `PAYLASILAN_SIR`'a kopyalayıp yeni sürüm dağıtır (URL aynı), (2) commit+push → analistler
güncellemeyle alır (`.env` gerekmez; env `USAGE_SINK_TOKEN` varsa dosyayı ezer). Eski yol (`.env`) da çalışır.
Token dağıtılana kadar script'te `PAYLASILAN_SIR=''` bırakılırsa `_sirOk` false döner → **yazma durur**; bu yüzden
sırrı önce dağıt, sonra script'e koy (ya da `_sirOk`'u `!PAYLASILAN_SIR || …` ile geçici gevşet).
