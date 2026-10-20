"""Opt-in Ekran Görüntüsü yakalama (offline, 0 token; AI + Jira attach MOCK).

yakala(): analizi + canlı bloğu alır, AI'ya screenshot talimatı verir, diske düşen PNG'leri agent'ın bildirdiği sıra/
açıklamayla eşler. jiraya_ekle(): her PNG'yi atlassian_attach ile yükler (her biri ayrı try). Hedef yok / PNG yok →
ok:False, akış kırılmaz.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skills import ekran_goruntu as EG  # noqa: E402

HATA = 0


def chk(ad, kosul, ek=""):
    global HATA
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if (ek and not kosul) else ""))
    if not kosul:
        HATA += 1


tmp = Path(tempfile.mkdtemp())
EG.EKRAN_GORUNTU_DIR = tmp

# ── yakala: hedef yok → AI çağrılmaz, ok False ──
chk("canlı hedef yok → ok False, AI yok", EG.yakala("analiz", "", "gorev", _ai=lambda s, m: (_ for _ in ()).throw(AssertionError("AI!")))["ok"] is False)

# ── yakala: 2 PNG diske düşer, agent 2 açıklama bildirir → eşleşir ──
import time as _t  # noqa: E402


def _ai_2png(s, m):
    # agent iki ekranı çeker (diske PNG düşmesini taklit et) + rapor bloğu
    for i in range(2):
        (tmp / f"page-{i}.png").write_bytes(b"\x89PNG" + bytes([i]))
        _t.sleep(0.01)
    return ('<ekran_goruntu>[{"sira":1,"ekran":"Market Setup > Market Per Sport — Edit modalı","aciklama":"Main Market switch\'leri"},'
            '{"sira":2,"ekran":"Market Mapping Data > Definitions — Edit modalı","aciklama":"Pre/Live Main Market"}]</ekran_goruntu>')


r = EG.yakala("## Çözüm\n4 modal...", "canlı blok", "gorev", _ai=_ai_2png)
chk("2 PNG + 2 açıklama → ok, sıralı eşleşme", r["ok"] and len(r["goruntular"]) == 2
    and r["goruntular"][0]["ekran"].startswith("Market Setup") and r["goruntular"][1]["ekran"].startswith("Market Mapping")
    and all(Path(g["yol"]).exists() for g in r["goruntular"]), r.get("neden"))

# ── klasör yakalamadan önce temizlenir (eski PNG taşınmaz) ──
(tmp / "eski.png").write_bytes(b"\x89PNG")


def _ai_1png(s, m):
    (tmp / "yeni.png").write_bytes(b"\x89PNG")
    return '<ekran_goruntu>[{"sira":1,"ekran":"Tek ekran","aciklama":"x"}]</ekran_goruntu>'


r2 = EG.yakala("analiz", "canlı", "gorev", _ai=_ai_1png)
chk("yakalama öncesi klasör temizlenir → yalnız yeni PNG (eski.png eşleşmez)",
    r2["ok"] and len(r2["goruntular"]) == 1 and Path(r2["goruntular"][0]["yol"]).name == "yeni.png")

# ── PNG hiç yok → ok False ──
r3 = EG.yakala("analiz", "canlı", "gorev", _ai=lambda s, m: "<ekran_goruntu>[]</ekran_goruntu>")
chk("agent screenshot almadı (PNG yok) → ok False + neden", r3["ok"] is False and "alınamadı" in r3["neden"])

# ── guvenli ad ──
chk("dosya adı güvenli (slug + sıra)", EG._guvenli_ad("Market Setup > Market Per Sport — Edit", 0) == "01-market-setup-market-per-sport-edit.png")
chk("boş ekran adı → fallback", EG._guvenli_ad("", 2).endswith(".png") and "ekran-3" in EG._guvenli_ad("", 2))

# ── jiraya_ekle: her PNG attach, biri hatalı olsa diğeri gider ──
ekli = []


def _sahte_attach(key, ad, icerik, content_type="", cloud_id=""):
    if "02" in ad:
        raise RuntimeError("Jira reddetti")
    ekli.append((key, ad, content_type))
    return [{"id": "1"}]


import skills.atlassian as _atl  # noqa: E402
_atl.atlassian_attach = _sahte_attach
(tmp / "a.png").write_bytes(b"\x89PNG")
(tmp / "b.png").write_bytes(b"\x89PNG")
g = [{"yol": str(tmp / "a.png"), "ekran": "Ekran A"}, {"yol": str(tmp / "b.png"), "ekran": "Ekran B"}]
res = EG.jiraya_ekle("MBSUATEAM-181", g, cloud_id="c")
chk("jiraya_ekle: 1 eklendi (image/png), 2. hata yakalandı (ayrı try)",
    len(res["eklenen"]) == 1 and res["eklenen"][0]["dosya"] == "01-ekran-a.png" and ekli[0][2] == "image/png"
    and len(res["hatalar"]) == 1 and "02-ekran-b" in res["hatalar"][0], res)
chk("dosya yoksa hata listesine, patlamaz", EG.jiraya_ekle("K-1", [{"yol": str(tmp / "yok.png"), "ekran": "X"}])["ok"] is False)

print()
if HATA:
    print(f"FAIL — {HATA} kontrol başarısız")
    sys.exit(1)
print("EKRAN GÖRÜNTÜSÜ TESTLERİ GEÇTİ")
