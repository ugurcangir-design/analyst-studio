"""Yerel masaüstü bildirimi (macOS) — 0 bağımlılık, 0 token, best-effort.

Her analist KENDİ makinesinde çalışır → bildirimler YERELDİR (hiçbir veri makineden
çıkmaz, yalnız macOS Bildirim Merkezi'ne yerel mesaj). Kapatma: `.env BILDIRIM=false`.
macOS dışında (şimdilik) no-op — Windows bildirimi sonraki faz.

`gonder()` ASLA exception yükseltmez: bildirim başarısız olsa bile ana akış (analiz,
köprü turu) bozulmaz. base.py'yi IMPORT ETMEZ → run.py/workflow.py'de de ucuzdur.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

# Bariz sır desenleri — bildirim metni caller-kontrollü olsa da savunma amaçlı maskele
# (doküman adı + sayı beklenir; yine de sk-…/parola/anahtar sızarsa gizle).
_SIR_DESEN = re.compile(
    r"(sk-[A-Za-z0-9_\-]{8,}|(?i:password|passwd|api[_-]?key|token|secret)\s*[=:]\s*\S+)"
)


def acik_mi() -> bool:
    """BILDIRIM env'i (varsayılan açık). false/0/hayır/off → kapalı."""
    return os.getenv("BILDIRIM", "true").strip().lower() not in (
        "false", "0", "hayir", "hayır", "off", "kapali", "kapalı",
    )


def _redakte(s: str) -> str:
    return _SIR_DESEN.sub("«sır»", s or "")


def _kacir(s: str) -> str:
    """AppleScript string kaçışı (\\ ve ") + tek satıra indir (notification tek satırdır)."""
    s = _redakte(s).replace("\\", "\\\\").replace('"', '\\"')
    return " ".join(s.split())


def gonder(baslik: str, metin: str, alt_metin: str = "") -> bool:
    """macOS Bildirim Merkezi'ne yerel bildirim gönderir. Döner: gönderildi mi.

    Best-effort: BILDIRIM=false, macOS değil veya osascript yoksa no-op → False.
    Hata YUTAR (asla yükseltmez)."""
    if not acik_mi() or sys.platform != "darwin":
        return False
    if not shutil.which("osascript"):
        return False
    metin_k, baslik_k = _kacir(metin), _kacir(baslik)
    script = f'display notification "{metin_k}" with title "{baslik_k}"'
    if alt_metin:
        script += f' subtitle "{_kacir(alt_metin)}"'
    try:
        subprocess.run(
            ["osascript", "-e", script], timeout=5,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
        return True
    except Exception:
        return False
