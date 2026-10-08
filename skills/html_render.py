"""HTML → PNG görsel render (kurulu tarayıcı headless ekran görüntüsü).

Amaç: Ekran mockup'ı (HTML) Jira'ya eklenince Jira HTML'i satır-içi render ETMEZ (kaynak
gösterir). Bir PNG görsel eklersek Jira onu satır-içi gösterir → tasarım görünür olur.

Yöntem: kurulu Google Chrome / Chromium / Edge / Brave'i `--headless --screenshot` ile
çalıştırır (ek bağımlılık YOK; playwright chromium indirmeye gerek yok). Chrome ekran
görüntüsünü yazdıktan SONRA arka plan updater süreçleri yüzünden hemen çıkmayabilir →
PNG dosyası oluşunca süreci PROCESS GRUBUYLA öldürürüz (asılı kalmaz). Fail-safe: tarayıcı
yoksa / hata olursa False döner, çağıran HTML-only'ye düşer.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path


def _chrome_yolu() -> str:
    """Kurulu bir Chromium-tabanlı tarayıcının yolunu bulur (yoksa '')."""
    c = os.getenv("CHROME_PATH", "").strip()
    if c and Path(c).exists():
        return c
    adaylar = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ]
    for a in adaylar:
        if Path(a).exists():
            return a
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        w = shutil.which(name)
        if w:
            return w
    return ""


def tarayici_var() -> bool:
    return bool(_chrome_yolu())


def html_to_png(html_yolu, png_yolu, genislik: int = 1440, yukseklik: int = 3600,
                timeout: int = 45) -> bool:
    """`html_yolu` dosyasını headless tarayıcıyla render edip `png_yolu`'ya PNG yazar.
    Başarıda True. Fail-safe (tarayıcı yok / hata → False). Çıktı oluşunca süreç PROCESS
    GRUBUYLA öldürülür (Chrome updater yüzünden asılı kalmaz)."""
    chrome = _chrome_yolu()
    if not chrome:
        return False
    html_yolu = Path(html_yolu).resolve()
    png_yolu = Path(png_yolu)
    if not html_yolu.exists():
        return False
    try:
        if png_yolu.exists():
            png_yolu.unlink()
    except Exception:
        pass
    prof = tempfile.mkdtemp(prefix="mockup-chrome-")
    cmd = [
        chrome, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
        "--no-first-run", "--no-default-browser-check", "--disable-extensions",
        "--disable-background-networking", "--disable-component-update",
        f"--screenshot={png_yolu}", f"--window-size={genislik},{yukseklik}",
        "--force-device-scale-factor=1", "--default-background-color=ffffffff",
        f"--user-data-dir={prof}", html_yolu.as_uri(),
    ]
    proc = None
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)
        t0 = time.time()
        while time.time() - t0 < timeout:
            if png_yolu.exists() and png_yolu.stat().st_size > 1000:
                time.sleep(0.3)   # yazımın bitmesine küçük pay
                return png_yolu.stat().st_size > 1000
            if proc.poll() is not None:
                break
            time.sleep(0.4)
        return png_yolu.exists() and png_yolu.stat().st_size > 1000
    except Exception:
        return False
    finally:
        if proc is not None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        shutil.rmtree(prof, ignore_errors=True)
