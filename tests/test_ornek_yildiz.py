"""★ İyi örnek kürasyonu (offline, 0 token): yildiz_ayarla tracked id dosyasına yazar, ornek_listesi bayrağı taşır ve
işaretlileri öne alır, ornek_bloklari few-shot seçiminde işaretlileri (alaka sırası korunarak) ÖNCE verir; uç doğrulaması."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("AUTO_UPDATE", "false")
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("SIRKET_EPOSTA_DOMAIN", "example.com")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skills import ornek_havuzu as O  # noqa: E402

HATA = 0


def chk(ad, kosul, ek=""):
    global HATA
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if (ek and not kosul) else ""))
    if not kosul:
        HATA += 1


tmp = Path(tempfile.mkdtemp())
O.YILDIZ_DOSYA = tmp / "ornek_yildiz.json"
havuz = [
    {"id": "a1", "tip": "teknik", "ts": "2026-10-01T00:00:00", "icerik": "ödeme servisi endpoint validasyon " * 40, "jira_key": "X-1"},
    {"id": "b2", "tip": "teknik", "ts": "2026-10-05T00:00:00", "icerik": "rapor ekranı filtre tablo " * 40, "jira_key": "X-2"},
    {"id": "c3", "tip": "teknik", "ts": "2026-10-03T00:00:00", "icerik": "ödeme iade akışı endpoint " * 40, "jira_key": "X-3"},
]
O._oku_hepsi = lambda: [dict(o) for o in havuz]

chk("başta yıldız yok", O.yildizlar() == set())
ids = O.yildiz_ayarla("b2", True)
chk("işaretle → dosyaya yazıldı (yalnız id)", ids == {"b2"} and O.YILDIZ_DOSYA.exists() and "b2" in O.YILDIZ_DOSYA.read_text(encoding="utf-8")
    and "icerik" not in O.YILDIZ_DOSYA.read_text(encoding="utf-8"))
L = O.ornek_listesi()
chk("liste: yıldızlı önce + bayrak + boyut", L[0]["id"] == "b2" and L[0]["yildiz"] is True and L[1]["yildiz"] is False and L[0]["boyut"] > 0, [x["id"] for x in L])
bl = O.ornek_bloklari("ödeme endpoint validasyon", tip="teknik", n=2)
chk("few-shot: alakasız ama ★ işaretli b2 İLK, sonra en alakalı ödeme örneği", len(bl) == 2 and "X-2" in bl[0]["text"] and ("X-1" in bl[1]["text"] or "X-3" in bl[1]["text"]), [b["text"][:80] for b in bl])
O.yildiz_ayarla("b2", False)
bl2 = O.ornek_bloklari("ödeme endpoint validasyon", tip="teknik", n=2)
chk("işaret kalkınca saf alaka sırası (ödeme örnekleri)", len(bl2) == 2 and all("X-2" not in b["text"] for b in bl2))
O.yildiz_ayarla("a1", True)
O.yildiz_ayarla("c3", True)
bl3 = O.ornek_bloklari("rapor ekranı filtre", tip="teknik", n=2)
chk("iki ★ varken n=2 dolar → işaretsiz en alakalı (b2) girmez", all("X-2" not in b["text"] for b in bl3) and len(bl3) == 2)

import app as A  # noqa: E402
c = A.app.test_client()
H = {"Origin": "http://localhost"}
r = c.post("/api/ornekler/yildiz", json={}, headers=H)
chk("uç: yetki kapısı (yetki_gerekli) ya da id doğrulaması", r.status_code in (400, 403))
print()
if HATA:
    print(f"FAIL — {HATA} kontrol başarısız")
    sys.exit(1)
print("ÖRNEK YILDIZ TESTLERİ GEÇTİ")
