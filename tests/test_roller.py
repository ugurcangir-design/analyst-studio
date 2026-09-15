"""Rol→ekran yetkisi (roller.json, hash'li, telemetri-güdümlü) — offline, 0 token.

Doğrular: e-posta hash (normalize+salt, PII'siz), rol→ekran etkin görünürlük (rütbe),
eski gorunurluk.json fallback, telemetri isim çekme, CRUD uçları owner-gate, tracked
dosyada ham e-posta BULUNMAZ.

Çalıştır:  venv/bin/python tests/test_roller.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("AUTO_UPDATE", "false")
os.environ.setdefault("JIRA_KOPRU", "false")
os.environ.setdefault("SIRKET_EPOSTA_DOMAIN", "example.com")

import app  # noqa: E402
from skills import telemetri  # noqa: E402

basari = 0


def kontrol(ad, kosul, detay=""):
    global basari
    if not kosul:
        raise SystemExit(f"FAIL {ad} {detay}")
    basari += 1
    print(f"  ✓ {ad}")


tmp = Path(tempfile.mkdtemp())
app.ROLLER_PATH = tmp / "roller.json"
app.GORUNURLUK_PATH = tmp / "gorunurluk.json"
telemetri.ANALIST_DOSYA = tmp / "analist.json"

# ── Hash (normalize + salt + PII'siz) ─────────────────────────────────────────
h = app._eposta_hash("Emin@Example.com")
kontrol("hash büyük/küçük normalize", h == app._eposta_hash("emin@example.com"))
kontrol("hash 64 hex", len(h) == 64)
kontrol("boş → ''", app._eposta_hash("") == "")

# ── roller.json PII'siz yazım + geriye-uyumlu okuma ───────────────────────────
app._roller_kaydet({h: "owner"}, {"delta": "owner", "kod": "analist"})
raw = app.ROLLER_PATH.read_text(encoding="utf-8")
kontrol("tracked roller.json ham e-posta içermez", "@" not in raw and "emin" not in raw.lower())
d = app._roller_oku()
kontrol("okuma: kullanıcı rolü", d["kullanicilar"][h] == "owner")
kontrol("okuma: ekran rolü", d["ekran_roller"]["delta"] == "owner")

# eski format (değer dict {rol,...}) geriye-uyumlu
app.ROLLER_PATH.write_text(json.dumps({"kullanicilar": {h: {"rol": "owner", "ac": [], "kapat": []}}}), encoding="utf-8")
kontrol("eski format kullanıcı rolü okunur", app._roller_oku()["kullanicilar"][h] == "owner")

# ── Etkin görünürlük (rol rütbesi) ────────────────────────────────────────────
app._owner_mi = lambda: False
app.GORUNURLUK_PATH.write_text(json.dumps({"gizli": ["brd"]}), encoding="utf-8")   # eski default: brd → owner
app._roller_kaydet({h: "analist"}, {"delta": "owner", "kod": "analist"})
telemetri.analist_yaz("Emin", "emin@example.com")
etkin = set(app._etkin_gizli())
# analist görür: kod(analist), brd? gorunurluk gizli→owner → gizli. delta→owner → gizli.
kontrol("analist: owner-ekranları gizli (delta, brd)", etkin == {"delta", "brd"}, str(etkin))
kontrol("analist: analist-ekranı görünür (kod gizli değil)", "kod" not in etkin)

# aynı kişi owner rolüne yükseltilince hiç gizli kalmaz
app._roller_kaydet({h: "owner"}, {"delta": "owner", "kod": "analist"})
kontrol("owner rolü → hiç gizli yok", app._etkin_gizli() == [])

# kimlik yoksa analist varsayılan (default görünürlük)
telemetri.ANALIST_DOSYA = tmp / "yok.json"
kontrol("kimlik yoksa analist default", set(app._etkin_gizli()) == {"delta", "brd"})

# yerel owner her şeyi görür
app._owner_mi = lambda: True
kontrol("yerel owner → hiç gizli", app._etkin_gizli() == [])

# ── Telemetri isim çekme (benzersiz) ──────────────────────────────────────────
telemetri.olaylari_oku = lambda: [
    {"analist": "Emin K", "eposta": "emin@example.com"},
    {"analist": "Emin K", "eposta": "emin@example.com"},
    {"analist": "Kübra", "eposta": "kubra@example.com"},
    {"analist": "Adsız", "eposta": ""},
]
liste = telemetri.analistler_listesi()
kontrol("telemetri: benzersiz e-posta (2 kişi)",
        {x["eposta"] for x in liste if x["eposta"]} == {"emin@example.com", "kubra@example.com"})

# ── CRUD uçları (owner-gate) ──────────────────────────────────────────────────
app._owner_konsol_aktif = lambda: True
telemetri.ANALIST_DOSYA = tmp / "analist.json"
telemetri.analist_yaz("Owner", "owner@example.com")
c = app.app.test_client()
ORIGIN = {"Origin": "http://localhost"}

r = c.get("/api/roller")
j = r.get_json()
kontrol("GET /api/roller: çekilen kullanıcılar + ekranlar",
        any(u["eposta"] == "emin@example.com" for u in j["kullanicilar"]) and len(j["ekranlar"]) > 0)

r = c.post("/api/roller/kullanici", json={"eposta": "emin@example.com", "rol": "owner"}, headers=ORIGIN)
kontrol("POST rol ata → 200", r.status_code == 200)
kontrol("rol yazıldı (hash→owner)",
        app._roller_oku()["kullanicilar"][app._eposta_hash("emin@example.com")] == "owner")
kontrol("tracked dosyada ham e-posta YOK", "emin@example.com" not in app.ROLLER_PATH.read_text(encoding="utf-8"))

r = c.post("/api/roller/kullanici", json={"eposta": "x@gmail.com", "rol": "owner"}, headers=ORIGIN)
kontrol("POST geçersiz domain → 400", r.status_code == 400)

r = c.post("/api/roller/ekranlar", json={"ekran_roller": {"kopru": "owner", "delta": "analist"}}, headers=ORIGIN)
kontrol("POST ekranlar → 200", r.status_code == 200)
kontrol("ekran rolü yazıldı", app._roller_oku()["ekran_roller"]["kopru"] == "owner")

print(f"\nROLLER TESTLERİ GEÇTİ ({basari} kontrol)")
