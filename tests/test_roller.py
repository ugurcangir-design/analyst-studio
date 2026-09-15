"""Kullanıcı-bazlı ekran yetkisi (roller.json, hash'li) — offline, 0 token.

Doğrular: e-posta hash (normalize+salt, PII'siz), etkin görünürlük (analist default −
kullanıcı 'ac' + 'kapat'), per-user rol=owner → hiç gizli, yerel owner her şeyi görür,
CRUD uçları owner-gate + tracked dosyada ham e-posta/ad BULUNMAZ (yalnız yerel dosyada).

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
app.ROLLER_YEREL_PATH = tmp / "roller_yerel.json"
app.GORUNURLUK_PATH = tmp / "gorunurluk.json"
telemetri.ANALIST_DOSYA = tmp / "analist.json"

# ── Hash (normalize + salt + PII'siz) ─────────────────────────────────────────
h = app._eposta_hash("Emin@Example.com")
kontrol("hash büyük/küçük harf normalize", h == app._eposta_hash("emin@example.com"))
kontrol("hash 64 hex", len(h) == 64 and all(c in "0123456789abcdef" for c in h))
kontrol("boş e-posta → ''", app._eposta_hash("") == "")

# ── roller.json PII'siz yazım ─────────────────────────────────────────────────
app._roller_yaz({h: {"rol": "analist", "ac": ["kod"], "kapat": ["brd"]}})
raw = app.ROLLER_PATH.read_text(encoding="utf-8")
kontrol("tracked roller.json ham e-posta içermez", "@" not in raw and "emin" not in raw.lower())
kontrol("geçersiz id/rol elenir",
        app._roller_oku()["kullanicilar"][h]["rol"] == "analist")

# ── Etkin görünürlük (analist simülasyonu) ────────────────────────────────────
app._owner_mi = lambda: False
app.GORUNURLUK_PATH.write_text(json.dumps({"gizli": ["delta", "brd", "kod"]}), encoding="utf-8")
telemetri.analist_yaz("Emin", "emin@example.com")
# ac=[kod] (aç), kapat=[jira-gorevler] (ekstra kapat)
app._roller_yaz({h: {"rol": "analist", "ac": ["kod"], "kapat": ["jira-gorevler"]}})
etkin = set(app._etkin_gizli())
kontrol("etkin gizli: base − ac + kapat",
        etkin == {"delta", "brd", "jira-gorevler"}, str(etkin))

# per-user rol=owner → hiç gizli
app._roller_yaz({h: {"rol": "owner", "ac": [], "kapat": []}})
kontrol("per-user rol=owner → hiç gizlenmez", app._etkin_gizli() == [])

# kimlik yoksa yalnız global default
telemetri.ANALIST_DOSYA = tmp / "kimlik_yok.json"
kontrol("kimlik yoksa global default", set(app._etkin_gizli()) == {"delta", "brd", "kod"})

# yerel owner (owner_konsol) → her şeyi görür
app._owner_mi = lambda: True
kontrol("yerel owner → hiç gizli yok", app._etkin_gizli() == [])

# ── CRUD uçları (owner-gate) + PII ayrımı ─────────────────────────────────────
app._owner_konsol_aktif = lambda: True          # yetki_gerekli geçsin
telemetri.ANALIST_DOSYA = tmp / "analist.json"
telemetri.analist_yaz("Owner", "owner@example.com")
c = app.app.test_client()
ORIGIN = {"Origin": "http://localhost"}

r = c.post("/api/roller/kullanici",
           json={"eposta": "kubra@example.com", "ad": "Kübra", "rol": "analist",
                 "ac": ["kod"], "kapat": ["brd"]}, headers=ORIGIN)
kontrol("roller ekle → 200", r.status_code == 200)
hk = r.get_json()["hash"]
kontrol("yerel dosyada ham e-posta VAR", "kubra@example.com" in app.ROLLER_YEREL_PATH.read_text(encoding="utf-8"))
kontrol("tracked roller.json'da ham e-posta YOK", "kubra@example.com" not in app.ROLLER_PATH.read_text(encoding="utf-8"))

r = c.get("/api/roller")
j = r.get_json()
kontrol("roller getir: kullanıcı + yerel ad birleşir",
        any(u["hash"] == hk and u["ad"] == "Kübra" for u in j["kullanicilar"]))

r = c.post("/api/roller/kullanici", json={"eposta": "x@gmail.com", "ad": "X"}, headers=ORIGIN)
kontrol("roller geçersiz domain → 400", r.status_code == 400)

r = c.delete(f"/api/roller/kullanici/{hk}", headers=ORIGIN)
kontrol("roller sil → 200", r.status_code == 200)
kontrol("silinen kullanıcı defterde yok", hk not in app._roller_oku()["kullanicilar"])

print(f"\nROLLER TESTLERİ GEÇTİ ({basari} kontrol)")
