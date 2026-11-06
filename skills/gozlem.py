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
    # Odak hash'i TAM özet üzerinden (denetim 2026-11-02 B#2): ilk 2k ile hash'lenince aynı gövdeli ama farklı
    # istekli/notlu iki görev (istek SONDA) aynı anahtara düşüp birbirinin raporunu 'taze' sayıyordu.
    odak = hashlib.sha1((gorev_ozet or "").strip().encode("utf-8")).hexdigest()[:10]
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
- **ALANIN TAŞINDIĞI / YÖNETİLDİĞİ EKRAN (owner 2026-11-06):** görev 'X ekranından kaldırılsın, Y ekranında yapılması
  yeterli / Y'den yönetilecek' diyorsa Y KAPSAMDADIR: Y'ye git, o alanın düzenlendiği satırın Edit/düzenleme modalını AÇ,
  alanı değiştirip KAYDET'e bas ve yazma isteğini yakala (`[K: Network:METHOD /path]` + payload alan adları), sonra eski
  değere geri al. Amaç: Y'nin alanı HANGİ UÇLA yazdığı (X ile aynı uç mu, ayrı bir uç mu — ör. `PATCH …/odd-multiplier`).
  Bu sorunun cevabı olmadan 'aynı uç' VARSAYMA; Y'ye gidemediysen 'Gezilemeyen'e yaz.

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
- **PARAMETRE/YETENEK DOĞRULAMA (notta istenen servis kontrolü — PASİF GÖZLEM YETMEZ):** görev/analist notu belirli bir
  parametre ya da yetenek doğrulaması istiyorsa (ör. "serviste `id` parametresi var mı", `sportId`/`name` ile filtre,
  sayfalama) o parametreyi SADECE varsayılan ekran yüklenirken İZLEME — FİİLEN DENE: arama/filtre alanına değer gir ya da
  aynı ucu parametreyi EKLEYEREK ve EKLEMEDEN çağır, her iki isteğin path+query'sini ve dönen sonucu `browser_network_request`
  ile yakala, davranış farkını yaz (ör. "`?id=123` → tek kayıt / `?name=x&sportId=5` → filtreli liste, page 0-tabanlı size 20").
  Deneyemediğin parametreyi 'Gezilemeyen'e nedeniyle yaz — 'analist bildirdi' diye RAPORA GEÇME (rapor yalnız SENİN gözlemin).

## Validasyon ve Mesajlar
- Hangi alan/aksiyonda hangi mesaj AYNEN · istek gitti mi · errorCode
- **MODAL/FORM = GÖZLEM HEDEFİ, YAZMA İŞLEMİ DEĞİL (owner 2026-11-05):** Edit / Add / View Details / Düzenle / Yeni
  butonuyla açılan modal veya form SALT-OKUNUR gözlem kapsamındadır — AÇ (kaydetmeden) ve rapora yaz: alanların tipi,
  maske/format, ondalık/basamak kabulü, max uzunluk, zorunluluk işareti, disabled bağımlılıkları. Hedef belirli bir alan
  için 'şu değeri yaz' diyorsa (ör. Odds Multiplier'a `1,111111`) o değeri alana FİİLEN YAZ ve ne olduğunu gözle (kesildi mi,
  virgül→nokta oldu mu, hata mesajı çıktı mı); sonra Cancel/kapat. Modal açıp alan yazmak kayıt DEĞİŞTİRMEZ → 'Gezilemeyen'e
  'yazma işlemi' diye KOYMA. Save/Kaydet'e YALNIZ hedef açıkça 'kaydet / payload'ı yakala' diyorsa bas; bastıysan isteğin
  payload'ını yakala ve kaydı eski değerine GERİ AL.
- **ÖNCE DERİNLİK, SONRA GENİŞLİK:** hedef belirli bir ekran/modal/alan adlandırıyorsa ÖNCE ona git ve modal gözlemini
  TAMAMLA; menü altındaki diğer ekranları listelemek ikincildir (bütçe kalırsa). Yalnız liste kolonlarını sayıp modalı
  'açılmadı' bırakan rapor hedefi karşılamaz.

## Boş / Hata Durumları
- Kayıt yokken · hata dönünce ekran davranışı

## Kapsam Dışı Gözlemler (kısa)
- Kapsamı doğrudan etkileyen başka ekran/servis varsa 1-2 satır

## Gezilemeyen
- Ekran/akış + neden (yetki, veri yok, hata, tur tavanı)
</gozlem_raporu>
KURALLAR: yalnız gözlemlenen; UYDURMA yok; her satırda kanıt etiketi; rapor ≤ 10.000 karakter (gereksiz tekrar yok)."""


def _ozet_kirp(metin: str) -> str:
    """Özet tavanı: BAŞ + SON (denetim 2026-11-02 B#2) — analist isteği/notu çoğunlukla SONDA (BRD alıntılı uzun
    açıklamanın ardından); yalnız baş alınınca gözlemci isteği hiç görmüyordu."""
    m = (metin or "").strip()
    if len(m) <= _OZET_KC:
        return m
    bas, son = int(_OZET_KC * 0.6), _OZET_KC - int(_OZET_KC * 0.6)
    return m[:bas] + "\n…(orta kısım kırpıldı)…\n" + m[-son:]


_PARAM_ADAY = re.compile(r"`?\b([a-z][A-Za-z0-9]*(?:Id|ID|Name|Code)|id|name|q|page|size|sportId|marketId)\b`?")
_UC_ADAY = re.compile(r"(?:GET|POST|PUT|PATCH|DELETE)?\s*(/(?:bff|api)/[A-Za-z0-9_./{}-]+)")
# Hedef modal/form gözlemi istiyor mu (Edit/Add/modal/input'a değer yaz…) → zorunlu doğrulama listesine modal maddesi girer.
# "… Y sayfasında/ekranında yapılması yeterli(dir)" / "Y üzerinden yönetil…" → alanın taşındığı ekran adı
_TASINAN_EKRAN = re.compile(r"((?:[A-ZÇĞİÖŞÜ][\w'’-]*\s+){0,3}[A-ZÇĞİÖŞÜ][\w'’-]*)\s+(?i:sayfas[ıi]nda|ekran[ıi]nda|"
                            r"sekmesinde|üzerinden)\s+(?i:yap[ıi]lmas[ıi]\s+yeterli|y[öo]netil|g[üu]ncellen|d[üu]zenlen)")
_MODAL_ADAY = re.compile(r"(?i)\b(edit|add|düzenle|modal|form|yeni kayıt|input|alan[a-zı]* (?:yaz|gir)|yaz(?:ıp|ın)?\b|gir(?:ip|in)?\b|"
                         r"popup|drawer|detail)")


def _dogrulama_listesi(gorev_ozet: str) -> str:
    """Analist notu / task özetinde adı geçen parametre ve uçlardan ZORUNLU doğrulama listesi (recency bloğu).
    Not yoksa ve parametre adayı yoksa boş döner (prompt büyümez)."""
    m = (gorev_ozet or "")
    not_bolumu = m.split("ANALİST NOTU", 1)[1] if "ANALİST NOTU" in m else ""
    kaynak = not_bolumu or m
    params = []
    for p in _PARAM_ADAY.findall(kaynak):
        if p not in params and p.lower() not in ("page", "size"):
            params.append(p)
    ucler = []
    for u in _UC_ADAY.findall(m):
        if u not in ucler:
            ucler.append(u)
    modal_istek = bool(_MODAL_ADAY.search(kaynak))
    tasinan = [t.strip() for t in _TASINAN_EKRAN.findall(m)]
    if not not_bolumu and not params and not modal_istek and not tasinan:
        return ""
    # Kayıtlı Swagger'daki GERÇEK parametre adları (1254 koşusu: gözlemci nottaki 'id'/'q' ile uğraşıp `name`/`marketId`'yi
    # hiç denemedi) — uç adı eşleşen kayıtlı endpoint'lerin query parametreleri listeye eklenir.
    swagger_params: dict[str, list[str]] = {}
    try:
        from .servis_sozlesme import _endpointleri_oku, _yol_kaynaklari
        kayitlar = _endpointleri_oku()
        for u in ucler[:4]:
            hedef = _yol_kaynaklari(u)
            for k in kayitlar:
                if k["method"] == "GET" and hedef and hedef <= _yol_kaynaklari(k["path"]):
                    adlar = [p["ad"] for p in (k.get("parametreler") or []) if p["yer"] == "query"
                             and p["ad"] not in ("page", "size", "sortBy", "sortDirection")]
                    if adlar:
                        swagger_params[u] = adlar[:10]
                        break
    except Exception:
        pass
    sat = ["### GÖZLEM BİTMEDEN ÖNCE ZORUNLU DOĞRULAMA (analist/task isteği — pasif izleme YETMEZ; ÖNCELİK 1: bunları "
           "İLK yap, referans ekran aramaya/gezintiye tur harcamadan önce)"]
    if ucler:
        sat.append("- İlgili uç(lar): " + ", ".join(f"`{u}`" for u in ucler[:4]))
    for u, adlar in swagger_params.items():
        sat.append(f"- Kayıtlı Swagger'a göre `{u}` GERÇEK query parametreleri: " + ", ".join(f"`{a}`" for a in adlar)
                   + " — nottaki ad farklıysa (ör. 'id'/'q') BUNLARI dene ve eşlemeyi yaz.")
    if params:
        sat.append("- Şu parametrelerin HER BİRİ için en az bir istek tetikle: " + ", ".join(f"`{p}`" for p in params[:8])
                   + ". NASIL: ekrandaki ilgili filtre/arama alanına değer yazıp Apply/Enter ile UI ÜZERİNDEN tetikle (uygulama "
                   "isteği kendi oturum token'ıyla atar). Oturum dışı doğrudan URL/`fetch` çağrısı 401 döner ve KANIT SAYILMAZ. "
                   "Filtreli yanıt küçüktür → `browser_network_request` ile path+query+yanıt gövdesini oku ve 'Aksiyonlar → "
                   "Servis Çağrıları'na `[K: Network:GET …?<param>=…]` satırı olarak yaz (parametresiz/parametreli toplam kayıt farkını belirt).")
        sat.append("- Parametrenin GERÇEK adı notta yazandan farklıysa gerçek adı yaz; UI'da o filtre alanı yoksa 'Gezilemeyen'e "
                   "'UI'da tetiklenemedi: <alan yok>' + Swagger'daki adı yaz (400/401 denemesi kanıt değildir).")
    if modal_istek:
        sat.append("- Hedefte Edit/Add/modal/form/alan yazımı geçiyor → ilgili satırın Edit (ya da Add/View Details) düğmesine bas, "
                   "modalı AÇ, alanları ve istenen değerin girişini (maske, ondalık, mesaj) gözle; bu salt-okunur gözlemdir, "
                   "Save'e basmadan kapat (hedef 'kaydet/payload' demiyorsa). Modalı açmadan 'yazma işlemi yapılmadı' diye bitirme.")
    for t in tasinan[:2]:
        sat.append(f"- Görev alanın yönetimini **{t}** ekranına bırakıyor → o ekrana git, ilgili satırın Edit modalını aç, alanı "
                   "değiştirip kaydet, yazma isteğini (method + path + payload alanları) `[K: Network:…]` ile yakala, değeri geri al. "
                   "Hangi UÇ olduğunu raporda açıkça yaz (kaldırılan ekranla aynı uç mu, ayrı mı). Gidemediysen 'Gezilemeyen'e yaz.")
    sat.append("- Bu listedeki her madde rapora 'denendi' ya da 'denenemedi + neden' olarak girmeden raporu BİTİRME.")
    return "\n".join(sat)


def rapor_al(canli_blok: str, kapsam: str, gorev_ozet: str = "", yeniden: bool = True,
             max_turns: int | None = None, _ai=None, tur_devam: int | None = None) -> dict:
    """Gözlem fazını çalıştırır (ya da taze raporu yeniden kullanır).
    canli_blok: `canli_uygulama_baglami_hazirla(...)` çıktısı (URL + hedef + giriş + kurallar) — motorun zaten ürettiği blok.
    kapsam: 'gorev' | 'surec' (profil/URL seti). yeniden=False → taze önbellek varsa gözlem YAPILMAZ (cevap turu vb.).
    max_turns / tur_devam: tur tavanı ve tavana takılınca bütçe yenileme hakkı (None → base varsayılanları).
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
              {"type": "text", "text": _RAPOR_FORMAT}]
    # ZORUNLU DOĞRULAMA LİSTESİ (recency — promptun SONUNA): analist notu/task belirli parametre/uç adlandırıyorsa gözlemci
    # bunları FİİLEN denemeden raporu bitiremez (MBSTRADE-1254 koşusu: not 'id/name/sportId dene' dediği hâlde 47 turda
    # yalnız varsayılan liste çağrısı yakalandı → analiz 'gözlem raporunda doğrulanamadı' dedi).
    _dl = _dogrulama_listesi(gorev_ozet)
    if _dl:
        icerik.append({"type": "text", "text": _dl})
    icerik.append({"type": "text", "text": "Gözlemi uygula ve raporu yaz."})
    ai = _ai or (lambda s, m: _api_cagri(s, m, max_tokens=MAX_TOKENS_COMBINED, thinking=False, onbellek=False,
                                         canli_uygulama_kapsami=kapsam, max_turns=max_turns, katman="yardimci",
                                         tur_devam=tur_devam))
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
