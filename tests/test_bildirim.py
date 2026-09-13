"""Bildirim altyapısı — offline birim testi (0 token, gerçek bildirim ATEŞLENMEZ).

Kapalıyken no-op, redaksiyon ve AppleScript kaçışı doğrulanır.
Çalıştır:  venv/bin/python tests/test_bildirim.py
"""

import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

import skills.bildirim as b  # noqa: E402

basari = 0


def kontrol(ad: str, kosul: bool) -> None:
    global basari
    if not kosul:
        raise SystemExit(f"FAIL {ad}")
    basari += 1
    print(f"  ✓ {ad}")


# ── acik_mi: BILDIRIM env ──────────────────────────────────────────────────────
os.environ["BILDIRIM"] = "false"
kontrol("BILDIRIM=false → kapalı", b.acik_mi() is False)
kontrol("kapalıyken gonder() no-op → False (hata YOK)", b.gonder("Başlık", "metin") is False)
os.environ["BILDIRIM"] = "true"
kontrol("BILDIRIM=true → açık", b.acik_mi() is True)
os.environ.pop("BILDIRIM", None)
kontrol("varsayılan (env yok) → açık", b.acik_mi() is True)

# ── redaksiyon: sır sızıntısı maskelenir ──────────────────────────────────────
kontrol("sk-… anahtarı maskelenir", "«sır»" in b._redakte("anahtar sk-ABCD1234EFGH5678 burada"))
kontrol("password=… maskelenir", "«sır»" in b._redakte("giriş password=gizli123"))
kontrol("normal metin dokunulmaz", b._redakte("5 açık soru çıkarıldı") == "5 açık soru çıkarıldı")

# ── AppleScript kaçışı: " ve \ + tek satır ────────────────────────────────────
kacik = b._kacir('«Doküman "A"» sürüm\\1\nyeni satır')
kontrol("çift tırnak kaçışlanır", '\\"' in kacik)
kontrol("ters bölü kaçışlanır", "\\\\" in kacik)
kontrol("newline tek satıra iner", "\n" not in kacik)

print(f"\nBİLDİRİM TESTLERİ GEÇTİ ({basari} kontrol)")
