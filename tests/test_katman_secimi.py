"""Katman seçimli Jira yazımı — FE+BE setinden yalnız FE / yalnız BE / ikisi (offline, Jira MOCK, 0 token).

Kapsam:
  1. gorev_fe_be_task_olustur(katmanlar): ['fe'] → yalnız yeni FE task + kaynak task'a Relates, BE yazılmaz;
     ['be'] → yalnız orijinal güncellenir, task açılmaz; ['be','fe'] → eski davranış (BE yaz + FE aç + Blocks);
     boş/eksik katman → ValueError
  2. gorev_yeni_task_olustur(mode='be'|'fe') → tek önekli task + kaynak/üst Relates; 'fe-be' iki task
  3. katman_is_var_mi: VAR/YOK/yok; gorev_fe_be_analiz sonucu is_var taşır
  4. app: fe-be-olustur katmanlar doğrulaması (eksik md → 400), yeni-task mode doğrulaması; UI kaynak kontrolleri
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("BILDIRIM", "false")

from skills import jira_gorevleri as JG  # noqa: E402
JG.canli_uygulama_baglami_hazirla = lambda *a, **k: ""   # gözlem fazı gerçek CLI açmasın (0 token)
import skills.jira_tasks as JT  # noqa: E402
import skills.jira_fe_be as JF  # noqa: E402
import skills.jira_kopru as JK  # noqa: E402

_hata = 0


def chk(ad, kosul, ek=""):
    global _hata
    if not kosul:
        _hata += 1
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if ek and not kosul else ""))


olay: list = []
JG._cloud_id = lambda: "cid"
JG.gorev_getir = lambda key: {"key": key, "summary": "Match Status filtresi"}
JG.gorev_jiraya_yaz = lambda key, md, summary=None: olay.append(("guncelle", key, summary)) or True
JT._proje_bilgi = lambda proje, cid: {"task_id": "10001"}
_sayac = {"n": 0}


def _issue_olustur(summary, adf, task_id, proje, cid):
    _sayac["n"] += 1
    k = f"{proje}-9{_sayac['n']}"
    olay.append(("ac", k, summary))
    return k


JT._issue_olustur = _issue_olustur
JF._blocks_link_tipi = lambda cid: "Blocks"
JF._blocks_bagla = lambda a, b, tip, cid: olay.append(("blocks", a, b))
JK.jira_issue_link = lambda a, b, tip="Relates": olay.append(("relates", a, b))

print("1) gorev_fe_be_task_olustur — katmanlar")
olay.clear()
r = JG.gorev_fe_be_task_olustur("MBS-365", "## BE\nx", "## FE\ny", summary="Filtre", katmanlar=["fe"])
chk("yalnız FE: yeni FE task açıldı, BE yazılmadı, kaynak task'a Relates", r["fe_key"] == "MBS-91" and r["be_key"] is None
    and ("ac", "MBS-91", "FE - Filtre") in olay and not any(o[0] == "guncelle" for o in olay)
    and ("relates", "MBS-91", "MBS-365") in olay and r["link"] and r["katmanlar"] == ["fe"], olay)
olay.clear()
r = JG.gorev_fe_be_task_olustur("MBS-365", "## BE\nx", "", summary="Filtre", katmanlar=["be"])
chk("yalnız BE: orijinal 'BE - ' ile güncellendi, task açılmadı, bağ yok", r["be_key"] == "MBS-365" and r["fe_key"] is None
    and ("guncelle", "MBS-365", "BE - Filtre") in olay and not any(o[0] in ("ac", "blocks", "relates") for o in olay), olay)
olay.clear()
r = JG.gorev_fe_be_task_olustur("MBS-365", "## BE\nx", "## FE\ny", summary="Filtre")
chk("ikisi (varsayılan): BE yaz + FE aç + BE→FE Blocks", r["be_key"] == "MBS-365" and r["fe_key"] == "MBS-92"
    and ("blocks", "MBS-365", "MBS-92") in olay and r["link"], olay)
for kat, be, fe in (([], "x", "y"), (["fe"], "x", ""), (["be"], "", "y")):
    try:
        JG.gorev_fe_be_task_olustur("MBS-365", be, fe, katmanlar=kat)
        chk(f"doğrulama {kat}", False)
    except ValueError:
        chk(f"doğrulama: katman={kat} eksik içerik → ValueError", True)

print("2) gorev_yeni_task_olustur — mode be|fe")
olay.clear()
r = JG.gorev_yeni_task_olustur("MBS", mode="fe", markdown="## FE\ny", baslik="Filtre", ust_key="MBS-1", kaynak_key="MBS-365")
chk("mode=fe: tek 'FE - ' task + üst + kaynak Relates", len(r["tasklar"]) == 1 and r["tasklar"][0]["katman"] == "FE"
    and r["tasklar"][0]["summary"] == "FE - Filtre" and ("relates", r["tasklar"][0]["key"], "MBS-1") in olay
    and ("relates", r["tasklar"][0]["key"], "MBS-365") in olay and r["febe_link"] is None, (r, olay))
olay.clear()
r = JG.gorev_yeni_task_olustur("MBS", mode="be", markdown="## BE\nx", baslik="Filtre")
chk("mode=be: tek 'BE - ' task", r["tasklar"][0]["summary"] == "BE - Filtre" and not any(o[0] == "blocks" for o in olay))
try:
    JG.gorev_yeni_task_olustur("MBS", mode="fe", markdown="", baslik="x")
    chk("mode=fe boş md → ValueError", False)
except ValueError:
    chk("mode=fe boş md → ValueError", True)
olay.clear()
r = JG.gorev_yeni_task_olustur("MBS", mode="fe-be", be_markdown="b", fe_markdown="f", baslik="Filtre")
chk("mode=fe-be: iki task + Blocks (değişmedi)", len(r["tasklar"]) == 2 and r["febe_link"] is True)

print("3) 'Bu katmanda iş' satırı")
chk("VAR / YOK / yok", JG.katman_is_var_mi("## 📋 Yönetici Özeti\n…\n\n**Bu katmanda iş:** VAR — filtre") is True
    and JG.katman_is_var_mi("**Bu katmanda iş:** YOK — BE'de değişiklik gerekmez") is False and JG.katman_is_var_mi("## 1. Amaç") is None)
JG.gorev_analiz_et = lambda gorev, **kw: {"markdown": ("**Bu katmanda iş:** YOK — x" if kw.get("katman") == "be" else "**Bu katmanda iş:** VAR — y"), "acik_sorular": ""}
r = JG.gorev_fe_be_analiz({"key": "MBS-365", "summary": "s", "description": "d"})
chk("fe_be sonucu is_var taşır (BE False, FE True)", r["be"]["is_var"] is False and r["fe"]["is_var"] is True)
src = Path(JG.__file__).read_text(encoding="utf-8")
chk("katman promptu 'Bu katmanda iş' satırını ister", "ANALİZİN EN BAŞINA TEK SATIR yaz: `**Bu katmanda iş:** VAR" in src)

print("4) app + UI")
import app as A  # noqa: E402
A._kimlik_tam_mi = lambda *a, **k: True
c = A.app.test_client()
H = {"Origin": "http://localhost"}
chk("fe-be-olustur: katmanlar=['fe'] + fe boş → 400 (BE dolu olsa da)",
    c.post("/api/jira/gorev/fe-be-olustur", json={"key": "MBS-1", "be_markdown": "x", "fe_markdown": "", "katmanlar": ["fe"]}, headers=H).status_code == 400)
chk("fe-be-olustur: katmanlar=['be'] + be dolu, fe boş → doğrulamayı geçer (Jira kontrolüne düşer, 400 'BE analizi boş' DEĞİL)",
    "BE analizi boş" not in (c.post("/api/jira/gorev/fe-be-olustur", json={"key": "MBS-1", "be_markdown": "x", "fe_markdown": "", "katmanlar": ["be"]}, headers=H).get_json() or {}).get("error", ""))
chk("fe-be-olustur: katmanlar boş → 400", c.post("/api/jira/gorev/fe-be-olustur", json={"key": "MBS-1", "be_markdown": "x", "fe_markdown": "y", "katmanlar": ["x"]}, headers=H).status_code == 400)
chk("yeni-task: mode=fe md boş → 400 'FE içeriği boş'", "FE içeriği boş" in (c.post("/api/jira/gorev/yeni-task", json={"proje": "MBS", "mode": "fe", "markdown": ""}, headers=H).get_json() or {}).get("error", ""))
chk("yeni-task: geçersiz mode → 400", c.post("/api/jira/gorev/yeni-task", json={"proje": "MBS", "mode": "zzz", "markdown": "x"}, headers=H).status_code == 400)
ui = Path(A.__file__).parent.joinpath("templates/index.html").read_text(encoding="utf-8")
chk("UI: katman kutuları + etiket + yeni task katman seçimi + katmanlar gövdeye", all(x in ui for x in (
    'id="jg-kat-be"', 'id="jg-kat-fe"', "_jgKatmanEtiketGuncelle", 'name="jg-yt-katman"', "summary: be.summary || '', katmanlar })", "mode: ytMode")))

print()
if _hata:
    print(f"KATMAN SEÇİMİ TESTLERİ BAŞARISIZ ({_hata} hata)")
    sys.exit(1)
print("KATMAN SEÇİMİ TESTLERİ GEÇTİ")
