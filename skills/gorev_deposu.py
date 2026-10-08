"""Task analizi sunucu deposu (kalıcılık + kurtarma + eğitim toplama noktası).

Üretilen her Task analizi `output/gorev-analizleri/<key>.json`'a yazılır → restart/yenileme
sonrası kaybolmaz (bellekteki localStorage'a ek güvence) ve Jira'ya yazılmasa da içerik
sunucuda toplanır. **30 gün sonra otomatik silinir** (yer doldurmasın) — kayıt/okuma/boot'ta
prune edilir. output/ gitignore'da → içerik git'e girmez.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DEPO_DIR = BASE_DIR / "output" / "gorev-analizleri"
SAKLAMA_GUN = 30


def _slug(key: str) -> str:
    return (re.sub(r"[^A-Za-z0-9_-]+", "_", (key or "gorev")).strip("_") or "gorev")[:64]


def kaydet(key: str, markdown: str, acik_sorular: str = "", summary: str = "",
           katman: str = "") -> bool:
    """Task analizini depoya yazar (idempotent, key başına tek dosya = en güncel). Best-effort."""
    try:
        if not (markdown or "").strip():
            return False
        DEPO_DIR.mkdir(parents=True, exist_ok=True)
        (DEPO_DIR / f"{_slug(key)}.json").write_text(json.dumps({
            "key": key, "summary": summary or "", "katman": katman or "",
            "markdown": markdown, "acik_sorular": acik_sorular or "",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "ts_epoch": time.time(),
        }, ensure_ascii=False), encoding="utf-8")
        prune()
        return True
    except Exception:
        return False


def oku(key: str) -> dict | None:
    """Depodaki Task analizini getirir ({key,summary,katman,markdown,acik_sorular,ts}) ya da None."""
    try:
        p = DEPO_DIR / f"{_slug(key)}.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def prune(gun: int = SAKLAMA_GUN) -> int:
    """SAKLAMA_GUN'den eski kayıtları siler (yer doldurmasın). Dönen: silinen adet."""
    n = 0
    try:
        sinir = time.time() - gun * 86400
        for p in DEPO_DIR.glob("*.json"):
            try:
                if p.stat().st_mtime < sinir:
                    p.unlink(missing_ok=True)
                    n += 1
            except Exception:
                continue
    except Exception:
        pass
    return n
