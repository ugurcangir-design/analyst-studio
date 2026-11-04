"""Canlı ekran YAKALAMA (0 token) — mockup'ın baz alacağı "gerçek ekran".

Owner isteri (2026-11-04): mockup'ı sıfırdan çizdirmek yerine mevcut ekranın gerçek HTML/CSS'i + PNG'si alınır,
model yalnız DEĞİŞİKLİĞİ (yama) üretir → zaman + token tasarrufu, birebir tasarım. Spike bulguları:
- `chrome --dump-dom` YETMEZ: MUI/emotion prod'da kuralları CSSOM'a `insertRule` ile yazar, `<style>` boş serileşir →
  sayfa içinde `document.styleSheets` serileştirmesi şart → Playwright-core (npx önbelleğindeki @playwright/mcp
  kurulumuyla gelir; ek bağımlılık yok) + kurulu Chrome `channel` + agent'ın OTURUMLU profil slotu (`base._slot_al`).
- `networkidle` SPA polling'i yüzünden gelmiyor → hedef selector beklenir.
- Oturum localStorage'da; ana profil çerezsiz. Login formu görülürse ok=False (çağıran giriş kapısını çalıştırır).
Çıktı: output/mockup-kaynak/<anahtar>/{baseline.html, live.png, meta.json}; 7 gün önbellek (`EKRAN_YAKALA_ONBELLEK_GUN`).
`sadelestir()` modele gidecek DOM'u küçültür (script/svg/aria/stil atılır, tablo satırları N örnek) ~13k token.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from .base import BASE_DIR, OUTPUT_DIR, logger

MOCKUP_KAYNAK_DIR = OUTPUT_DIR / "mockup-kaynak"
_JS = BASE_DIR / "skills" / "ekran_yakala.js"
_MIN_HTML = 2000          # bundan kısa DOM = boş/hatalı sayfa


def onbellek_gun() -> float:
    try:
        return float(os.getenv("EKRAN_YAKALA_ONBELLEK_GUN", "7"))
    except (TypeError, ValueError):
        return 7.0


def _url_normalize(url: str) -> str:
    u = (url or "").strip()
    u = re.sub(r"#.*$", "", u)
    return u.rstrip("/") if u.count("/") > 2 else u


def anahtar(url: str, bekle: str = "") -> str:
    return hashlib.sha1(f"{_url_normalize(url)}|{bekle or ''}".encode()).hexdigest()[:12]


def dizin(url: str, bekle: str = "") -> Path:
    return MOCKUP_KAYNAK_DIR / anahtar(url, bekle)


# ── çalışma zamanı keşfi (Node + playwright-core) ────────────────────────────────────────────────────────
def node_yolu() -> str | None:
    yol = shutil.which("node")
    if yol:
        return yol
    ev = os.path.expanduser("~")
    adaylar = sorted(glob.glob(f"{ev}/.nvm/versions/node/*/bin/node"), reverse=True)
    adaylar += ["/opt/homebrew/bin/node", "/usr/local/bin/node"]
    return next((a for a in adaylar if os.path.exists(a)), None)


def playwright_core_dir() -> str | None:
    """`playwright-core`'un bulunduğu node_modules dizini (NODE_PATH). Öncelik env `PLAYWRIGHT_CORE_DIR`, sonra npx
    önbelleği (@playwright/mcp kurulumu), sonra global node_modules."""
    env = os.getenv("PLAYWRIGHT_CORE_DIR", "").strip()
    if env and os.path.exists(os.path.join(env, "playwright-core")):
        return env
    ev = os.path.expanduser("~")
    adaylar = glob.glob(f"{ev}/.npm/_npx/*/node_modules/playwright-core")
    adaylar += glob.glob(f"{ev}/.nvm/versions/node/*/lib/node_modules/playwright-core")
    adaylar += ["/usr/local/lib/node_modules/playwright-core", "/opt/homebrew/lib/node_modules/playwright-core"]
    adaylar = [a for a in adaylar if os.path.exists(a)]
    if not adaylar:
        return None
    adaylar.sort(key=lambda a: os.path.getmtime(a), reverse=True)
    return os.path.dirname(adaylar[0])


def hazir() -> tuple[bool, str]:
    if not node_yolu():
        return False, "Node.js bulunamadı."
    if not playwright_core_dir():
        return False, "playwright-core bulunamadı (canlı gözlem bir kez çalışınca npx önbelleğine iner)."
    if not _JS.exists():
        return False, "ekran_yakala.js eksik."
    return True, ""


def _node_calistir(arg: dict, zaman_asimi: int) -> tuple[int, str, str]:
    env = dict(os.environ)
    env["NODE_PATH"] = (playwright_core_dir() or "") + (os.pathsep + env["NODE_PATH"] if env.get("NODE_PATH") else "")
    p = subprocess.run([node_yolu() or "node", str(_JS), json.dumps(arg)], env=env, capture_output=True, text=True,
                       timeout=zaman_asimi, cwd=str(BASE_DIR))
    return p.returncode, p.stdout, p.stderr


# ── önbellek ───────────────────────────────────────────────────────────────────────────────────────────
def oku(url: str, bekle: str = "") -> dict | None:
    d = dizin(url, bekle)
    meta = d / "meta.json"
    if not (meta.exists() and (d / "baseline.html").exists()):
        return None
    try:
        m = json.loads(meta.read_text(encoding="utf-8"))
    except Exception:
        return None
    return {**m, "dizin": str(d), "baseline": str(d / "baseline.html"),
            "png": str(d / "live.png") if (d / "live.png").exists() else "",
            "yas_sn": max(0.0, time.time() - meta.stat().st_mtime)}


def taze_mi(kayit: dict | None) -> bool:
    return bool(kayit and kayit.get("ok") and kayit.get("yas_sn", 1e12) < onbellek_gun() * 86400)


# ── yakalama ───────────────────────────────────────────────────────────────────────────────────────────
def yakala(url: str, bekle: str = "", yeniden: bool = False, zaman_asimi: int = 120,
           _calistir=None, _slot=None) -> dict:
    """URL'deki ekranı oturumlu slot profiliyle yakalar. Dönen: {ok, dizin, baseline, png, neden, login, meta…,
    yeniden_kullanildi}. Taze önbellek varsa (yeniden=False) tarayıcı açılmaz. Hata akışı kırmaz → ok=False + neden."""
    url = _url_normalize(url)
    if not url.startswith("http"):
        return {"ok": False, "neden": "Geçersiz URL.", "yeniden_kullanildi": False}
    if not yeniden:
        mevcut = oku(url, bekle)
        if taze_mi(mevcut):
            return {**mevcut, "yeniden_kullanildi": True}
    ok, neden = hazir()
    if not ok and _calistir is None:
        return {"ok": False, "neden": neden, "yeniden_kullanildi": False}
    d = dizin(url, bekle)
    d.mkdir(parents=True, exist_ok=True)
    from . import base as B
    slot = _slot if _slot is not None else B._slot_al(bekle_sn=60)
    if not slot:
        return {"ok": False, "neden": "Canlı profil slotu alınamadı (havuz dolu).", "yeniden_kullanildi": False}
    n, prof = slot
    t0 = time.time()
    try:
        arg = {"profile": str(prof), "url": url, "out": str(d), "zamanAsimiMs": max(10000, (zaman_asimi - 15) * 1000)}
        if bekle:
            arg["bekle"] = bekle
        try:
            rc, out, err = (_calistir or _node_calistir)(arg, zaman_asimi)
        except subprocess.TimeoutExpired:
            return _sonuc(d, False, f"Yakalama zaman aşımı ({zaman_asimi} sn).")
        except Exception as e:
            return _sonuc(d, False, f"Yakalayıcı çalıştırılamadı: {e}")
    finally:
        if _slot is None:
            B._slot_birak(n)
    if rc != 0:
        hata = (err or out or "").strip().splitlines()[-1:] or ["bilinmeyen hata"]
        return _sonuc(d, False, f"Yakalama hatası: {hata[0][:300]}")
    try:
        meta = json.loads((out or "").strip().splitlines()[-1])
    except Exception:
        meta = {}
    html = d / "baseline.html"
    if not html.exists() or html.stat().st_size < _MIN_HTML:
        return _sonuc(d, False, "Baseline boş/eksik üretildi.", meta)
    if meta.get("login"):
        return _sonuc(d, False, "Oturum yok — sayfa giriş formuna düştü (önce 'Girişi Doğrula').", meta)
    if meta.get("erisim_yok"):
        return _sonuc(d, False, "Yetki yok — sayfa 'Access Denied' gösterdi (kayıtlı hesabın bu ekrana izni yok).", meta)
    if meta.get("beklendi") is False:
        logger.warning("Ekran yakalama: hedef selector görünmedi (%s) — baseline eksik olabilir.", url)
    logger.info("Ekran yakalandı: %s → %s (%.1f sn, html %sk, css %sk)", url, d.name, time.time() - t0,
                meta.get("html_kc", 0) // 1000, meta.get("css_kc", 0) // 1000)
    return _sonuc(d, True, "", meta)


def _sonuc(d: Path, ok: bool, neden: str, meta: dict | None = None) -> dict:
    kayit = {**(meta or {}), "ok": ok, "neden": neden, "ts": time.time()}
    try:
        (d / "meta.json").write_text(json.dumps(kayit, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass
    return {**kayit, "dizin": str(d), "baseline": str(d / "baseline.html") if ok else "",
            "png": str(d / "live.png") if (d / "live.png").exists() else "", "yeniden_kullanildi": False}


# ── modele gidecek sadeleştirilmiş DOM ──────────────────────────────────────────────────────────────────
_ATTR_SIL = re.compile(r'\s(?:data-[\w-]+|aria-(?!label|disabled)[\w-]+|tabindex|style|xmlns(?::\w+)?)="[^"]*"')


def sadelestir(html: str, satir_ornek: int = 3, azami_kc: int = 60000) -> str:
    """Baseline HTML'i model girdisine küçültür: script/noscript/style/svg gövdeleri, data-/aria-/style attr'ları atılır
    (aria-label + disabled + class KORUNUR → yama selector'ları ve durum bilgisi için); her tablo gövdesinde ilk
    `satir_ornek` satır kalır (+ '… N satır daha' notu); `azami_kc` aşılırsa kuyruk kırpılır."""
    s = html or ""
    s = re.sub(r"<script\b.*?</script>", "", s, flags=re.S)
    s = re.sub(r"<noscript\b.*?</noscript>", "", s, flags=re.S)
    s = re.sub(r"<style\b.*?</style>", "", s, flags=re.S)
    s = re.sub(r"<svg\b.*?</svg>", "<svg/>", s, flags=re.S)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = _ATTR_SIL.sub("", s)

    def _tbody(m):
        govde = m.group(2)
        satirlar = re.findall(r"<tr\b.*?</tr>", govde, flags=re.S)
        if len(satirlar) <= satir_ornek:
            return m.group(0)
        kalan = len(satirlar) - satir_ornek
        return m.group(1) + "".join(satirlar[:satir_ornek]) + f"<!-- … {kalan} satır daha (aynı yapı) -->" + m.group(3)

    s = re.sub(r"(<tbody\b[^>]*>)(.*?)(</tbody>)", _tbody, s, flags=re.S)
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{2,}", "\n", s)
    s = re.sub(r">\s+<", "><", s)
    if len(s) > azami_kc:
        s = s[:azami_kc] + "\n<!-- … kırpıldı -->"
    return s


def ozet(kayit: dict) -> str:
    """Analist/HUD için tek satır."""
    if not kayit:
        return "ekran yakalanmadı"
    if kayit.get("ok"):
        return (f"ekran yakalandı ({'önbellek' if kayit.get('yeniden_kullanildi') else 'taze'} · "
                f"{kayit.get('title', '')[:40]})")
    return f"ekran yakalanamadı — {kayit.get('neden', '')}"


def herhangi_baseline(url: str) -> dict | None:
    """Aynı origin'den en TAZE başarılı yakalamayı döndürür (yeni-ekran KABUĞU için). Yoksa None."""
    from urllib.parse import urlparse
    try:
        origin = urlparse(_url_normalize(url)).netloc
    except Exception:
        return None
    if not origin or not MOCKUP_KAYNAK_DIR.exists():
        return None
    adaylar = []
    for d in MOCKUP_KAYNAK_DIR.iterdir():
        m = d / "meta.json"
        if not (m.exists() and (d / "baseline.html").exists()):
            continue
        try:
            k = json.loads(m.read_text(encoding="utf-8"))
        except Exception:
            continue
        if k.get("ok") and urlparse(str(k.get("url", ""))).netloc == origin:
            adaylar.append((m.stat().st_mtime, d, k))
    if not adaylar:
        return None
    mt, d, k = max(adaylar, key=lambda a: a[0])
    return {**k, "dizin": str(d), "baseline": str(d / "baseline.html"), "png": str(d / "live.png") if (d / "live.png").exists() else "",
            "yas_sn": max(0.0, time.time() - mt)}
