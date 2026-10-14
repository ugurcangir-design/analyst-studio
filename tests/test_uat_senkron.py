"""UAT Durum Senkronu — offline, 0 token, Jira MOCK.

Kapsam:
  1. plan_hesapla: yalnız Backlog/Yapılacaklar UAT · doğrudan link · Devam Ediyor ve sonrası tetikler ·
     Story/Epic linki, iptal, başka proje, Backlog'daki hedef tetiklemez · Hold/Tamam UAT'a dokunulmaz
  2. tasi: geçiş 'to' adından bulunur · geçiş yoksa net hata · yorum eklenir
  3. tur: RAPOR modunda Jira'ya YAZMAZ · OTOMATİK modda taşır + geçmişe yazar
  4. ayar_kaydet doğrulama + uçlar (durum/ayar/calistir doğrulamaları)
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("BILDIRIM", "false")

from skills import uat_durum_senkron as US  # noqa: E402

_hata = 0


def chk(ad, kosul, ek=""):
    global _hata
    if not kosul:
        _hata += 1
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if ek and not kosul else ""))


_tmp = Path(tempfile.mkdtemp())
US.AYAR_DOSYA = _tmp / "uat_senkron.json"
US.DURUM_DOSYA = _tmp / "durum.json"


def lk(key, durum, tip="Görev"):
    return {"key": key, "durum": durum, "type": tip, "summary": f"{key} özet", "iliski": "relates to"}


def u(key, status, links, tip="Görev"):
    return {"key": key, "summary": f"{key} özet", "status": status, "type": tip, "baglantililar": links}


UAT = [
    u("UAT-1", "Backlog", [lk("MBSTRADE-1", "Devam Ediyor")]),                 # taşınır
    u("UAT-2", "Yapılacaklar", [lk("MBSOPS-2", "READY FOR TEST")]),            # sonrası da tetikler
    u("UAT-3", "Backlog", [lk("MBSTRADE-3", "Backlog")]),                      # hedef henüz başlamamış
    u("UAT-4", "Backlog", [lk("MBSTRADE-4", "Devam Ediyor", tip="Hikaye")]),   # Story linki sayılmaz
    u("UAT-5", "Backlog", [lk("MBSTRADE-5", "İptal Edildi")]),                 # iptal tetiklemez
    u("UAT-6", "Backlog", [lk("OTHER-6", "Devam Ediyor")]),                    # başka proje
    u("UAT-7", "Hold", [lk("MBSTRADE-7", "Devam Ediyor")]),                    # Hold'a dokunulmaz
    u("UAT-8", "Tamam", [lk("MBSTRADE-8", "Tamam")]),                          # kapanmış
    u("UAT-9", "Backlog", [lk("MBSTRADE-9", "Backlog"), lk("MBSTRADE-10", "Tamam")]),  # biri yeter
    u("UAT-10", "Backlog", [lk("MBSTRADE-11", "Devam Ediyor")], tip="Hikaye"),  # UAT Story'si → kalem değil
]

print("1) plan_hesapla")
plan = US.plan_hesapla(UAT, US.ayarlar())
keys = [p["uat_key"] for p in plan]
chk("yalnız doğru UAT'lar", keys == ["UAT-1", "UAT-2", "UAT-9"], keys)
chk("tetikleyen yalnız geliştirmeye alınmış task", [t["key"] for t in plan[2]["tetikleyenler"]] == ["MBSTRADE-10"],
    plan[2]["tetikleyenler"])
chk("varsayılan KAPALI + rapor modu", US.ayarlar()["aktif"] is False and US.ayarlar()["mod"] == "rapor")

print("2) tasi")
yazilan, yorumlar = [], []
GECISLER = {"transitions": [{"id": "11", "name": "Başla", "to": {"name": "Devam Ediyor"}},
                            {"id": "21", "name": "Beklet", "to": {"name": "Hold"}}]}
US.atlassian_get = lambda path, cid: GECISLER
US.atlassian_post = lambda path, body, cid: yazilan.append((path, body)) or {}
import skills.jira_kopru as JK  # noqa: E402
JK.jira_yorum_ekle = lambda key, md: yorumlar.append((key, md)) or True
r = US.tasi(plan[0], "Devam Ediyor", "cid")
chk("geçiş 'to' adından bulundu ve gönderildi", r["ok"] and yazilan == [("/rest/api/3/issue/UAT-1/transitions",
                                                                         {"transition": {"id": "11"}})], yazilan)
chk("yorum: tetikleyen task + durum geçişi", yorumlar and "MBSTRADE-1 (Devam Ediyor)" in yorumlar[0][1]
    and "'Backlog' → 'Devam Ediyor'" in yorumlar[0][1], yorumlar)
GECISLER = {"transitions": [{"id": "21", "name": "Beklet", "to": {"name": "Hold"}}]}
r = US.tasi(plan[0], "Devam Ediyor", "cid")
chk("geçiş yoksa net hata (yazma yok)", not r["ok"] and "bulunamadı" in r["hata"] and "Hold" in r["hata"], r)

print("3) tur — rapor vs otomatik")
GECISLER = {"transitions": [{"id": "11", "name": "Başla", "to": {"name": "Devam Ediyor"}}]}
US._cloud_id = lambda: "cid"
US._uat_gorevlerini_cek = lambda ayar, cid: [dict(x) for x in UAT]
yazilan.clear()
yorumlar.clear()
d = US.tur()   # ayar: rapor modu
chk("RAPOR: Jira'ya HİÇ yazılmadı", yazilan == [] and yorumlar == [], yazilan)
chk("RAPOR: plan kaydedildi", d["son_mod"] == "rapor" and len(d["plan"]) == 3 and d["tasinan"] == 0)
US.ayar_kaydet({"aktif": True, "mod": "otomatik"})
d = US.tur()
chk("OTOMATİK: 3 UAT taşındı + 3 yorum", d["tasinan"] == 3 and len(yazilan) == 3 and len(yorumlar) == 3, d["tasinan"])
chk("geçmişe yazıldı", [g["uat_key"] for g in US.durum_oku()["gecmis"]] == ["UAT-1", "UAT-2", "UAT-9"])
chk("sıra: yeni tur sonrası aralık dolmadı", US.sira_geldi_mi() is False)
US.hata_kaydet("ağ yok")
chk("hata tur zamanını değiştirmez (kısa aralıkla tekrar)", US.durum_oku()["son_tur_ts"] == d["son_tur_ts"]
    and US.durum_oku()["son_hata"] == "ağ yok")

print("4) ayar + uçlar")
try:
    US.ayar_kaydet({"mod": "hepsini-sil"})
    chk("geçersiz mod reddedilir", False)
except ValueError:
    chk("geçersiz mod reddedilir", True)
chk("aralık alt sınırı (10 dk)", US.ayar_kaydet({"aralik_sn": 5})["aralik_sn"] == 600)
import app as A  # noqa: E402
c = A.app.test_client()
H = {"Origin": "http://localhost"}
A._kimlik_tam_mi = lambda *a, **k: True
r = c.get("/api/uat-senkron/durum").get_json()
chk("GET durum: ayar + plan + geçmiş", r.get("ok") and r["ayar"]["mod"] == "otomatik" and len(r["gecmis"]) == 3, r.get("ayar"))
chk("POST ayar boş → 400", c.post("/api/uat-senkron/ayar", json={}, headers=H).status_code == 400)
chk("POST ayar geçersiz mod → 400", c.post("/api/uat-senkron/ayar", json={"mod": "x"}, headers=H).status_code == 400)
chk("POST calistir geçersiz uygula → 400", c.post("/api/uat-senkron/calistir", json={"uygula": "evet"}, headers=H).status_code == 400)
chk("ayar dosyası yerel (gitignore)", "reference/uat_senkron.json" in Path(".gitignore").read_text(encoding="utf-8"))
json.loads(US.AYAR_DOSYA.read_text(encoding="utf-8"))

print()
if _hata:
    print(f"UAT SENKRON TESTLERİ BAŞARISIZ ({_hata} hata)")
    sys.exit(1)
print("UAT SENKRON TESTLERİ GEÇTİ")
