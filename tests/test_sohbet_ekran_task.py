"""İnteraktif Analiz → Task Analizi formatında ekran FE+BE analizi (owner 2026-11-06). Sohbetin 🌐 gözlem raporu oturuma
bağlanır, ekran envanteri gözlemdeki ekranları aday yapar, ekran task adımı raporu taşır, motor hazır raporla YENİDEN GÖZLEMEZ,
iş bitince sohbete katman kararı mesajı düşer. Offline / 0 token; gerçek oturum dosyasına DOKUNMAZ."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("TELEMETRI_SINK", "off")

from skills import base as B  # noqa: E402
from skills import gozlem as GZ  # noqa: E402
from skills import sohbet_analiz as SA  # noqa: E402

tmp = Path(tempfile.mkdtemp())
SA._SOHBET_DIR = tmp
SA._OTURUM_DOSYA = tmp / "oturum.json"
SA._EK_DIR = tmp / "ekler"
GZ.GOZLEM_DIR = tmp / "gozlem"
B.CONTEXT_FILTER_PATH = tmp / "context_filter.json"
B.CONTEXT_FILTER_PATH.write_text(json.dumps({"live_app": {"target_url": "https://dev-ornek.local/app"},
                                             "live_app_auth": {"username": "u", "password": "p"}}), encoding="utf-8")
hatalar = []


def chk(ad, kosul, ek=""):
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f" — {ek}" if ek and not kosul else ""))
    if not kosul:
        hatalar.append(ad)


RAPOR_MD = "## Ekran ve Navigasyon\n- Sports `/basic-data/sports` `[K: Canlı UI:/basic-data/sports]`\n- Groups `/basic-data/groups`\n"
yak = {}


def sahte_ai(cevap):
    def f(sistem, mesajlar, **kw):
        yak["metin"] = "\n".join(p.get("text", "") for m in mesajlar for p in (m.get("content") or []) if isinstance(p, dict))
        yak["kw"] = kw
        return cevap
    return f


print("1) 🌐 turu: başarılı rapor oturuma + agent mesajına bağlanır")
SA._api_cagri = sahte_ai("gördüm")
SA.referans_dosyalari_hazirla = lambda: []
SA.live_app_urls = lambda: ["https://dev-ornek.local/app"]
SA.canli_uygulama_baglami_hazirla = lambda **kw: "### CANLI GÖREV " + kw.get("hedef_tarif", "")
GZ.rapor_al = lambda *a, **k: {"ok": True, "md": RAPOR_MD, "anahtar": "abc123", "ts": time.time()}
SA.oturum_sifirla()
o = SA.sohbet_mesaj("sport basic data altını tara", gozlem=True)
chk("oturum.gozlemler[] anahtar + agent mesajı gozlem_anahtar", (o.get("gozlemler") or [{}])[-1].get("anahtar") == "abc123"
    and o["mesajlar"][-1].get("gozlem_anahtar") == "abc123")
GZ.rapor_al = lambda *a, **k: {"ok": False, "md": "", "neden": "x"}
o = SA.sohbet_mesaj("tekrar", gozlem=True)
chk("başarısız gözlem oturuma yazılmaz, mesajda anahtar yok", len(o.get("gozlemler")) == 1 and "gozlem_anahtar" not in o["mesajlar"][-1])

print("2) son_gozlem_raporu: taze + ok rapor; eski/ok=False → None")
GZ.rapor_oku = lambda a: {"ok": True, "md": RAPOR_MD, "anahtar": a, "yas_sn": 10} if a == "abc123" else None
chk("taze rapor bulunur", (SA.son_gozlem_raporu() or {}).get("anahtar") == "abc123")
GZ.rapor_oku = lambda a: {"ok": True, "md": RAPOR_MD, "anahtar": a, "yas_sn": 10 ** 9}
chk("eski rapor → None", SA.son_gozlem_raporu() is None)
GZ.rapor_oku = lambda a: {"ok": True, "md": RAPOR_MD, "anahtar": a, "yas_sn": 10}

print("3) ekran envanteri gözlem raporunu görür; ekran görevleri raporu taşır")
SA._api_cagri = sahte_ai('<ekranlar>[{"ad":"Sports","menu":"Sport Basic Data › Sports","ister":"6 ondalık"}]</ekranlar>')
ek = SA.ekran_listesi_cikar()
chk("envanter promptunda CANLI GÖZLEM RAPORU bloğu", "CANLI GÖZLEM RAPORU" in yak["metin"] and "/basic-data/sports" in yak["metin"])
ad = SA.ekran_gorevleri([0])
chk("adım: gozlem_anahtar + sohbet_kaynak + fe-be-ayir", ad[0]["gozlem_anahtar"] == "abc123" and ad[0]["sohbet_kaynak"] is True
    and ad[0]["mode"] == "fe-be-ayir")
GZ.rapor_oku = lambda a: None
chk("rapor yoksa anahtar boş (motor kendisi gözler)", SA.ekran_gorevleri([0])[0]["gozlem_anahtar"] == "")

print("4) motor: hazır gozlem_rapor verilince rapor_al ÇAĞRILMAZ, rapor bloğu analize girer")
from skills import jira_gorevleri as JG  # noqa: E402
import skills.ornek_havuzu as OH  # noqa: E402
JG.referans_dosyalari_hazirla = lambda *a, **k: []
JG.load_context_filter = lambda *a, **k: {}
JG._gorev_acik_sorular_uret = lambda *a, **k: ""
OH.ornek_bloklari = lambda *a, **k: []
JG.canli_uygulama_baglami_hazirla = lambda *a, **k: ""
cag = []
JG._api_cagri = lambda s, m, **k: (cag.append("\n".join(p.get("text", "") for p in m[0]["content"] if isinstance(p, dict)))
                                    or "<teknik_analiz>**Bu katmanda iş:** VAR\n## 1. Amaç\nx\n</teknik_analiz>")
GZ.rapor_al = lambda *a, **k: (_ for _ in ()).throw(AssertionError("yeniden gözlem olmamalı"))
G = {"key": "EKRAN-1", "summary": "Sport Basic Data › Sports", "description": "6 ondalık", "issuetype": "Görev"}
r = JG.gorev_fe_be_analiz(G, canli_baglam_override="### CANLI GÖREV x", gozlem_rapor={"ok": True, "md": RAPOR_MD, "ts": time.time()})
chk("rapor_al çağrılmadı, BE+FE analizlerinde rapor bloğu, is_var parse", len(cag) >= 2
    and all("CANLI UYGULAMA GÖZLEM RAPORU" in c for c in cag[:2]) and r["be"]["is_var"] is True)
cag.clear()
gz = []
GZ.rapor_al = lambda *a, **k: (gz.append(1) or {"ok": True, "md": RAPOR_MD, "ts": time.time()})
JG.gorev_fe_be_analiz(G, canli_baglam_override="### CANLI GÖREV x", gozlem_rapor={"ok": False, "md": ""})
chk("ok=False hazır rapor → eski yol (rapor_al çağrılır)", gz == [1])

print("5) sohbete katman kararı mesajı")
SA.ekran_sonucu_bildir("EKRAN-1", "Sport Basic Data › Sports", True, False)
m = SA.oturum_oku()["mesajlar"][-1]
chk("sistem mesajı: BE iş VAR · FE iş YOK + task_analizi bayrağı", m.get("sistem") and m.get("task_analizi") and "BE iş VAR" in m["metin"] and "FE iş YOK" in m["metin"])
SA.ekran_sonucu_bildir("EKRAN-1", "Sports", None, None, hata="zaman aşımı")
chk("hata mesajı", "üretilemedi" in SA.oturum_oku()["mesajlar"][-1]["metin"])

print("6) app: iş başlatma gozlem_anahtar/sohbet_kaynak taşır")
sys.argv = ["test_sohbet_ekran_task"]
import app as A  # noqa: E402
from skills import telemetri as T  # noqa: E402
T.USAGE_DIR = tmp / "usage"
T.EVENTS_DOSYA = T.USAGE_DIR / "events.jsonl"
T._sink_gonder = lambda k: None
A._kimlik_tam_mi = lambda *a, **k: True
A._jira_baglanti_eksik = lambda: "Jira bağlı değil"
A._gorev_is_calistir = lambda job_id: None
c = A.app.test_client()
rj = c.post("/api/jira/gorev/is/baslat", json={"adimlar": ad}, headers={"Origin": "http://localhost"}).get_json()
a0 = A._gorev_isler[rj["job"]]["adimlar"][0]
chk("adım beyaz listesi: gozlem_anahtar + sohbet_kaynak", a0.get("gozlem_anahtar") == "abc123" and a0.get("sohbet_kaynak") is True, a0)
chk("gözlem turu talimatı Task Analizi şablonunu ister", "TASK ANALİZİ ŞABLONU" in SA._GOZLEM_TURU_TALIMAT and "## 11. Kabul Kriterleri" in SA._GOZLEM_TURU_TALIMAT)

print(f"\n{'SOHBET EKRAN TASK TESTLERİ GEÇTİ' if not hatalar else 'HATA: ' + ', '.join(hatalar)}")
sys.exit(1 if hatalar else 0)
