"""Kullanım Raporu — Analist Özeti seçili dönem kartına (bugün / bu hafta / bu ay) göre; tüm zamanlar toplamı (owner 2026-11-06)."""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("TELEMETRI_SINK", "off")
from skills import telemetri as T  # noqa: E402

now = datetime.now()


def ev(gun_once, analist, olay="gorev_analiz", task=0):
    ts = (now - timedelta(days=gun_once)).strftime("%Y-%m-%dT%H:%M:%S")
    return {"ts": ts, "analist": analist, "olay": olay, "durum": "ok", "sure_ms": 1000, **({"jira": {"toplam": task}} if task else {})}


# bugün: Emin 2 · 10 gün önce: Elif 1 (son 30 gün içinde) · 100 gün önce: Uğur 1 (aralık dışı) · kimlik olayı sayılmaz
T.olaylari_oku = lambda: [ev(0, "Emin"), ev(0, "Emin", "sohbet"), ev(10, "Elif", task=2), ev(100, "Uğur", "jira_gonder", task=1),
                          {"ts": now.strftime("%Y-%m-%dT%H:%M:%S"), "analist": "X", "olay": "kimlik"}]
hatalar = []


def chk(ad, kosul, ek=""):
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f" — {ek}" if ek and not kosul else ""))
    if not kosul:
        hatalar.append(ad)


d = T.istatistik(gun=30, donem="gun", pencere="bugun")
chk("pencere=bugun: Analist Özeti yalnız bugünün olayları (Emin 2)", [a["analist"] for a in d["analistler"]] == ["Emin"] and d["analistler"][0]["toplam"] == 2 and d["toplam_analiz"] == 2)
chk("aktivite kartları aralıktan: bugün 2, bu ay ≥ 2", d["ozet"]["bugun"] == 2 and d["ozet"]["bu_ay"] >= 2)
chk("tüm zamanlar: 4 işlem, 3 task (kimlik hariç, aralık dışı dahil)", d["tum_zaman_toplam"] == 4 and d["tum_zaman_task"] == 3, (d["tum_zaman_toplam"], d["tum_zaman_task"]))
d2 = T.istatistik(gun=30, donem="hafta", pencere="aralik")
chk("pencere verilmezse/aralik: eski davranış (son 30 gün: Emin + Elif)", sorted(a["analist"] for a in d2["analistler"]) == ["Elif", "Emin"] and d2["toplam_jira_task"] == 2)
d3 = T.istatistik(gun=365, donem="ay", pencere="ay")
chk("pencere=ay: yalnız bu ay (100 gün önceki Uğur yok)", "Uğur" not in [a["analist"] for a in d3["analistler"]] and d3["pencere"] == "ay")
chk("geçersiz pencere → aralik", T.istatistik(gun=30, pencere="x")["pencere"] == "aralik")

print(f"\n{'KULLANIM PENCERE TESTLERİ GEÇTİ' if not hatalar else 'HATA: ' + ', '.join(hatalar)}")
sys.exit(1 if hatalar else 0)
