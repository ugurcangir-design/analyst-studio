"""FE+BE setinde 'Cevapları İşle' — cevap KARDEŞ katmana da işlenir (owner 2026-11-04, MBSUATEAM-105; offline, AI/Jira MOCK).

Bulgu: BE'de cevaplanan Q-T-001 FE sekmesinde tekrar çıkıyordu — iş yalnız aktif katmanı işliyor, FE analizi + FE sunucu
deposu bayat kalıyordu. Artık adım `kardes:{key, katman, markdown}` taşır → ikinci hedefli uygulama (soru üretimi YOK,
deterministik yakınsama) → sonuc.kardes + her iki depo yazılır; UI kardeş entry'yi tazeler.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("JIRA_KOPRU", "false")
os.environ.setdefault("JIRA_KOPRU_PROJELER", "")
os.environ.setdefault("TELEMETRI_SINK", "off")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

HATA = 0


def chk(ad, kosul, ek=""):
    global HATA
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if (ek and not kosul) else ""))
    if not kosul:
        HATA += 1


tmp = Path(tempfile.mkdtemp())
from skills import jira_gorevleri as jg  # noqa: E402
from skills import base as B  # noqa: E402

# ── 1 gorev_cevap_uygula(sorular_uret=False): soru üretimi çağrılmaz, deterministik yakınsama ──
jg.gorev_analiz_duzelt = lambda gorev, govde, talimat, asama="gorev:duzelt", **k: govde + "\n\n[CEVAP işlendi]"
sayac = {"soru": 0}
jg._gorev_acik_sorular_uret = lambda *a, **k: sayac.__setitem__("soru", sayac["soru"] + 1) or "### Q-T-009: yeni?\n- Soru: ?"
onceki = "### Q-T-001: konum?\n- Soru: a\n\n### Q-T-002: diğer?\n- Soru: b"
r = jg.gorev_cevap_uygula({"key": "X-1", "summary": "s"}, "## Amaç\nx", "Q-T-001: (a) sport ile group arası", onceki, sorular_uret=False)
chk("kardeş modu: soru üretimi YOK, cevaplanan düşer, kalan korunur", sayac["soru"] == 0 and "[CEVAP işlendi]" in r["markdown"]
    and "Q-T-001" not in r["acik_sorular"] and "Q-T-002" in r["acik_sorular"])
r = jg.gorev_cevap_uygula({"key": "X-1", "summary": "s"}, "## Amaç\nx", "Q-T-001: a", onceki)
chk("normal mod: soru üretimi çağrılır", sayac["soru"] == 1 and "Q-T-009" in r["acik_sorular"])

# ── 2 app işi: mode cevap + kardes → sonuc.kardes + iki depo ──
import app as A  # noqa: E402
from skills import telemetri as _tel  # noqa: E402
_tel.USAGE_DIR = tmp / "usage"
_tel.EVENTS_DOSYA = tmp / "usage" / "events.jsonl"
_tel._sink_gonder = lambda k: None
A.OUTPUT_DIR = tmp
A.REF_DIR = tmp
B.CONTEXT_FILTER_PATH = tmp / "context_filter.json"
A._kimlik_tam_mi = lambda *a, **k: True
A._telemetri_olay = lambda *a, **k: None
depo = []
A._gorev_egitim_topla = lambda key, summary, katman, mode, sonuc: depo.append((key, katman, mode, (sonuc.get("markdown") or "")[:40], sonuc.get("acik_sorular", "")))
from skills import bff_kesif  # noqa: E402
bff_kesif.otomatik_acik = lambda: False
bff_kesif.rapor_oku = lambda *a, **k: None
from skills import mockup_yama as MY  # noqa: E402
MY.otomatik_acik = lambda kapsam="gorev": False
gorev = {"key": "MBSUATEAM-105", "summary": "Market Per Sport satırı", "description": "d", "status": "Backlog", "issuetype": "Görev"}
jg.gorev_getir = lambda key: gorev
cagri = []


def _cevap(gorev, mevcut, cevaplar, onceki_sorular="", sorular_uret=True):
    cagri.append((mevcut, sorular_uret, cevaplar, onceki_sorular))
    return {"markdown": mevcut + "\n[CEVAP]", "acik_sorular": "Açık soru tespit edilmedi." if sorular_uret else jg._cevaplanan_sorulari_dus(onceki_sorular, cevaplar), "hedefli": True}


jg.gorev_cevap_uygula = _cevap
c = A.app.test_client()
H = {"Origin": "http://localhost"}
adim = {"key": "MBSUATEAM-105", "mode": "cevap", "katman": "be", "markdown": "## BE analizi", "cevaplar": "Q-T-001: (a)",
        "onceki_sorular": "### Q-T-001: konum?", "gorev": gorev,
        "kardes": {"key": "MBSUATEAM-105::FE", "katman": "fe", "markdown": "## FE analizi",
                   "acik_sorular": "### Q-T-001: konum?\n- Soru: a\n\n### Q-T-005: fe-özel?\n- Soru: f"}}
job = c.post("/api/jira/gorev/is/baslat", json={"adimlar": [adim]}, headers=H).get_json()["job"]
for _ in range(200):
    d = c.get(f"/api/jira/gorev/is/durum?job={job}", headers=H).get_json()
    if d.get("durum") in ("bitti", "hata", "durduruldu"):
        break
    time.sleep(0.05)
son = (d.get("sonuclar") or {}).get("MBSUATEAM-105") or {}
chk("iş bitti, ana katman işlendi", d.get("durum") == "bitti" and son.get("markdown") == "## BE analizi\n[CEVAP]", json.dumps(son)[:200])
chk("kardeş katman ikinci çağrıyla (sorular_uret=False, yalnız ORTAK cevap, kardeşin kendi listesi) işlendi",
    len(cagri) == 2 and cagri[1][0] == "## FE analizi" and cagri[1][1] is False and cagri[1][2] == "Q-T-001: (a)" and "Q-T-005" in cagri[1][3])
k = son.get("kardes") or {}
chk("sonuc.kardes: ortak Q-T-001 düştü, FE'ye özel Q-T-005 KORUNDU (ana liste kopyalanmadı)",
    k.get("key") == "MBSUATEAM-105::FE" and k.get("katman") == "fe" and k.get("markdown") == "## FE analizi\n[CEVAP]"
    and "Q-T-001" not in k.get("acik_sorular", "") and "Q-T-005" in k.get("acik_sorular", ""), json.dumps(k)[:200])
chk("iki depo da yazıldı (BE + FE::FE), FE deposunda kendi listesi",
    [x[0] for x in depo] == ["MBSUATEAM-105", "MBSUATEAM-105::FE"] and depo[1][1] == "fe" and "Q-T-005" in depo[1][4])
# ortak soru YOKSA kardeşe dokunulmaz
cagri.clear()
depo.clear()
adim_f = dict(adim, kardes={**adim["kardes"], "acik_sorular": "### Q-T-007: bambaşka?\n- Soru: z"})
job = c.post("/api/jira/gorev/is/baslat", json={"adimlar": [adim_f]}, headers=H).get_json()["job"]
for _ in range(200):
    d = c.get(f"/api/jira/gorev/is/durum?job={job}", headers=H).get_json()
    if d.get("durum") in ("bitti", "hata", "durduruldu"):
        break
    time.sleep(0.05)
sk = ((d.get("sonuclar") or {}).get("MBSUATEAM-105") or {}).get("kardes") or {}
chk("farklı sorular → kardeş işlenmez (atlandi), ikinci çağrı yok, FE deposu yazılmaz",
    len(cagri) == 1 and sk.get("atlandi") and [x[0] for x in depo] == ["MBSUATEAM-105"])
chk("ortak_cevaplari_suz: ID normalize + yalnız kardeşteki", jg.ortak_cevaplari_suz("Q-T-001: a\nQT2: b\nQ-T-3: c", "### Q-001: x\n### Q-T-003: y") == "Q-T-001: a\nQ-T-3: c"
    and jg.ortak_cevaplari_suz("Q-T-001: a", "") == "")
chk("aktif_not temizlendi", not d.get("aktif_not"))
# kardeş hata verirse ana sonuç korunur, kardes.hata döner, kardeş deposu yazılmaz
cagri.clear()
depo.clear()


def _cevap2(gorev, mevcut, cevaplar, onceki_sorular="", sorular_uret=True):
    if not sorular_uret:
        raise RuntimeError("kardeş patladı")
    return {"markdown": mevcut + "\n[CEVAP]", "acik_sorular": "", "hedefli": True}


jg.gorev_cevap_uygula = _cevap2
job = c.post("/api/jira/gorev/is/baslat", json={"adimlar": [adim]}, headers=H).get_json()["job"]
for _ in range(200):
    d = c.get(f"/api/jira/gorev/is/durum?job={job}", headers=H).get_json()
    if d.get("durum") in ("bitti", "hata", "durduruldu"):
        break
    time.sleep(0.05)
son = (d.get("sonuclar") or {}).get("MBSUATEAM-105") or {}
chk("kardeş hatası ana sonucu düşürmez; kardes.hata; FE deposu yazılmaz",
    d.get("durum") == "bitti" and "[CEVAP]" in son.get("markdown", "") and "patladı" in (son.get("kardes") or {}).get("hata", "")
    and [x[0] for x in depo] == ["MBSUATEAM-105"])
# kardeş yoksa (tek katman) davranış aynı
cagri.clear()
jg.gorev_cevap_uygula = _cevap
adim2 = {k2: v for k2, v in adim.items() if k2 != "kardes"}
job = c.post("/api/jira/gorev/is/baslat", json={"adimlar": [adim2]}, headers=H).get_json()["job"]
for _ in range(200):
    d = c.get(f"/api/jira/gorev/is/durum?job={job}", headers=H).get_json()
    if d.get("durum") in ("bitti", "hata", "durduruldu"):
        break
    time.sleep(0.05)
chk("kardeş yoksa tek çağrı, sonuçta kardes yok", len(cagri) == 1 and "kardes" not in ((d.get("sonuclar") or {}).get("MBSUATEAM-105") or {}))
# UI kaynak kontrolü
html = (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(encoding="utf-8")
chk("UI: jgCevaplariIsle kardeş gönderir + merge rs.kardes'i işler", "kardes = { key: kk" in html and "rs.kardes && rs.kardes.key" in html)

print(f"\n{'TÜM TESTLER GEÇTİ' if HATA == 0 else str(HATA) + ' HATA'}")
sys.exit(1 if HATA else 0)
