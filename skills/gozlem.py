"""Canlı Gözlem Fazı — analizden AYRI, küçük promptlu gözlem → yapılandırılmış GÖZLEM RAPORU (Faz 1 / A1.1-A1.3).

Kota taraması (docs/KOTA-OPTIMIZASYON-PLANI.md): canlı gözlem, analiz çağrısının İÇİNDE yapılıyordu → agentik döngüde her
araç turu (tipik 17-34) referans+few-shot+domain+task'tan oluşan ~40k token'lık bağlamı yeniden okuyordu (tek çağrıda
5.9M cache okuma). Bu modül gözlemi ayırır:
  1. Gözlem fazı: KÜÇÜK prompt (canlı görev bloğu + görev özeti + rapor biçimi; referans/few-shot/domain YOK) →
     `<gozlem_raporu>` (ekran/alanlar/aksiyon→istek-yanıt/validasyon/boş-hata durumları/gezilemeyen; kanıt etiketli).
  2. Analiz fazı (motorlarda): TEK gözlemsiz çağrı — tüm bağlam + bu rapor (`rapor_blogu`). Kalite: analiz aynı bağlamı
     görür; gözlem artık denetlenebilir bir rapor. "Model araç çağırmadı" hatası büyük promptlardan geliyordu → küçük
     gözlem promptunda kaybolur.
  3. Rapor önbelleği (A1.3 — owner onayı): aynı canlı görev bloğu (URL+hedef) için `GOZLEM_RAPOR_GECERLILIK` sn (vars. 6 sa)
     içinde rapor YENİDEN KULLANILIR — yalnız `yeniden=False` çağrılarda (cevap turu / düzelt / FE+BE ikinci katman).
     Yeni "Teknik Analiz Et" (`yeniden=True`) her zaman taze gözler ("canlı gözlem = mevcut durum" kuralı korunur).
Dosyalar: `reference/live-app/gozlem/<anahtar>.md` + `.json` (gitignore'lu dizin). Hata → `{ok: False}`; analiz kırılmaz,
motor gözlemsiz devam eder ve raporda "gözlem yapılamadı" notu düşer (rozet `.gozlem-durum.json`'dan).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

from .base import (
    LIVE_APP_DIR, MAX_TOKENS_COMBINED,
    _api_cagri, _xml_ayir, _metin_sikistir, asama_ayarla, gozlem_durum_oku,
)

GOZLEM_DIR = LIVE_APP_DIR / "gozlem"
_RAPOR_KC_TAVAN = 12_000       # rapor karakter tavanı (analiz promptuna girecek)
_OZET_KC = 3_000               # görev/doküman özeti tavanı (gözlem promptu küçük kalsın)


def gecerlilik_sn() -> int:
    try:
        return max(0, int(os.getenv("GOZLEM_RAPOR_GECERLILIK", str(6 * 3600))))
    except (TypeError, ValueError):
        return 6 * 3600


_ODAK_KC = 2_000               # anahtara giren görev odağı (gorev_ozet) karakteri


def _anahtar(canli_blok: str, kapsam: str, gorev_ozet: str = "") -> str:
    """Önbellek anahtarı = kapsam + canlı blok (URL/hedef) + GÖREV ODAĞI (özetin ilk ~2k karakteri).
    Odak anahtara girmezse aynı URL'e gelen farklı task'lar birbirinin 6 saatlik raporunu devralırdı
    (başka ekranın gözlemi 'taze' sayılırdı)."""
    odak = hashlib.sha1((gorev_ozet or "").strip()[:_ODAK_KC].encode("utf-8")).hexdigest()[:10]
    return hashlib.sha1(f"{kapsam}|{(canli_blok or '').strip()}|{odak}".encode("utf-8")).hexdigest()[:12]


def _durum_bu_cagrinin_mi(durum: dict | None, baslangic: float) -> bool:
    """`.gozlem-durum.json` bu çağrıdan ÖNCE yazılmışsa (başka bir akışın kalıntısı) bu gözleme ait değildir
    → yapildi=False say. `zaman` yoksa (eski biçim) dosyaya güvenilir (geri uyum)."""
    if not durum:
        return False
    z = durum.get("zaman")
    if not z:
        return True
    try:
        return datetime.fromisoformat(str(z)).timestamp() >= baslangic - 1.0
    except (TypeError, ValueError):
        return True


def _yollar(anahtar: str) -> tuple[Path, Path]:
    return GOZLEM_DIR / f"{anahtar}.md", GOZLEM_DIR / f"{anahtar}.json"


def rapor_oku(anahtar: str) -> dict | None:
    md_yol, meta_yol = _yollar(anahtar)
    if not (md_yol.exists() and meta_yol.exists()):
        return None
    try:
        meta = json.loads(meta_yol.read_text(encoding="utf-8"))
        md = md_yol.read_text(encoding="utf-8").rstrip("\n")
    except Exception:
        return None
    ts = float(meta.get("ts") or 0)
    return {**meta, "md": md, "yas_sn": time.time() - ts, "yol": str(md_yol)}


def taze_mi(rapor: dict | None) -> bool:
    return bool(rapor) and bool(rapor.get("ok")) and (rapor.get("yas_sn", 1e12) < gecerlilik_sn())


_SISTEM = (
    "Canlı uygulama GÖZLEMCİSİSİN. Tek görevin: verilen canlı uygulama görevini tarayıcı araçlarıyla uygulayıp "
    "GÖZLEMLENEN GERÇEĞİ yapılandırılmış raporla bildirmek. Analiz, öneri, gereksinim, çözüm YAZMAZSIN; tahmin etmezsin; "
    "göremediğini 'gözlemlenemedi' diye yazarsın. Şifre/token yazmazsın."
)

_RAPOR_FORMAT = """
### GÖZLEM RAPORU BİÇİMİ (zorunlu) — gözlem bitince YALNIZ şu bloğu yaz (blok dışına metin/süreç anlatımı yok)
<gozlem_raporu>
## Ekran ve Navigasyon
- Route/başlık · menü yolu · giriş durumu · kapsamdaki ekranın yerleşimi (tablo/filtre/aksiyon alanları) `[K: Canlı UI:/route]`
- **ÇOK EKRAN:** Görev/özet BİRDEN ÇOK ekran adlandırıyorsa (ör. "Prematch + Live + Outright Program"), HER adlandırılan
  ekrana menü/rota ile GİT ve her birini AYRI gözlemle — rotası, liste/istek ucu, filtre/alan davranışı. Ekranlar arasında
  uç/alan/filtre FARKI olabilir; birini gözleyip "diğerleri aynı" DEME. Her ekran için ayrı `[K: Canlı UI:/route]` +
  `[K: Network:…]` ver. Gidemediğin ekranı 'Gezilemeyen'e yaz (neden); varsayma.

## Alanlar ve Bileşenler
| Alan/Bileşen | Tip | Zorunlu | Varsayılan / Seçenekler | Davranış (disabled, bağımlılık) |
|---|---|---|---|---|

## Aksiyonlar → Servis Çağrıları
| Aksiyon | İstek (method path + önemli query/payload alanları, maskeli) | Status | Yanıt alanları (özet) | Ekran sonucu |
|---|---|---|---|---|
(her satır `[K: Network:METHOD /path → status]` ile)
- KRİTİK VERİ-ÇEKME çağrıları (liste/detay/eşleme okuma) için `browser_network_request` ile o isteğin TAM yanıt
  gövdesini AÇ ve GERÇEK alan adlarını 'Yanıt alanları' sütununa YAZ (ör. `outcomes[].externalId`, `provider`,
  `matchedInfo`). Alan adları geliştiriciye sözleşme olur — 'okunamadı' bırakma, mümkünse birkaç örnek alan ver.

## Validasyon ve Mesajlar
- Hangi alan/aksiyonda hangi mesaj AYNEN · istek gitti mi · errorCode

## Boş / Hata Durumları
- Kayıt yokken · hata dönünce ekran davranışı

## Kapsam Dışı Gözlemler (kısa)
- Kapsamı doğrudan etkileyen başka ekran/servis varsa 1-2 satır

## Gezilemeyen
- Ekran/akış + neden (yetki, veri yok, hata, tur tavanı)
</gozlem_raporu>
KURALLAR: yalnız gözlemlenen; UYDURMA yok; her satırda kanıt etiketi; rapor ≤ 10.000 karakter (gereksiz tekrar yok)."""


def _ozet_kirp(metin: str) -> str:
    m = (metin or "").strip()
    return m if len(m) <= _OZET_KC else m[:_OZET_KC] + "\n…(kırpıldı)"


def rapor_al(canli_blok: str, kapsam: str, gorev_ozet: str = "", yeniden: bool = True,
             max_turns: int | None = None, _ai=None) -> dict:
    """Gözlem fazını çalıştırır (ya da taze raporu yeniden kullanır).
    canli_blok: `canli_uygulama_baglami_hazirla(...)` çıktısı (URL + hedef + giriş + kurallar) — motorun zaten ürettiği blok.
    kapsam: 'gorev' | 'surec' (profil/URL seti). yeniden=False → taze önbellek varsa gözlem YAPILMAZ (cevap turu vb.).
    Dönen: {ok, md, anahtar, ts, yas_sn, yeniden_kullanildi, yapildi(num_turns>1), neden}."""
    anahtar = _anahtar(canli_blok, kapsam, gorev_ozet)
    if not (canli_blok or "").strip():
        return {"ok": False, "md": "", "anahtar": anahtar, "neden": "Canlı görev bloğu boş.", "yeniden_kullanildi": False}
    if not yeniden:
        mevcut = rapor_oku(anahtar)
        if taze_mi(mevcut):
            print(f"  ♻️  Taze gözlem raporu yeniden kullanıldı ({int(mevcut['yas_sn'] // 60)} dk önce) — yeniden gözlem yok.")
            return {**mevcut, "yeniden_kullanildi": True}
    asama_ayarla("gozlem")
    icerik = [{"type": "text", "text": canli_blok},
              {"type": "text", "text": "### Gözlem konusu (görev/doküman özeti — yalnız hedefi anlamak için)\n" + _ozet_kirp(gorev_ozet)},
              {"type": "text", "text": _RAPOR_FORMAT},
              {"type": "text", "text": "Gözlemi uygula ve raporu yaz."}]
    ai = _ai or (lambda s, m: _api_cagri(s, m, max_tokens=MAX_TOKENS_COMBINED, thinking=False, onbellek=False,
                                         canli_uygulama_kapsami=kapsam, max_turns=max_turns, katman="yardimci"))
    baslangic = time.time()      # durum dosyası tazeliği: bu çağrıdan önce yazılmış kalıntı 'yapıldı' sayılmaz
    try:
        yanit = ai(_SISTEM, [{"role": "user", "content": icerik}])
    except Exception as e:
        return {"ok": False, "md": "", "anahtar": anahtar, "neden": f"Gözlem çalıştırılamadı: {str(e)[:200]}", "yeniden_kullanildi": False}
    metin = _metin_sikistir(yanit or "")
    if "<gozlem_raporu>" in metin:
        md = _xml_ayir(metin, "gozlem_raporu").strip()
    elif re.search(r"^## (Ekran|Alanlar|Aksiyonlar)", metin, re.M):
        md = metin.strip()          # etiket atlanmış ama gövde var → kaybetme
    else:
        return {"ok": False, "md": "", "anahtar": anahtar, "neden": "Gözlem raporu üretilemedi (tarayıcı aracı çalışmamış olabilir).",
                "yeniden_kullanildi": False}
    if len(md) > _RAPOR_KC_TAVAN:
        md = md[:_RAPOR_KC_TAVAN] + "\n…(rapor tavana kırpıldı)"
    durum = gozlem_durum_oku() or {}
    # yapildi: makine-doğrulanmış (num_turns/araç reddi) ve BU çağrıya ait durum dosyası; dosya yoksa (test/mock, API modu)
    # modelin çıktısına güvenilir. ok ayrıca GERÇEK kanıt etiketi ister — "## Aksiyonlar" başlığı biçim şablonunda zaten var,
    # kanıt değil (eskiden boş şablon 'ok' sayılıp 6 saat önbellekleniyordu).
    yapildi = bool(durum.get("yapildi", True)) if (not durum or _durum_bu_cagrinin_mi(durum, baslangic)) else False
    ok = yapildi and ("[K: Network" in md or "[K: Canlı UI" in md)
    ts = time.time()
    GOZLEM_DIR.mkdir(parents=True, exist_ok=True)
    md_yol, meta_yol = _yollar(anahtar)
    md_yol.write_text(md + "\n", encoding="utf-8")
    meta_yol.write_text(json.dumps({"anahtar": anahtar, "kapsam": kapsam, "ts": ts, "ok": ok, "yapildi": yapildi,
                                    "num_turns": int(durum.get("num_turns") or 0)}, ensure_ascii=False), encoding="utf-8")
    return {"ok": ok, "md": md, "anahtar": anahtar, "ts": ts, "yas_sn": 0.0, "yapildi": yapildi, "yol": str(md_yol),
            "yeniden_kullanildi": False, "neden": "" if ok else "Gözlem eksik (tarayıcı kullanılamadı ya da servis gözlenemedi)."}


def rapor_blogu(rapor: dict) -> str:
    """Analiz promptuna girecek blok — gözlem artık AÇIK bir rapor; analiz buna atıf verir, raporda olmayanı uydurmaz."""
    tarih = datetime.fromtimestamp(float(rapor.get("ts") or time.time())).strftime("%Y-%m-%d %H:%M")
    ek = " · önbellekten (taze)" if rapor.get("yeniden_kullanildi") else ""
    return ("### CANLI UYGULAMA GÖZLEM RAPORU (" + tarih + ek + ")\n"
            "Aşağıdaki ekran/alan/servis/mesaj bilgileri GERÇEK gözlemdir (agent uygulamayı gezdi). Analizde `[K: Canlı UI:…]` "
            "ve `[K: Network:…]` etiketlerini bu rapordan AYNEN taşı; raporda olmayan ekran/servis/alan UYDURMA; raporla referans "
            "(Swagger/Confluence/BRD) çelişirse gözlenen gerçek kazanır; çelişkiyi ilgili yerde `[K: ❓ Belirsiz]` ile işaretle "
            "(açık sorular ayrı adımda üretilir). Bu çağrıda tarayıcı aracı YOK — gözlem tamamlandı, yalnız analizi yaz.\n\n"
            + (rapor.get("md") or ""))


_SORU_RAPOR_KC = 4_000


def rapor_soru_blogu(rapor: dict | None) -> str:
    """Açık soru aşamasına (gorev/teknik) giren KISA gözlem özeti (~4k): raporla referans çelişkileri soruya dönüşebilsin.
    Rapor yok/boş → ''."""
    md = ((rapor or {}).get("md") or "").strip()
    if not md:
        return ""
    if len(md) > _SORU_RAPOR_KC:
        md = md[:_SORU_RAPOR_KC] + "\n…(kırpıldı)"
    return ("### CANLI GÖZLEM RAPORU (özet — soru üretimi için)\n"
            "Analizde `[K: ❓ Belirsiz]` ile işaretlenen gözlem↔referans çelişkileri (endpoint/alan/davranış farkı) bloklayıcıysa "
            "açık soruya çevir.\n\n" + md)


def gozlem_yok_blogu(neden: str) -> str:
    """Gözlem yapılamadıysa analize düşen kısa not (analiz URL'lere dayalı iddiaları doğrulanmamış sayar)."""
    return ("### CANLI UYGULAMA GÖZLEMİ YAPILAMADI\n"
            f"Neden: {neden or 'bilinmiyor'}. Canlı ekran/servis davranışına dair iddiaları doğrulanmamış say; "
            "referanslara dayan, belirsiz noktaları `[K: ❓ Belirsiz]` ile işaretle. Bu çağrıda tarayıcı aracı YOK.")
