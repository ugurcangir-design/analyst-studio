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
_ORJ_YAZ = JG.gorev_jiraya_yaz   # bölüm 5 gerçek fonksiyonu test eder
JG.gorev_jiraya_yaz = lambda key, md, summary=None, orijinal_koru=True: olay.append(("guncelle", key, summary)) or True
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

print("5) BE'yi yaz → TEMİZ analiz (owner 2026-10-21: wrapper YOK); köprü yolu orijinali korur")
yazilan: dict = {}
JG.gorev_jiraya_yaz = lambda key, md, summary=None, orijinal_koru=True: yazilan.__setitem__(key, (md, orijinal_koru)) or True
JG.gorev_getir = lambda key: {"key": key, "summary": "Match Status filtresi", "description": "Müşteri isterisi: filtre eklensin."}
JG.gorev_fe_be_task_olustur("MBS-365", "## 1. Amaç\nBE analizi `[K: Swagger]`", "", katmanlar=["be"])
chk("BE yazımı TEMİZ: '📌 Orijinal Talep'/'🤖 Teknik Analiz' wrapper YOK, orijinal_koru=False",
    yazilan["MBS-365"][0].startswith("## 1. Amaç") and "📌 Orijinal Talep" not in yazilan["MBS-365"][0]
    and "🤖 Teknik Analiz" not in yazilan["MBS-365"][0] and yazilan["MBS-365"][1] is False, yazilan["MBS-365"])
_gercek_yaz = _ORJ_YAZ
put: dict = {}
JG.atlassian_put = lambda path, body, cloud_id: put.update({"path": path, "body": body}) or {}
JG.markdown_to_adf = lambda md: [{"type": "paragraph", "md": md}]
# Güncelle endpoint artık orijinal_koru=False (temiz); AMA köprü orijinal_koru=True ile orijinali KORUR
_gercek_yaz("MBS-365", "## 1. Amaç\nyeni analiz", summary="BE - x", orijinal_koru=True)
md_put = put["body"]["fields"]["description"]["content"][0]["md"]
chk("köprü yolu (orijinal_koru=True): işaret yoksa mevcut açıklamayı okuyup orijinali korur", "Orijinal Talep" in md_put
    and "Müşteri isterisi" in md_put and "yeni analiz" in md_put and put["body"]["fields"]["summary"] == "BE - x", md_put[:160])
# Güncelle endpoint yolu (orijinal_koru=False): wrapper EKLENMEZ, temiz analiz yazılır
put.clear()
_gercek_yaz("MBS-365", "## 1. Amaç\nyeni analiz", summary="BE - x", orijinal_koru=False)
md_put2 = put["body"]["fields"]["description"]["content"][0]["md"]
chk("Güncelle yolu (orijinal_koru=False): wrapper YOK, isteri EKLENMEZ", "Orijinal Talep" not in md_put2
    and "Müşteri isterisi" not in md_put2 and "yeni analiz" in md_put2, md_put2[:160])
okuma: list = []
JG.gorev_getir = lambda key: okuma.append(key) or {"key": key, "description": "x"}
_gercek_yaz("MBS-365", "## 📌 Orijinal Talep\n\nisteri\n\n---\n\n## 🤖 Teknik Analiz (Analyst Agent)\n\nanaliz")
chk("işaret zaten varsa (köprü/BE'yi yaz birleştirdi) yeniden okuma yok, olduğu gibi yazılır", okuma == [] and "isteri" in put["body"]["fields"]["description"]["content"][0]["md"])
JG.gorev_getir = lambda key: None
try:
    _gercek_yaz("MBS-365", "## 1. Amaç\nx")
    chk("okunamazsa yazılmaz", False)
except RuntimeError as e:
    chk("mevcut açıklama okunamazsa yazma YAPILMAZ (orijinal korunamaz → net hata)", "korunamayacağı" in str(e))
JG.gorev_getir = lambda key: {"key": key, "summary": "Match Status filtresi"}
chk("gorev_jiraya_yaz kaynak: eski geniş 'except ValueError' kalktı", "except ValueError" not in __import__("inspect").getsource(_gercek_yaz))

print("6) sentetik anahtar + hata deseni + bölüm desenleri + few-shot öz-kirlenme")
olay.clear()
r = JG.gorev_yeni_task_olustur("MBS", mode="tek", markdown="## x", baslik="Ekran", kaynak_key="EKRAN-3")
chk("gorev_yeni_task_olustur: 'EKRAN-n' sentetik kaynak açıkça yok sayılır (Relates kurulmaz)", not any(o[0] == "relates" and o[2] == "EKRAN-3" for o in olay))
chk("_hata_gorev_mi: özellik işi ('Hata mesajlarının gösterilmesi', 'Çalışma saatleri', 'Eksik alanların eklenmesi') BUG DEĞİL",
    not any(JG._hata_gorev_mi({"summary": s}) for s in ("Hata mesajlarının gösterilmesi", "Çalışma saatleri ekranı", "Eksik alanların eklenmesi")))
chk("_hata_gorev_mi: başlıkta bariz hata ifadesi ('çalışmıyor', 'hata alıyor', 'açılmıyor', 'fix:', 'Hata: … silinemiyor') → kısa mod",
    all(JG._hata_gorev_mi(g) for g in ({"summary": "Filtre çalışmıyor"}, {"summary": "Kaydet'te hata alıyor"}, {"summary": "Rapor açılmıyor"},
                                       {"summary": "fix: login"}, {"summary": "Hata: kayıt silinemiyor"})))
# owner 2026-10-26 (MBSUATEAM-362): issuetype TEK BAŞINA kısa moda düşürmez — UAT board'unda geliştirme işleri de
# 'Hata' tipiyle açılıyor; başlık nötrse standart şablon kullanılmalı (ilgili başlıklar dolu, gereksizler atlanmış).
chk("_hata_gorev_mi: 'Hata'/'Bug' tipli ama başlık nötr geliştirme → kısa mod DEĞİL (standart şablon)",
    not any(JG._hata_gorev_mi(g) for g in ({"summary": 'Event Mapping Data> Events "ID kontrolü"', "issuetype": "Hata"},
                                           {"summary": "Export eklensin", "issuetype": "Bug"})))
ys = JG._yapisal_skor({"summary": "x", "description": "Bu değişiklik için amaç: hız. acceptance test sonra.\n" + "y" * 150})
chk("_yapisal_skor: gövde içi 'değişiklik'/'amaç:'/'acceptance' başlık sayılmaz (çapalı)", not ys["bolumler"]["degisiklik"] and not ys["bolumler"]["amac"]
    and not ys["bolumler"]["kabul"], ys)
ys2 = JG._yapisal_skor({"summary": "x", "description": "## Amaç\nhız\n**Değişiklik**\nx\n### Kabul Kriterleri\n- a\n" + "y" * 150})
chk("_yapisal_skor: başlık/bold başlık olarak geçince yakalanır", ys2["bolumler"]["amac"] and ys2["bolumler"]["degisiklik"] and ys2["bolumler"]["kabul"] and ys2["hazir_yapisal"])
chk("_ornek_kendisi_mi: '· MBS-365' / '· MBS-365::FE' etiketli örnek bu task'ın kendisi; başka key değil",
    JG._ornek_kendisi_mi({"text": "### ONAYLI ÖRNEK · proje: MBS · MBS-365\n\nicerik"}, "MBS-365")
    and JG._ornek_kendisi_mi({"text": "### ONAYLI ÖRNEK · MBS-365::FE\nx"}, "mbs-365")
    and not JG._ornek_kendisi_mi({"text": "### ONAYLI ÖRNEK · MBS-3650\nx"}, "MBS-365"))

print("6) '**Bu katmanda iş:**' göstergesi analiz çıktısından çıkar (is_var ayrı taşınır)")
_m = "## 📋 Yönetici Özeti\n- x\n\n---\n**Bu katmanda iş:** VAR — Market ID input.\n\n## 1. Amaç\nİş."
chk("is_var çıkarmadan ÖNCE parse edilir (VAR)", JG.katman_is_var_mi(_m) is True)
_ck = JG.katman_satiri_cikar(_m)
chk("katman_satiri_cikar: gösterge + önündeki '---' çıkar, iş + özet kalır",
    "Bu katmanda iş" not in _ck and "## 1. Amaç" in _ck and "Yönetici Özeti" in _ck, _ck)
chk("YOK göstergesi de çıkar", "Bu katmanda iş" not in JG.katman_satiri_cikar("**Bu katmanda iş:** YOK — gerekçe\n\n## 1. Amaç\nx"))

print()
if _hata:
    print(f"KATMAN SEÇİMİ TESTLERİ BAŞARISIZ ({_hata} hata)")
    sys.exit(1)
print("KATMAN SEÇİMİ TESTLERİ GEÇTİ")
