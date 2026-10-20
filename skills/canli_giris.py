"""Canlı uygulama GİRİŞ KAPISI — analiz başlamadan önce kayıtlı test hesabıyla giriş doğrulanır.

Owner isteri (2026-10-16, Task Analizi): "URL'e giriş yapılmadıysa uyarı ver ve analizi başlatma; URL yoksa 'canlı gözlem
yapılmadan analiz yapılacak' diye bilgi ver, öyle başla." Eskiden yanlış şifre ancak analiz bittikten sonra (login
duvarında kalan gözlem) fark ediliyordu → dakikalar + token boşa gidiyordu.

- `durum(kapsam)` (0 token): hedef URL var mı · son giriş testi sonucu · TAZE mi (URL+kullanıcı+şifre imzası aynı ve
  `GIRIS_TEST_GECERLILIK` sn içinde) · analiz öncesi test gerekli mi.
- `test_et(kapsam)`: 1 CLI/Playwright çağrısı — ana adrese git, giriş yap, ilk ekranı bildir → `output/.giris-durum-<kapsam>.json`.
  Sonuç imzayla saklanır: Bağlam Filtresi'nde URL ya da giriş bilgisi değişince otomatik geçersizleşir.
kapsam: 'gorev' (Task Analizi `live_app_gorev`) · 'surec' (Süreç/Teknik + İnteraktif `live_app`). İnteraktif Analiz'in
"Girişi Test Et" düğmesi de aynı çekirdeği kullanır (sohbet_analiz.giris_testi → test_et('surec')).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from urllib.parse import urlparse

from .base import (
    OUTPUT_DIR, MAX_TOKENS_KISA,
    _api_cagri, _xml_ayir, _metin_sikistir, load_context_filter, asama_ayarla,
    canli_uygulama_baglami_hazirla, gorev_live_app_urls, live_app_urls, oturum_durumu,
)

KAPSAMLAR = ("gorev", "surec")


def gecerlilik_sn() -> int:
    try:
        return max(60, int(os.getenv("GIRIS_TEST_GECERLILIK", "3600")))
    except (TypeError, ValueError):
        return 3600


def hedef_url(kapsam: str) -> str:
    urls = gorev_live_app_urls() if kapsam == "gorev" else live_app_urls()
    u = (urls[0] if urls else "").strip()
    p = urlparse(u)
    return u if p.scheme and p.netloc else ""


def _imza(kapsam: str) -> str:
    ctx = load_context_filter() or {}
    auth = ctx.get("live_app_auth") if isinstance(ctx.get("live_app_auth"), dict) else {}
    ham = f"{hedef_url(kapsam)}|{auth.get('username', '')}|{auth.get('password', '')}"
    return hashlib.sha1(ham.encode("utf-8")).hexdigest()[:16]


def _dosya(kapsam: str):
    return OUTPUT_DIR / f".giris-durum-{kapsam}.json"


def _oku(kapsam: str) -> dict | None:
    try:
        p = _dosya(kapsam)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except Exception:
        return None


def kaydet(kapsam: str, sonuc: dict) -> None:
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        _dosya(kapsam).write_text(json.dumps({**sonuc, "imza": _imza(kapsam), "ts": sonuc.get("ts") or time.time()},
                                             ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def durum(kapsam: str) -> dict:
    """{kapsam, url, var, giris:{ok,neden,ekran,ts,taze}|None, gerekli, mesaj}.
    gerekli=True → analiz öncesi giriş testi çalıştırılmalı (URL var ama taze/başarılı sonuç yok)."""
    kapsam = kapsam if kapsam in KAPSAMLAR else "gorev"
    url = hedef_url(kapsam)
    if not url:
        return {"kapsam": kapsam, "url": "", "var": False, "giris": None, "gerekli": False,
                "mesaj": "Canlı uygulama hedefi tanımlı değil — analiz canlı gözlem YAPILMADAN üretilecek."}
    g = _oku(kapsam)
    taze = bool(g) and g.get("imza") == _imza(kapsam) and (time.time() - float(g.get("ts") or 0)) < gecerlilik_sn()
    # Kota (2026-10-19): agent'ın KENDİ girişiyle kaydedilmiş TAZE oturum varsa (profil havuzu geri yazımı) giriş testi
    # ATLANIR — her analiz öncesi ~9 turluk/0.5M okuma testi gereksiz; gözlem zaten kayıtlı oturumla açılır, düşerse
    # OTOMATİK GİRİŞ devreye girer. Yalnız başarısız taze sonuç (şifre yanlış) bu atlamayı ezer (analiz başlamasın).
    try:
        o = oturum_durumu() or {}
    except Exception:
        o = {}
    oturum_taze = bool(o.get("var")) and o.get("kaynak") == "agent" and float(o.get("yas_dk") or 1e9) * 60 < gecerlilik_sn()
    # Atlama HOST BAZLI: agent oturumu başka bir uygulamada (örn. Task hedefi) açılmış olabilir → bu kapsamın host'u için
    # geçerli değildir. Oturum kaydında host varsa onunla; yoksa bu kapsamın SON BAŞARILI giriş kaydının host'uyla
    # karşılaştırılır (aynı host'ta daha önce girilmişse çerez o host'a aittir). Hiçbiri eşleşmiyorsa atlanmaz.
    if oturum_taze and not _oturum_bu_host_icin_mi(o, url, g):
        oturum_taze = False
    if oturum_taze and not (taze and g and not g.get("ok")):
        return {"kapsam": kapsam, "url": url, "var": True, "gerekli": False, "oturum": o,
                "giris": {"ok": True, "neden": "", "ekran": "", "ts": float(o.get("son_giris") or 0), "taze": True},
                "mesaj": f"Kayıtlı oturum var (agent girişi · {int(o.get('yas_dk') or 0)} dk önce) — giriş testi atlandı."}
    giris = None
    if g:
        giris = {"ok": bool(g.get("ok")), "neden": str(g.get("neden") or ""), "ekran": str(g.get("ekran") or ""),
                 "ts": float(g.get("ts") or 0), "taze": taze}
    gerekli = not (taze and giris and giris["ok"])
    if giris and giris["ok"] and taze:
        mesaj = f"Giriş doğrulandı ({giris['ekran'] or url})."
    elif giris and not giris["ok"] and taze:
        mesaj = f"Giriş BAŞARISIZ — {giris['neden'] or 'neden belirlenemedi'}. Analiz başlatılmaz."
    else:
        mesaj = "Giriş henüz doğrulanmadı — analiz öncesi test edilecek."
    return {"kapsam": kapsam, "url": url, "var": True, "giris": giris, "gerekli": gerekli, "mesaj": mesaj}


def _host(u: str) -> str:
    """URL ya da çıplak host adından host (küçük harf). 'https://a.local/x' → 'a.local' · 'a.local' → 'a.local'."""
    u = (u or "").strip()
    if not u:
        return ""
    p = urlparse(u if "://" in u else "//" + u)
    return (p.netloc or "").lower()


def _oturum_bu_host_icin_mi(oturum: dict, url: str, son_giris: dict | None) -> bool:
    """Kayıtlı agent oturumu BU kapsamın host'u için mi? Oturum kaydında `host` varsa doğrudan; yoksa bu kapsamın son
    BAŞARILI giriş kaydındaki URL host'u ile aynıysa evet; aksi hâlde hayır (atlama yapılmaz, giriş test edilir)."""
    h = _host(url)
    if not h:
        return False
    kayitli = _host(str(oturum.get("host") or oturum.get("url") or ""))
    if kayitli:
        return kayitli == h
    if son_giris and son_giris.get("ok") and _host(str(son_giris.get("url") or "")) == h:
        return True
    return False


def giris_calistir(canli: str, kapsam: str, _ai=None) -> dict:
    """Hazır canlı görev bloğuyla giriş denemesi (çekirdek). Dönen: {ok, neden, ekran, menu, ts}."""
    sistem = ("Canlı uygulama ERİŞİM testçisisin. Tek görevin: ana adrese gidip kayıtlı hesapla giriş yapmak ve "
              "sonucu bildirmek. Gezme, analiz yapma, varsayım üretme.")
    icerik = [{"type": "text", "text": canli}, {"type": "text", "text": (
        "### GÖREV\n1) Ana adrese git. 2) Giriş formu varsa kayıtlı hesapla giriş yap (bir kez). 3) Sonucu bildir.\n"
        "Çıktı YALNIZ şu blok:\n<giris_sonuc>{\"ok\": true, \"neden\": \"\", \"ekran\": \"giriş sonrası sayfa başlığı/route\", "
        "\"menu\": [\"üst menü öğeleri\"]}</giris_sonuc>\nGiriş reddedildiyse ok=false ve neden'e ekrandaki hata metnini AYNEN yaz. "
        "Giriş formu hiç çıkmadıysa (oturum zaten açık) ok=true. Şifreyi yazma.")}]
    asama_ayarla("giris")
    ai = _ai or (lambda s, m, k=kapsam: _api_cagri(s, m, max_tokens=MAX_TOKENS_KISA, thinking=False, onbellek=False,
                                                  canli_uygulama_kapsami=k, katman="yardimci"))
    try:
        yanit = ai(sistem, [{"role": "user", "content": icerik}])
        ham = _xml_ayir(_metin_sikistir(yanit or ""), "giris_sonuc")
        try:
            d = json.loads(ham)
        except Exception:
            a, b = ham.find("{"), ham.rfind("}")
            d = json.loads(ham[a:b + 1]) if a != -1 and b > a else {}
        sonuc = {"ok": bool(d.get("ok")), "neden": str(d.get("neden") or "").strip(),
                 "ekran": str(d.get("ekran") or "").strip(),
                 "menu": [str(x) for x in (d.get("menu") or []) if str(x).strip()][:30]}
        if not d:
            sonuc["neden"] = "Giriş sonucu okunamadı (tarayıcı aracı çalışmamış olabilir)."
    except Exception as e:
        sonuc = {"ok": False, "neden": f"Giriş testi çalıştırılamadı: {str(e)[:200]}", "ekran": "", "menu": []}
    sonuc["ts"] = time.time()
    return sonuc


def test_et(kapsam: str, _ai=None) -> dict:
    """Kapsamın hedefine giriş dener, sonucu imzayla kaydeder. URL yoksa AI çağrılmaz."""
    kapsam = kapsam if kapsam in KAPSAMLAR else "gorev"
    url = hedef_url(kapsam)
    if not url:
        return {"ok": False, "neden": "Canlı uygulama hedefi tanımlı değil (Bağlam Filtresi).", "ekran": "", "menu": [],
                "ts": time.time(), "url": ""}
    p = urlparse(url)
    tarif = "GİRİŞ TESTİ — yalnız giriş yap ve açılan ilk ekranı/üst menüyü bildir; başka ekran gezme."
    if kapsam == "gorev":
        canli = canli_uygulama_baglami_hazirla(gorev=True, hedef_tarif=tarif)
    else:
        canli = canli_uygulama_baglami_hazirla(base_url_override=f"{p.scheme}://{p.netloc}", hedef_tarif=tarif)
    if not canli:
        return {"ok": False, "neden": "Canlı görev hazırlanamadı (npx/MCP yok?).", "ekran": "", "menu": [], "ts": time.time(), "url": url}
    sonuc = giris_calistir(canli, kapsam, _ai=_ai)
    sonuc["url"] = url
    kaydet(kapsam, sonuc)
    return sonuc
