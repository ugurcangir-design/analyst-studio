"""Bağlam filtresi — Jira Issue Keys uzaktan çekme (offline, 0 token, ağ MOCK).

Regresyon: süreç analizi ekranında "Jira Issue Keys" alanına girilen key'ler yerel
export'ta (reference/jira/*.json) yoksa bağlama EKLENMİYORDU. Artık eksik key'ler
doğrudan Jira'dan (bulkfetch) çekilir; yerelde olan tekrar çekilmez; Jira bağlı
değilse akış kırılmaz.

Çalıştır:  venv/bin/python tests/test_baglam_jira.py
"""

import json
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

import skills.base as B  # noqa: E402
import skills.jira_gorevleri as JG  # noqa: E402

basari = 0


def kontrol(ad: str, kosul: bool) -> None:
    global basari
    if not kosul:
        raise SystemExit(f"FAIL {ad}")
    basari += 1
    print(f"  ✓ {ad}")


def _izole():
    tmp = Path(tempfile.mkdtemp())
    B.REF_DIR = tmp
    B.JIRA_REF_DIR = tmp / "jira"
    B.JIRA_REF_DIR.mkdir(parents=True, exist_ok=True)
    return tmp


CTX = {"keywords": [], "jira_keys": ["MBS-100", "MBS-200"], "confluence_pages": []}


# ── 1) Yerel export YOK → girilen key'ler doğrudan Jira'dan çekilir ─────────────
_izole()
JG._cloud_id = lambda: "fake-cloud"
JG._taze_issue_oku = lambda keys, cid: {
    "MBS-100": {"key": "MBS-100", "summary": "Ödeme ekranı", "description": "Ödeme akışı detayı"},
    "MBS-200": {"key": "MBS-200", "summary": "Sipariş listesi", "description": "Liste kuralları"},
}
sonuc = B.filtrele_referanslar([], CTX)
tmpf = [p for p in sonuc if p.name == "_context_filtered.json"]
kontrol("yerel export olmadan sonuç üretildi", bool(tmpf))
issues = json.loads(tmpf[0].read_text(encoding="utf-8")) if tmpf else []
kontrol("iki key de çekildi", sorted(i["key"] for i in issues) == ["MBS-100", "MBS-200"])
kontrol("task içeriği (description) bağlama girdi",
        any("Ödeme akışı" in i.get("description", "") for i in issues))

# ── 2) Biri yerelde var → yalnız EKSİK olan çekilir (çift çekme yok) ────────────
tmp = _izole()
(B.JIRA_REF_DIR / "MBS.json").write_text(
    json.dumps([{"key": "MBS-100", "summary": "Yerel", "description": "yerelden"}], ensure_ascii=False),
    encoding="utf-8")
_cagrilan = {"keys": None}


def _spy(keys, cid):
    _cagrilan["keys"] = list(keys)
    return {"MBS-200": {"key": "MBS-200", "summary": "Sipariş", "description": "x"}}


JG._taze_issue_oku = _spy
B.filtrele_referanslar([B.JIRA_REF_DIR / "MBS.json"], CTX)
kontrol("yalnız eksik key uzaktan çekildi", _cagrilan["keys"] == ["MBS-200"])

# ── 3) Jira bağlı değil → akış kırılmaz (boş, hatasız) ─────────────────────────
_izole()
JG._cloud_id = lambda: ""
sonuc3 = B.filtrele_referanslar([], {"keywords": [], "jira_keys": ["ZZ-1"], "confluence_pages": []})
kontrol("Jira bağlı değilken hata yok", isinstance(sonuc3, list))

# ── 4) Uzaktan çekme hatası → boş liste (yutulur) ──────────────────────────────
def _patla(keys, cid):
    raise RuntimeError("ağ hatası")


JG._cloud_id = lambda: "fake"
JG._taze_issue_oku = _patla
kontrol("fetch hatası yutulur → boş liste", B._jira_keyleri_uzaktan_cek(["X-1"]) == [])

print(f"\nBAĞLAM JIRA TESTLERİ GEÇTİ ({basari} kontrol)")
