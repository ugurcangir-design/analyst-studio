"""
Bölüm-hedefli AI düzenleme — v2 Faz 1 · Artım 2 (bkz. docs/ROADMAP-V2.md).

Analistin "şu bölümü şöyle değiştir" isteğini, TÜM dokümanı yeniden üretmeden
karşılar: yalnız hedef bölümü AI'a gönderir, dönen düzenlenmiş bölümü dokümana
geri yerleştirir (splice) ve sonucu `revizyon.revizyon_oner()` ile ONAY BEKLEYEN
bir öneri olarak kaydeder. Böylece:
  - tek-atış tam yeniden-üretim yok → daha ucuz, daha isabetli, format korunur
  - her düzenleme revizyon geçmişine düşer, analist onaylar/reddeder (belkemiği: revizyon.py)

Bölüm ayırma/splice DETERMİNİSTİKTİR (0 token, test edilir). Yalnız `bolum_duzenle`
içindeki tek AI çağrısı token harcar; test/enjeksiyon için `_ai_fn` parametresiyle
soyutlandı.
"""

import re
from pathlib import Path

from . import revizyon
from .base import _api_cagri, OUTPUT_DIR, MAX_TOKENS_KISA

# Markdown başlık satırı: "## Başlık", "### PA-001: ...", vb.
_BASLIK = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*#*$", re.MULTILINE)

# Bölüm-hedefli düzenleme sistem promptu. TÜM doküman değil, YALNIZ hedef bölüm
# gönderilir; AI aynı başlığı koruyarak yalnız bu bölümü döndürür.
# Not: Faz 2'de UI'dan düzenlenebilir olması için base.VARSAYILAN_PROMPTLAR'a
# taşınabilir; şu an v2-yeni yetenek olduğundan modülde tutuluyor (base.py'ye
# dokunmadan, düşük risk).
REFINE_BOLUM_PROMPT = """# ROL
Bir analiz dokümanının TEK bir bölümünü, analistin talimatına göre cerrahi
hassasiyetle düzenleyen kıdemli analistsin.

# GÖREV
Sana dokümanın YALNIZCA bir bölümü verildi. Analistin talimatını bu bölüme uygula.

# KESİN KURALLAR
- Yalnız verilen bölümü döndür — başka bölüm, giriş/kapanış cümlesi, açıklama EKLEME.
- Bölümün başlık satırını (örn. "## ...", "### PA-001: ...") AYNEN koru.
- Talimatın dokunmadığı satırları KELİMESİ KELİMESİNE koru.
- ID'leri (PA/BR/AC/EK/T-/Q- vb.), tablo yapısını ve Markdown formatını bozma.
- Talimat belirsizse mevcut içeriği bozmadan en yakın makul yorumu uygula.

# ANALİST TALİMATI
{talimat}

# DÜZENLENECEK BÖLÜM
{bolum}

# ÇIKTI
Yalnızca düzenlenmiş bölümün Markdown'ını ver (başlık dahil). Başka hiçbir şey yazma."""


def bolumlere_ayir(md: str) -> list[dict]:
    """Markdown'ı başlıklara göre iç içe olmayan bölümlere ayırır.

    Her bölüm bir başlıkla başlar ve seviyesi <= kendi seviyesi olan bir SONRAKİ
    başlığa kadar sürer (alt başlıklar bölüme dahildir). Başlık öncesi önsöz
    varsa `seviye=0`, `baslik=""` bir giriş bloğu olarak döner.

    Döner: [{indeks, seviye, baslik, baslangic, bitis, icerik}] — `baslangic`/`bitis`
    `md` içinde karakter ofsetleridir (splice için).
    """
    basliklar = [
        {"seviye": len(m.group(1)), "baslik": m.group(2).strip(), "satir_bas": m.start()}
        for m in _BASLIK.finditer(md)
    ]
    bolumler: list[dict] = []

    # Başlıktan önce önsöz (ör. HTML meta yorumu, yönetici özeti) varsa koru
    ilk = basliklar[0]["satir_bas"] if basliklar else len(md)
    if ilk > 0:
        bolumler.append({
            "indeks": 0, "seviye": 0, "baslik": "",
            "baslangic": 0, "bitis": ilk, "icerik": md[:ilk],
        })

    for i, b in enumerate(basliklar):
        bas = b["satir_bas"]
        bitis = len(md)
        for sonraki in basliklar[i + 1:]:
            if sonraki["seviye"] <= b["seviye"]:
                bitis = sonraki["satir_bas"]
                break
        bolumler.append({
            "indeks": len(bolumler), "seviye": b["seviye"], "baslik": b["baslik"],
            "baslangic": bas, "bitis": bitis, "icerik": md[bas:bitis],
        })
    return bolumler


_ID_DESEN = re.compile(r"[A-Za-z]{1,5}-\d{1,4}")


def _anahtar_idleri(anahtar: str) -> list[str]:
    """`anahtar` içindeki yapısal ID token'larını çıkarır (BR-001/BR-006 → [BR-001, BR-006];
    MOCKUP/EK-001 → [EK-001]; başlık metni → [])."""
    return _ID_DESEN.findall(anahtar or "")


def _id_govdede(icerik: str, id_: str) -> bool:
    """ID'yi token olarak arar (komşu harf/rakam/tire yok) → PA-003, PA-0031'e uymaz."""
    return re.search(r"(?<![\w-])" + re.escape(id_) + r"(?![\w-])", icerik, re.IGNORECASE) is not None


def bolum_bul(md: str, anahtar: str) -> dict | None:
    """`anahtar`'a uyan bölüm. `anahtar` bir ID (PA-001), başlık metni veya parçası olabilir.

    İki aşama:
      1. **Başlık eşleşmesi** (en kesin): başlığı `anahtar`'ı içeren İLK bölüm. Teknik
         analizde ID'ler başlıkta (`### T-BE-004: …`) olduğundan burada eşleşir.
      2. **Gövde-içi fallback** (yalnız 1 başarısızsa): `anahtar`'daki ID(ler) bir bölümün
         GÖVDESİNDE satır-içi geçiyorsa (süreç analizinde `**PA-003:** …` deseni — ID başlıkta
         DEĞİL), o ID'yi içeren EN DERİN (en spesifik) bölüm döner. Böylece hedefli düzeltme
         tam-regenerasyona düşmeden çalışır. Başlık metni verilmişse (ID yok) fallback devre dışı.
    """
    hedef = anahtar.strip().casefold()
    if not hedef:
        return None
    bolumler = bolumlere_ayir(md)
    # 1) Başlık eşleşmesi (mevcut davranış, en kesin)
    for b in bolumler:
        if b["seviye"] == 0:
            continue
        if hedef in b["baslik"].casefold():
            return b
    # 2) Gövde-içi fallback: ID'yi içeren en derin (eşitse en kısa) bölüm
    idler = _anahtar_idleri(anahtar)
    if not idler:
        return None
    en_iyi = None
    for b in bolumler:
        if b["seviye"] == 0:
            continue
        if any(_id_govdede(b["icerik"], i) for i in idler):
            if (en_iyi is None
                    or b["seviye"] > en_iyi["seviye"]
                    or (b["seviye"] == en_iyi["seviye"] and len(b["icerik"]) < len(en_iyi["icerik"]))):
                en_iyi = b
    return en_iyi


def _refine_bolum_ai(talimat: str, bolum: str) -> str:
    """Tek AI çağrısı — yalnız hedef bölümü düzenler. Token harcayan tek nokta."""
    sistem = REFINE_BOLUM_PROMPT.format(talimat=talimat, bolum=bolum)
    mesajlar = [{"role": "user", "content": [
        {"type": "text", "text": "Talimatı bu bölüme uygula ve yalnız bölümü döndür."}
    ]}]
    # Analistin açık düzenleme isteği — önbellekten değil, taze üret.
    return _api_cagri(sistem, mesajlar, max_tokens=MAX_TOKENS_KISA, onbellek=False)


def bolum_duzenle(
    hedef_dosya: str,
    anahtar: str,
    talimat: str,
    *,
    _ai_fn=_refine_bolum_ai,
) -> dict:
    """Hedef bölümü AI ile düzenler ve ONAY BEKLEYEN bir revizyon önerisi oluşturur.

    Akış:
      1. Aktif (onaylı) içeriği revizyon oturumundan al (oturum yoksa dosyadan başlat).
      2. `anahtar`'a uyan bölümü bul; yoksa ValueError.
      3. Yalnız o bölümü AI'a gönder (`_ai_fn`), düzenlenmiş bölümü al.
      4. Bölümü dokümana geri yerleştir (splice) → yeni tam içerik.
      5. `revizyon.revizyon_oner(... tip='bolum' ...)` ile beklemede öneri kaydet.

    Döner: eklenen revizyon (beklemede). Analist app.py'den onayla/reddet eder.
    `_ai_fn` yalnız test/enjeksiyon içindir (imza: (talimat, bolum) -> str).
    """
    talimat = (talimat or "").strip()
    if not talimat:
        raise ValueError("Düzenleme talimatı boş.")

    # 1) Aktif içerik — oturum varsa ondan, yoksa dosyadan başlat
    if revizyon.oturum_var_mi(hedef_dosya):
        mevcut = revizyon.onayli_icerik(hedef_dosya)
        # BAYAT OTURUM KORUMASI (veri kaybı önleme): pipeline/rerun/yeni-upload diski
        # oturumdan SONRA yeniden ürettiyse oturum eski içeriği tutar. Diski OTORİTE kabul et,
        # oturumu tazele — yoksa düzenleme sonrası onaylı içerik (eski + küçük düzeltme) güncel
        # analizin üzerine yazılıp onu yok eder.
        yol = OUTPUT_DIR / Path(hedef_dosya).name
        if yol.exists():
            disk = yol.read_text(encoding="utf-8")
            if disk.strip() != (mevcut or "").strip():
                revizyon.yeniden_bazla(hedef_dosya, disk)
                mevcut = disk
    else:
        yol = OUTPUT_DIR / Path(hedef_dosya).name
        if not yol.exists():
            raise FileNotFoundError(f"Çıktı yok: {hedef_dosya}")
        mevcut = yol.read_text(encoding="utf-8")
        revizyon.baslat(hedef_dosya, mevcut, not_="İlk üretim (revizyon oturumu açıldı)")

    # 2) Hedef bölüm
    bolum = bolum_bul(mevcut, anahtar)
    if bolum is None:
        raise ValueError(f"Bölüm bulunamadı: '{anahtar}'")

    # 3) AI düzenleme (yalnız bölüm)
    yeni_bolum = _ai_fn(talimat, bolum["icerik"]).strip("\n")
    # Bölümler arası tek boş satır düzenini koru (splice sonrası ardışık \n\n)
    if not yeni_bolum.endswith("\n"):
        yeni_bolum += "\n"
    # Orijinal bölüm sonundaki boşluk düzenini yaklaşık koru
    kuyruk = "\n" if bolum["icerik"].endswith("\n\n") else ""

    # 4) Splice
    yeni_icerik = mevcut[:bolum["baslangic"]] + yeni_bolum + kuyruk + mevcut[bolum["bitis"]:]

    # 5) Beklemede öneri
    return revizyon.revizyon_oner(
        hedef_dosya, yeni_icerik,
        tip="bolum",
        istek=talimat,
        ozet=f"'{bolum['baslik']}' bölümü düzenlendi",
        degisen_bolumler=[{
            "section": bolum["baslik"], "changeType": "updated",
            "reason": talimat[:160],
        }],
    )
