"""Jira hiyerarşi oluşturma — KISMİ HATA dayanıklılığı (offline, 0 token, Jira MOCK).

Bir Story/Subtask Jira'da reddedilse bile döngü patlamaz; kalanlar açılır, açılanlar +
hatalar raporlanır (öksüz Epic/Story + belirsiz 500 yerine).

Çalıştır:  venv/bin/python tests/test_jira_hiyerarsi.py
"""

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

import skills.jira_tasks as jt  # noqa: E402

basari = 0


def kontrol(ad, kosul):
    global basari
    if not kosul:
        raise SystemExit(f"FAIL {ad}")
    basari += 1
    print(f"  ✓ {ad}")


# Jira'yı ve ADF'i mock'la (ağ yok)
jt.env_oku = lambda: {"JIRA_CLOUD_ID": "c", "JIRA_PROJECT_KEY": "MBS"}
jt._proje_bilgi = lambda pk, cid: {"fake": True}
jt._issue_type_idleri = lambda proje, pk: ("epicid", "storyid", None)
jt._gorev_govde_adf = lambda desc, ac: {"adf": True}
jt._epik_adf = getattr(jt, "_epik_adf", None)

_created = []


def _fake_issue(summary, description_adf, issue_type_id, project_key, cloud_id, parent_key=None):
    if "PATLA" in summary:
        raise RuntimeError("Jira reddetti (ör. parent geçersiz)")
    key = f"MBS-{len(_created) + 1}"
    _created.append((key, summary, parent_key))
    return key


jt._issue_olustur = _fake_issue

hierarchy = {
    "epic_dahil": True, "epic_summary": "Epic X", "epic_description": "d",
    "stories": [
        {"summary": "Story A", "subtasks": [{"summary": "Sub A1"}, {"summary": "Sub PATLA"}]},
        {"summary": "Story PATLA", "subtasks": []},
        {"summary": "Story B", "subtasks": []},
    ],
}
r = jt.jira_hiyerarsi_olustur(hierarchy)

kontrol("kısmi hata bayrağı True", r["kismi"] is True)
kontrol("2 hata raporlandı (Sub PATLA + Story PATLA)", len(r["hatalar"]) == 2)
kontrol("olusturulan=4 (Epic + Story A + Sub A1 + Story B)", r["olusturulan"] == 4)
kontrol("Story PATLA açılamadı → stories listesinde yok",
        all("PATLA" not in s["summary"] for s in r["stories"]))
kontrol("Story PATLA'dan SONRA Story B yine açıldı (döngü patlamadı)",
        any(s["summary"] == "Story B" for s in r["stories"]))
kontrol("Story A'nın yalnız başarılı subtask'ı kaldı (Sub A1)",
        any(s["summary"] == "Story A" and len(s["subtasks"]) == 1 for s in r["stories"]))
kontrol("toplam plan sayısı korunur (6)", r["toplam"] == 6)

# ── Bozuk AI yanıtı 7 gün önbellekte kalmasın: parse hatasında BİR KEZ önbelleksiz tekrar ──
cagrilar: list = []
yanitlar = ["<jira_hierarchy>{bozuk json</jira_hierarchy>", '<jira_hierarchy>{"epic": {"summary": "E"}, "stories": []}</jira_hierarchy>']
jt._api_cagri = lambda s, m, **k: cagrilar.append(k.get("onbellek", True)) or yanitlar.pop(0)
jt.prompt_yukle = lambda sid: "P"
h = jt._hierarchy_uret("analiz")
kontrol("_hierarchy_uret: ilk yanıt bozuk → ikinci çağrı onbellek=False, sonuç ikinci yanıttan", cagrilar == [True, False] and h["epic"]["summary"] == "E")
cagrilar.clear()
yanitlar[:] = ["bozuk", "yine bozuk"]
try:
    jt._hierarchy_uret("analiz")
    kontrol("iki kez bozuk → ValueError", False)
except ValueError:
    kontrol("_hierarchy_uret: iki kez bozuk → ValueError (en fazla 1 tekrar)", cagrilar == [True, False])
import skills.jira_fe_be as jf  # noqa: E402
cagrilar.clear()
yanitlar[:] = ["<fe_be_gorevler>bozuk</fe_be_gorevler>", '<fe_be_gorevler>{"gorevler": [{"id": "BE-1", "katman": "BE", "summary": "s", "description": "d"}]}</fe_be_gorevler>']
jf._api_cagri = lambda s, m, **k: cagrilar.append(k.get("onbellek", True)) or yanitlar.pop(0)
g = jf._gorevler_uret("analiz")
kontrol("jira_fe_be._gorevler_uret: parse hatasında önbelleksiz tekrar, sonuç normalize", cagrilar == [True, False] and len(g) == 1 and g[0]["katman"] == "BE")

print(f"\nJIRA HİYERARŞİ TESTLERİ GEÇTİ ({basari} kontrol)")
