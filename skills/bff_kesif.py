"""BFF Keşfi (CRUD gözlemi) — ekranın GERÇEK servis sözleşmesini agent'ın KENDİ yaptığı create/update/delete ile çıkarır.

Owner isteri: Task Analizi'nde ekrandaki BFF'leri canlı gözlemlemek için analist elle kayıt açıp güncelleyip
silmek zorunda kalıyordu. Bu adım o işi agent'a verir: hedef ekranda liste → OLUŞTUR (AI-TEST, kayıt KALIR) →
doğrulama hatası (1 kez) → GÜNCELLE (kayıt KALIR) → SİL (ayrı ikinci AI-TEST kaydında) → diğer aksiyonlar (yalnız
kendi kaydında, geri alınamaz olanlar HARİÇ) → filtre/sayfalama; her adımda method/path/payload/response/status.

Çıktı: ekran başına **BFF sözleşme raporu** `reference/live-app/bff/<anahtar>.md` (+ `.json` meta). 7 gün önbellek
(`ONBELLEK_GUN`) → aynı ekrana gelen sonraki task'larda CRUD tekrarlanmaz; "BFF Keşfi" butonu her zaman yeniden
gözler. `reference/live-app/` RAG corpus'unda olduğundan rapor TÜM analizlere referans olarak da girer; Task
Analizi ayrıca hedef ekranın raporunu doğrudan prompta ekler (`rapor_blogu`). Tetikleme: Task Analizi'nde
otomatik (`live_app_gorev.bff_otomatik`, vars. açık) + "BFF Keşfi (CRUD)" butonu (iş modu `bff-kesif`).
Mevcut canlı-gözlem altyapısı (`canli_uygulama_baglami_hazirla` odaklı mod + CRUD kuralları) kullanılır; 1 CLI çağrısı.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from .base import (
    LIVE_APP_DIR, MAX_TOKENS_COMBINED,
    _api_cagri, _xml_ayir, _metin_sikistir, load_context_filter, asama_ayarla,
    canli_uygulama_baglami_hazirla, gorev_live_app_urls, live_app_urls,
)

BFF_DIR = LIVE_APP_DIR / "bff"
ONBELLEK_GUN = 7


# ── Anahtar / depo ───────────────────────────────────────────────────────────
def _anahtar(hedef_url: str, ekran_tarif: str = "") -> str:
    u = (hedef_url or "").strip().rstrip("/").casefold()
    e = re.sub(r"\s+", " ", (ekran_tarif or "").strip().casefold())[:120]
    return hashlib.sha1(f"{u}|{e}".encode("utf-8")).hexdigest()[:12]


def _yollar(anahtar: str) -> tuple[Path, Path]:
    return BFF_DIR / f"{anahtar}.md", BFF_DIR / f"{anahtar}.json"


def rapor_oku(hedef_url: str, ekran_tarif: str = "") -> dict | None:
    """Kayıtlı rapor: {anahtar, md, ts, yas_gun, hedef_url, ekran, yol, ok} ya da None."""
    anahtar = _anahtar(hedef_url, ekran_tarif)
    md_yol, meta_yol = _yollar(anahtar)
    if not md_yol.exists():
        return None
    try:
        meta = json.loads(meta_yol.read_text(encoding="utf-8")) if meta_yol.exists() else {}
    except Exception:
        meta = {}
    ts = float(meta.get("ts") or md_yol.stat().st_mtime)
    md = md_yol.read_text(encoding="utf-8")
    # `ok` OKUMA ANINDA yeniden değerlendirilir (meta eski heuristikle True kalmış olabilir — 2026-10-20: 4 günlük
    # 'Bad credentials' raporu 7 gün 'taze' sayılıp analize giriyordu): gerçek istek kanıtı şart + giriş hatası izi yok.
    ok = bool(meta.get("ok", True)) and rapor_tam_mi(md) and not _giris_hatasi_var(md)
    return {"anahtar": anahtar, "md": md, "ts": ts,
            "yas_gun": round((time.time() - ts) / 86400, 1), "hedef_url": meta.get("hedef_url", hedef_url),
            "ekran": meta.get("ekran", ekran_tarif), "yol": str(md_yol), "ok": ok}


_GIRIS_HATASI = re.compile(r"bad credentials|wrong password|giriş (başarısız|yapılamadı)|login (failed|başarısız)|HTTP 40[13]\b.*(login|giriş|auth)", re.I)


def _giris_hatasi_var(md: str) -> bool:
    """Rapor giriş duvarında kalmış mı (keşif yapılamamış)? Böyle rapor taze sayılmaz → otomatik yeniden keşif."""
    bas = (md or "")[:4000]
    return bool(_GIRIS_HATASI.search(bas)) and ("[K: Network:POST" not in md and "[K: Network:PUT" not in md)


def taze_mi(rapor: dict | None, gun: int = ONBELLEK_GUN) -> bool:
    return bool(rapor and rapor.get("ok") and (time.time() - float(rapor.get("ts") or 0)) < gun * 86400)


def otomatik_acik() -> bool:
    """Task Analizi'nde analiz öncesi otomatik keşif (vars. AÇIK; `live_app_gorev.bff_otomatik=false` kapatır)."""
    try:
        ctx = load_context_filter() or {}
        return (ctx.get("live_app_gorev") or {}).get("bff_otomatik", True) is not False
    except Exception:
        return True


# ── Keşif görevi (odaklı gözlem kapsamı olarak verilir) ─────────────────────
def _kesif_plani(ekran_tarif: str) -> str:
    damga = datetime.now().strftime("%m%d-%H%M")
    return (
        "BFF KEŞFİ (CRUD GÖZLEMİ)" + (f" — hedef ekran: {ekran_tarif}" if ekran_tarif else "") + "\n"
        "Amaç: bu ekranın BFF/servis SÖZLEŞMESİNİ gerçek istek/yanıtlarla çıkarmak. Analiz yazma; yalnız gözlemle. "
        "SIRAYLA uygula, her adımda tetiklenen isteği `browser_network_requests` ile listele ve ANA isteğin tam "
        "detayını `browser_network_request` ile al (method · path · query · request payload · response gövdesi özeti · status):\n"
        "1. LİSTE: ekranı aç → açılış/liste ve lookup isteklerini yakala; tablo kolonlarını ve filtre/arama/sayfalama "
        "kontrollerini kaydet; filtre/sayfalamayı BİR kez kullanıp query parametrelerini al.\n"
        f"2. OLUŞTUR: ekleme formunu aç; alanları (ad · tip · zorunlu · varsayılan · bağımlı/cascade) kaydet; geçerli "
        f"veriyle doldur — ad/kod/isim alanlarına `AI-TEST-{damga}` öneki — kaydet → POST isteğinin payload'ı + yanıtı "
        "(status, dönen id). BU KAYDI SİLME, kalsın (analist inceleyecek).\n"
        "3. DOĞRULAMA: aynı formu zorunlu bir alan BOŞ bırakarak bir kez gönder → ekran hata mesajı + (istek gittiyse) "
        "status/errorCode. Yalnız BİR kez.\n"
        f"4. GÜNCELLE: `AI-TEST-{damga}` kaydını aç, 1-2 alanı değiştir, kaydet → PUT/PATCH path + payload + yanıt. Kayıt KALSIN.\n"
        f"5. SİL: AYRI ikinci bir kayıt (`AI-TEST-{damga}-SIL`) oluştur ve onu sil → DELETE path + yanıt + listeden "
        "kalktığı doğrulaması. İlk kaydı silme.\n"
        "6. DİĞER AKSİYONLAR (aktif/pasif, kopyala, durum değiştir, toplu işlem, detay sekmeleri): YALNIZ kendi "
        f"`AI-TEST-{damga}` kaydında, GERİ ALINAMAZ olmayanları (publish/onaya gönder/ödeme/dış sisteme iletim HARİÇ) "
        "bir kez dene, isteklerini yakala.\n"
        "Yapamadığın/izin olmayan/bulamadığın adımı atla ve 'Gezilemeyen' altında nedeniyle yaz. Tahmin yok."
    )


_RAPOR_FORMAT = """
### BFF RAPORU ÇIKTI BİÇİMİ (zorunlu)
Gözlem bitince YALNIZ şu bloğu yaz (blok dışına metin yok, süreç anlatma):
<bff_rapor>
## Ekran
- Route / başlık · menü yolu · giriş durumu

## Açılış ve liste servisleri
| İstek | Query / Parametre | Status | Yanıt alanları (özet) |
|---|---|---|---|

## Form alanları (Oluştur / Güncelle)
| Alan | Tip | Zorunlu | Varsayılan / Bağımlılık | Not |
|---|---|---|---|---|

## CREATE
- İstek: `POST /path` · payload (maskeli) · status · yanıt (id vb.)
- Ekran sonucu: mesaj / liste yenilendi mi

## DOĞRULAMA HATASI
- Boş bırakılan alan · ekran mesajı · istek gitti mi · status/errorCode

## UPDATE
- İstek: `PUT|PATCH /path` · payload · status · yanıt

## DELETE (ayrı kayıt)
- İstek: `DELETE /path` · status · yanıt · listeden kalktı mı

## Diğer aksiyonlar
| Aksiyon | İstek | Status | Not |
|---|---|---|---|

## Bırakılan AI-TEST kayıtları
- (ad/kod + id) — analist inceleyip silebilir

## Gezilemeyen / yapılamayan
- adım — neden
</bff_rapor>
Kurallar: yalnız GÖZLENEN istek/alan/mesaj; token/cookie/şifre/kişisel veri MASKELE; "muhtemelen" yazma."""


def _canli_gorev(hedef_url: str, ekran_tarif: str, ekran_bazli: bool) -> tuple[str | None, str | None]:
    """(canlı görev metni, _api_cagri kapsamı). ekran_bazli → miras live_app ANA adresi + ekran hedefi ('surec'
    kapsamı); değilse Task Analizi'nin live_app_gorev hedefi ('gorev' kapsamı)."""
    plan = _kesif_plani(ekran_tarif)
    if ekran_bazli:
        p = urlparse(hedef_url or "")
        if not (p.scheme and p.netloc):
            return None, None
        return canli_uygulama_baglami_hazirla(base_url_override=f"{p.scheme}://{p.netloc}", hedef_tarif=plan), "surec"
    if not gorev_live_app_urls():
        return None, None
    return canli_uygulama_baglami_hazirla(gorev=True, hedef_tarif=plan), "gorev"


def _ham_kaydet(anahtar: str, yanit: str) -> str:
    """Rapor bloğu üretilmeyen yanıtı `<anahtar>.ham.txt`'ye yazar (teşhis; gitignore'lu dizin)."""
    try:
        BFF_DIR.mkdir(parents=True, exist_ok=True)
        yol = BFF_DIR / f"{anahtar}.ham.txt"
        yol.write_text((yanit or "")[:200_000], encoding="utf-8")
        return str(yol)
    except Exception:
        return ""


def kesfet(hedef_url: str = "", ekran_tarif: str = "", ekran_bazli: bool = False, *, _ai=None) -> dict:
    """Keşfi çalıştırır, raporu kaydeder, {ok, anahtar, md, ts, yas_gun, yol, neden} döner. Hata → ok False (fırlatmaz)."""
    if not hedef_url:
        urls = live_app_urls() if ekran_bazli else gorev_live_app_urls()
        hedef_url = urls[0] if urls else ""
    anahtar = _anahtar(hedef_url, ekran_tarif)
    canli, kapsam = _canli_gorev(hedef_url, ekran_tarif, ekran_bazli)
    if not canli:
        return {"ok": False, "anahtar": anahtar, "md": "", "neden": "Canlı uygulama hedefi tanımlı değil (Bağlam Filtresi)."}
    sistem = ("BFF keşif uzmanısın: canlı uygulamada ekranın servis sözleşmesini KENDİ yaptığın create/update/delete "
              "ile gerçek istek-yanıtlardan çıkarırsın. Analiz/öneri yazmazsın; yalnız gözlemlenen gerçeği, maskeleyerek raporlarsın.")
    icerik = [{"type": "text", "text": canli}, {"type": "text", "text": _RAPOR_FORMAT},
              {"type": "text", "text": "Keşfi uygula ve raporu yaz."}]
    asama_ayarla("bff")
    # CRUD keşfi (liste→oluştur→doğrula→güncelle→sil→filtre) 40 turluk genel tavanı aşıyor (2026-10-19: tavana takılıp
    # 3 kez baştan koştu) → kendi bütçesi (BFF_MAX_TUR, vars. 70) + 1 devam hakkı; sonra araçsız tamamlatma.
    try:
        _butce = max(20, int(os.getenv("BFF_MAX_TUR", "70")))
    except (TypeError, ValueError):
        _butce = 70
    ai = _ai or (lambda s, m, k: _api_cagri(s, m, max_tokens=MAX_TOKENS_COMBINED, thinking=False, onbellek=False,
                                            canli_uygulama_kapsami=k, katman="yardimci", max_turns=_butce, tur_devam=1))
    try:
        yanit = ai(sistem, [{"role": "user", "content": icerik}], kapsam)
    except Exception as e:
        return {"ok": False, "anahtar": anahtar, "md": "", "neden": f"Keşif çalıştırılamadı: {str(e)[:200]}"}
    if "<bff_rapor>" in (yanit or ""):
        md = _xml_ayir(_metin_sikistir(yanit or ""), "bff_rapor").strip()
    elif re.search(r"^## (Ekran|Açılış|CREATE)\b", _metin_sikistir(yanit or ""), re.M):
        # Etiket atlanmış ama rapor gövdesi var (model 10+ dk gözlem yapıp bloğu unutabiliyor) → KAYBETME
        md = _metin_sikistir(yanit or "").strip()
    else:
        # Blok hiç yok → rapor değil (tarayıcı aracı çalışmamış / model sapmış) → kaydetme, önbelleğe alma;
        # ham yanıtı teşhis için sakla (eskiden sessizce atılıyordu → neden anlaşılamıyordu)
        ham_yol = _ham_kaydet(anahtar, yanit or "")
        return {"ok": False, "anahtar": anahtar, "md": "",
                "neden": "Rapor üretilemedi (tarayıcı aracı çalışmamış olabilir)." + (f" Ham yanıt: {ham_yol}" if ham_yol else "")}
    if not md:
        return {"ok": False, "anahtar": anahtar, "md": "", "neden": "Rapor boş."}
    ok = rapor_tam_mi(md)
    ts = time.time()
    baslik = (f"<!-- bff-kesif · url={hedef_url} · ekran={ekran_tarif[:80] if ekran_tarif else '-'} · "
              f"{datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')} -->\n"
              f"# BFF Sözleşme Raporu — {ekran_tarif[:80] if ekran_tarif else hedef_url}\n\n")
    md_yol, meta_yol = _yollar(anahtar)
    BFF_DIR.mkdir(parents=True, exist_ok=True)
    md_yol.write_text(baslik + md + "\n", encoding="utf-8")
    meta_yol.write_text(json.dumps({"anahtar": anahtar, "hedef_url": hedef_url, "ekran": ekran_tarif, "ts": ts, "ok": ok},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": ok, "anahtar": anahtar, "md": baslik + md, "ts": ts, "yas_gun": 0.0, "yol": str(md_yol),
            "neden": "" if ok else "Rapor eksik görünüyor (CREATE/servis bölümü yok) — keşif yarım kalmış olabilir."}


_SERVIS_BOLUM = re.compile(r"(?im)^##\s*(?:CREATE|Açılış|Aksiyon|Servis|Liste|UPDATE|DELETE)")
_AG_KANIT = re.compile(r"\[K:\s*Network:\s*(?:GET|POST|PUT|PATCH|DELETE)\b")


def rapor_tam_mi(md: str) -> bool:
    """Rapor GERÇEK gözlem içeriyor mu? CREATE/servis bölümü VE en az bir `[K: Network:<METHOD> …]` kanıt etiketi.
    Eski sezgisel (`'POST' in md`) biçim şablonunda zaten 'POST' geçtiği için her zaman doğruydu → boş/yarım rapor
    7 gün 'taze' sayılıp analize gerçek sözleşme diye giriyordu."""
    m = md or ""
    return bool(_SERVIS_BOLUM.search(m)) and bool(_AG_KANIT.search(m))


def rapor_blogu(rapor: dict) -> str:
    """Analiz promptuna girecek blok (Task Analizi: hedef ekranın gerçek sözleşmesi). Rapor eksik (`ok` False) ya da
    eski (taze değil) ise açık uyarı eklenir → analiz onu kesin sözleşme değil, doğrulanacak ipucu olarak kullanır."""
    tarih = datetime.fromtimestamp(float(rapor.get("ts") or time.time())).strftime("%Y-%m-%d %H:%M")
    md = rapor.get("md") or ""
    tam = bool(rapor.get("ok")) and rapor_tam_mi(md)
    taze = taze_mi(rapor) if rapor.get("ts") else tam
    bas = ("### BFF SÖZLEŞME RAPORU — canlı CRUD gözlemi (" + tarih + ", "
           + str(rapor.get("ekran") or rapor.get("hedef_url") or "") + ")\n")
    if tam and taze:
        return bas + ("Aşağıdaki endpoint/alan/mesajlar GERÇEK gözlemdir (agent kayıt oluşturdu/güncelledi/sildi). API, DB ve "
                      "validasyon bölümlerini BU sözleşmeye dayandır; `[K: Network:<METHOD> <path>]` etiketiyle atıf ver. "
                      "Burada olmayan endpoint UYDURMA.\n\n") + md
    neden = ("rapor EKSİK (CREATE/servis bölümü ya da ağ kanıtı yok — keşif yarım kalmış olabilir)" if not tam
             else f"rapor ESKİ ({rapor.get('yas_gun', '?')} gün)")
    return bas + ("⚠ UYARI: " + neden + ". Buradaki endpoint/alanları KESİN sözleşme sayma — doğrulanacak ipucu olarak kullan; "
                  "kapsam için gereken ama raporda olmayan endpoint'i `[K: ❓ Belirsiz]` ile ÖNERİ olarak yazabilirsin "
                  "(yeni endpoint önerilebilir).\n\n") + md
