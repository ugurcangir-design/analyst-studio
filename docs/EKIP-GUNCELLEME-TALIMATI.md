# Analyst Studio — Tek Seferlik Güncelleme Talimatı (ekip)

> **Neden?** Depo geçmişi bir kez temizlendi (gizli/kişisel veri kaldırma). Bu temizlikten
> **önce** klonlayanlarda güncelleme "push edilmemiş commit / ıraksama / Repository not found"
> hatası verir. Aşağıdaki **tek seferlik** adımlar herkesi güncel sürüme getirir. Sonrasında
> normal **Güncelleme → Güncelle** düğmesi sorunsuz çalışır.
>
> `.env` ve `reference/` ayarlarınız (Jira bağlantısı, kimlik vb.) **korunur** — bunlar git'e dahil değildir.

---

## 1. Uygulamanın çalıştığı klasörü bulun

Terminali açın ve şunu yapıştırın (makinedeki tüm klonları + sürümlerini listeler):

```bash
for d in ~/analyst-studio* ~/projects/analyst-studio* ~/brd-analyst-agent* ~/Documents/analyst-studio* ~/Desktop/analyst-studio*; do [ -d "$d/.git" ] && echo "$d → $(git -C "$d" log -1 --format='%h · %ci' 2>/dev/null)"; done
```

- Tek satır çıkarsa: o klasörü kullanın.
- Birden fazla çıkarsa: **eski tarihli** olanı da düzeltmeniz gerekir (uygulama genelde ondan çalışır).
  Kesin bulmak için, **uygulama açıkken**: `lsof -nP -iTCP:5003 -sTCP:LISTEN` → çıkan PID ile
  `lsof -p <PID> | grep cwd` → `cwd` satırındaki klasör uygulamanın gerçek dizinidir.

## 2. O klasöre girip güncel sürümle eşitleyin

Her düzeltilecek klasör için (yolun tamamıyla):

```bash
cd "<klasör yolu>"
git remote set-url origin https://github.com/ugurcangir-design/analyst-studio.git
git remote -v
git fetch origin && git reset --hard origin/main
```

**Kontroller:**
- `git remote -v` çıktısı **`https://github.com/ugurcangir-design/analyst-studio.git`** olmalı
  (`git@…` SSH DEĞİL, `Analysys_Agent` DEĞİL).
- Son satır **`HEAD is now at <hash> …`** derse eşitleme başarılıdır.

## 3. Uygulamayı yeniden başlatın

**Analyst Studio.app**'i tamamen kapatıp yeniden açın (veya uygulama içinde **Güncelleme → Yeniden Başlat**).

## 4. Doğrulama

Uygulama açılınca **sol üstteki sürüm** güncel hash'i göstermeli ve:
- "… commit geride / ıraksama / push edilmemiş commit" **banner'ı kaybolur**,
- Jira Köprüsü'ndeki "Liste alınamadı" **hatası kaybolur**.

---

## Sık karşılaşılanlar

| Belirti | Çözüm |
|---|---|
| `Username for 'https://github.com'` soruyor | Remote yanlış (eski isim/SSH). Adım 2'deki `set-url`'i çalıştırın; depo public, doğru HTTPS ile kimlik sorulmaz. |
| `ERROR: Repository not found` | Remote `Analysys_Agent` veya `git@…` olarak ayarlı. Adım 2'deki doğru HTTPS URL ile düzeltin. |
| Terminal güncelledi ama uygulama eski | Birden fazla klon var; uygulama farklı klasörden çalışıyor. Adım 1 ile bulup o klasörü de eşitleyin. |
| `zsh: invalid mode specification` | `git remote -v` çıktısını yanlışlıkla komut olarak yapıştırmışsınız — zararsız, yok sayın. |

**Öneri:** Karışıklığı bitirmek için makinede **tek klon** bırakın; uygulama kısayolunu (Analyst Studio.app)
o klasörden `bash create_app.sh` ile yeniden oluşturun.
