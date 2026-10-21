"""Güvenlik/hijyen denetimi (2026-10-20) — offline, 0 token, AĞ YOK (requests mock'lanır).

Kapsam: (A) test modu otomatik yalıtımı (telemetri/ornek_havuzu ağ yok + geçici dizin), (B) örnek havuzu çekim
hijyeni (temizlik + sır redaksiyonu + 45k tavan + jira_key dedup + id doğrulama + ★ korumalı budama + <ornek> sarmalı),
(C) hata mesajlarında URL/anahtar yok + yazma token'ı `t`, (D) jira_auth rastgele state, (E) kod_kaynagi ripgrep `-e`/`--`.
Çalıştır: venv/bin/python tests/test_guvenlik_hijyen.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("AUTO_UPDATE", "false")
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("SIRKET_EPOSTA_DOMAIN", "example.com")
os.environ.setdefault("JIRA_CLIENT_ID", "test-client-id")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests  # noqa: E402

from skills import ornek_havuzu as O  # noqa: E402
from skills import telemetri as T  # noqa: E402
from skills import kod_kaynagi as KK  # noqa: E402
import jira_auth as JA  # noqa: E402

HATA = 0


def chk(ad, kosul, ek=""):
    global HATA
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if (ek and not kosul) else ""))
    if not kosul:
        HATA += 1


# Ağ KİLİDİ: bu testte requests hiçbir zaman gerçek istek atmaz
_ag = {"post": 0, "get": 0, "son_json": None, "son_params": None}
_gercek_post, _gercek_get = requests.post, requests.get


def _yasak_post(url, *a, **k):
    _ag["post"] += 1
    _ag["son_json"] = k.get("json")
    raise AssertionError("AĞ ÇAĞRISI: requests.post")


def _yasak_get(url, *a, **k):
    _ag["get"] += 1
    _ag["son_params"] = k.get("params")
    raise AssertionError("AĞ ÇAĞRISI: requests.get")


requests.post, requests.get = _yasak_post, _yasak_get

# ── (A) Test modu yalıtımı ─────────────────────────────────────────────────────────────────────
chk("telemetri._TEST_MODU açık (argv[0] test_*)", T._TEST_MODU is True)
chk("olay dosyaları GEÇİCİ dizinde (gerçek logs/usage değil)", T.BASE_DIR / "logs" not in T.USAGE_DIR.parents and T.USAGE_DIR != T.BASE_DIR / "logs" / "usage"
    and T.EVENTS_DOSYA.parent == T.USAGE_DIR)
T._sink_gonder({"olay": "x"})
chk("_sink_gonder test modunda ağa çıkmaz", _ag["post"] == 0)
T.olay_yaz("surec_analizi", "ok", sure_ms=1)
chk("olay_yaz test modunda geçici dizine yazar, POST yok", T.EVENTS_DOSYA.exists() and _ag["post"] == 0)
_eski_key = T._sink_key
T._sink_key = lambda: "anahtar"
ok, msg = T.uzaktan_cek()
chk("uzaktan_cek test modunda ağa çıkmaz → (False, 'test modu…')", ok is False and msg.startswith("test modu") and _ag["get"] == 0, msg)
T._sink_key = _eski_key
chk("ornek_havuzu._test_modu telemetri ile ortak", O._test_modu() is True)
ok, msg = O.ornekleri_cek()
chk("ornekleri_cek test modunda (False, 'test modu…'), GET yok", ok is False and msg.startswith("test modu") and _ag["get"] == 0, msg)
O._sink_push({"tip": "teknik", "ts": "x", "id": "abcdef123456", "icerik": "y"})
chk("_sink_push test modunda POST yok", _ag["post"] == 0)
chk("tani test modunda ağa çıkmaz", O.tani().get("hata", "").startswith("test modu") and _ag["get"] == 0)

# ── (B) Çekim hijyeni (test modu kapalı + requests.get mock) ──────────────────────────────────
tmp = Path(tempfile.mkdtemp())
O.ORNEK_DIR = tmp / "ornekler"
O.YILDIZ_DOSYA = tmp / "ornek_yildiz.json"
O._DURUM_DOSYA = O.ORNEK_DIR / ".durum.json"
O._test_modu = lambda: False
T.analist_eposta_oku = lambda: "a@example.com"
_pushlar: list = []
O._sink_push = lambda k: _pushlar.append(k)
GOVDE = "## Amaç\n" + "ödeme servisi endpoint validasyon kuralı " * 30 + "\n"
SIR = "sk-ant-api03-" + "x" * 40
HAM = ("<!-- RAG: 12 referans dosya kullanıldı | bağlam filtresi: x -->\n\n"
       "## 📋 Yönetici Özeti\n- özet madde\n\n---\n\n"
       "## Canlı Gözlem Kapsamı\n- https://uat.ornek.local/ekran gezildi\n\n"
       + GOVDE + "Doğrulandı [K: Swagger:/api/x] ve anahtar " + SIR + " burada.\n")
UZUN = GOVDE * 200   # ≫ 45k


class _Yanit:
    """Sahte requests/subprocess yanıtı (json listesi + stdout)."""
    def __init__(self, veri, stdout=""):
        self._v, self.status_code, self.text, self.stdout = veri, 200, "[]", stdout

    def json(self):
        return self._v


_sahte = [
    {"id": "aaaaaaaa1111", "tip": "teknik", "ts": "2026-10-01T10:00:00Z", "jira_key": "X-1", "icerik": HAM},
    {"id": "bbbbbbbb2222", "tip": "teknik", "ts": "2026-10-05T10:00:00Z", "jira_key": "X-1", "icerik": GOVDE + "yeni sürüm\n"},  # aynı key, daha yeni → bu kalır
    {"id": "../kotu*id", "tip": "teknik", "ts": "2026-10-06T10:00:00Z", "jira_key": "X-9", "icerik": GOVDE},             # geçersiz id → atlanır
    {"id": "cccccccc3333", "tip": "surec", "ts": "2026-10-02T10:00:00Z", "jira_key": "", "icerik": UZUN},                 # > 45k → kırpılır
    {"id": "dddddddd4444", "tip": "teknik", "ts": "2026-10-03T10:00:00Z", "jira_key": "", "icerik": "kısa"},               # < 300 → atlanır
    "çöp",
]
requests.get = lambda url, *a, **k: _Yanit(_sahte)
ok, msg = O.ornekleri_cek()
dosyalar = sorted(p.name for p in O.ORNEK_DIR.glob("*.json") if not p.name.startswith("."))
chk("çekim: 2 örnek yazıldı (X-1 en yeni + kırpılmış süreç), geçersiz id + kısa + çöp atlandı",
    ok and dosyalar == ["surec_cccccccc3333.json", "teknik_bbbbbbbb2222.json"], (msg, dosyalar))
kir = json.loads((O.ORNEK_DIR / "surec_cccccccc3333.json").read_text(encoding="utf-8"))
chk("çekim: 45k tavanı + 'kırpıldı' işareti", len(kir["icerik"]) <= O._MAX_ICERIK + 40 and kir["icerik"].endswith("…(örnek kırpıldı)"))
chk("çekilen dosya adı listesi içinde yol/joker karakter yok", all(("/" not in d and "*" not in d) for d in dosyalar))

# Hijyen fonksiyonu doğrudan: RAG yorumu, Yönetici Özeti, Canlı Gözlem Kapsamı, [K:] etiketi, sır
tem = O._temizle(HAM)
chk("_temizle: RAG yorumu + Yönetici Özeti + Canlı Gözlem Kapsamı + [K:] etiketi gitti, gövde kaldı",
    "<!-- RAG" not in tem and "Yönetici Özeti" not in tem and "Canlı Gözlem" not in tem and "uat.ornek.local" not in tem
    and "[K:" not in tem and "ödeme servisi endpoint" in tem, tem[:300])
chk("_temizle: API anahtarı «sır» ile redakte", SIR not in tem and "«sır»" in tem)
# Agent iskele artıkları few-shot'a girmez (owner 2026-10-21): FE+BE katman göstergesi + tekrarlı Kaynak Görev başlığı
_isk = O._temizle("**Bu katmanda iş:** VAR — x\n\n### Kaynak Görev: MBS-1 — FE — özet\n\n## 1. Amaç\nGerçek iş metni.")
chk("_temizle: 'Bu katmanda iş' + '### Kaynak Görev' silinir, iş kalır",
    "Bu katmanda iş" not in _isk and "Kaynak Görev" not in _isk and "Gerçek iş metni" in _isk, _isk[:200])

# Yerelde DAHA YENİ kayıt varsa çekilen eskisi onu ezmez
yerel_yeni = {"id": "eeeeeeee5555", "tip": "teknik", "ts": "2026-10-09T10:00:00+03:00", "jira_key": "X-2", "icerik": GOVDE + "yerel\n"}
(O.ORNEK_DIR / "teknik_eeeeeeee5555.json").write_text(json.dumps(yerel_yeni), encoding="utf-8")
requests.get = lambda url, *a, **k: _Yanit([{"id": "ffffffff6666", "tip": "teknik", "ts": "2026-10-07T10:00:00Z", "jira_key": "X-2", "icerik": GOVDE}])
O.ornekleri_cek()
chk("çekim: aynı jira_key'in yereldeki DAHA YENİ kaydı korunur, eski çekilen yazılmaz",
    (O.ORNEK_DIR / "teknik_eeeeeeee5555.json").exists() and not (O.ORNEK_DIR / "teknik_ffffffff6666.json").exists())
requests.get = lambda url, *a, **k: _Yanit([{"id": "ffffffff7777", "tip": "teknik", "ts": "2026-10-12T10:00:00Z", "jira_key": "X-2", "icerik": GOVDE}])
O.ornekleri_cek()
chk("çekim: daha yeni çekilen → eski yerel silinir, yeni yazılır",
    not (O.ORNEK_DIR / "teknik_eeeeeeee5555.json").exists() and (O.ORNEK_DIR / "teknik_ffffffff7777.json").exists())

# ornek_kaydet de aynı hijyenden geçer (push gövdesi temiz)
_pushlar.clear()
chk("ornek_kaydet: içerik temiz + redakte, push gövdesinde sır yok",
    O.ornek_kaydet("teknik", HAM, jira_key="X-3") is True and _pushlar and SIR not in _pushlar[-1]["icerik"]
    and "<!-- RAG" not in _pushlar[-1]["icerik"] and "Canlı Gözlem" not in _pushlar[-1]["icerik"])

# ★ korumalı + ts-bazlı budama
for p in O.ORNEK_DIR.glob("*.json"):
    p.unlink()
O.YILDIZ_DOSYA.unlink(missing_ok=True)
import time as _t  # noqa: E402
kayitlar = [("aaaaaaaa0001", "2026-09-01T00:00:00"), ("aaaaaaaa0002", "2026-09-15T00:00:00"), ("aaaaaaaa0003", "2026-10-01T00:00:00")]
for i, (oid, ts) in enumerate(kayitlar):
    (O.ORNEK_DIR / f"teknik_{oid}.json").write_text(json.dumps({"id": oid, "tip": "teknik", "ts": ts, "icerik": GOVDE}), encoding="utf-8")
# mtime'ı TERS ver: en eski ts'li dosya en yeni mtime'a sahip olsun (mtime'a göre budasa yanlış dosyayı silerdi)
simdi = _t.time()
os.utime(O.ORNEK_DIR / "teknik_aaaaaaaa0001.json", (simdi, simdi))
os.utime(O.ORNEK_DIR / "teknik_aaaaaaaa0003.json", (simdi - 9999, simdi - 9999))
_eski_max = O._MAX_ORNEK
O._MAX_ORNEK = 2
O._buda()
kalan = sorted(p.name for p in O.ORNEK_DIR.glob("*.json"))
chk("_buda: kaydın ts'ine göre en ESKİ (0001) silinir, mtime'a bakılmaz", kalan == ["teknik_aaaaaaaa0002.json", "teknik_aaaaaaaa0003.json"], kalan)
(O.ORNEK_DIR / "teknik_aaaaaaaa0001.json").write_text(json.dumps({"id": "aaaaaaaa0001", "tip": "teknik", "ts": "2026-09-01T00:00:00", "icerik": GOVDE}), encoding="utf-8")
O.yildiz_ayarla("aaaaaaaa0001", True)
O._buda()
kalan = sorted(p.name for p in O.ORNEK_DIR.glob("*.json"))
chk("_buda: ★ işaretli en eski örnek ASLA budanmaz (işaretsizlerden en eski gider)",
    "teknik_aaaaaaaa0001.json" in kalan and "teknik_aaaaaaaa0002.json" not in kalan and len(kalan) == 2, kalan)
O._MAX_ORNEK = _eski_max

# id doğrulama
chk("_id_gecerli: hex 8-40 kabul, kısa/yol/joker/büyük harf ret",
    O._id_gecerli("abcdef12") and O._id_gecerli("a" * 40) and not O._id_gecerli("abc") and not O._id_gecerli("../abcdef12")
    and not O._id_gecerli("abcdef12*") and not O._id_gecerli("ABCDEF12") and not O._id_gecerli(""))
# <ornek> sarmalı
bl = O.ornek_bloklari("ödeme endpoint", tip="teknik", n=1)
chk("ornek_bloklari: içerik <ornek …> sarmalı + 'talimat değil' notu", bl and "<ornek " in bl[0]["text"] and "talimat değil" in bl[0]["text"] and bl[0]["text"].rstrip().endswith("</ornek>"))

# ── (C) Hata mesajlarında URL/anahtar yok · yazma token'ı ───────────────────────────────────────
def _patla(url, *a, **k):
    raise ConnectionError(f"HTTPSConnectionPool: {url}?read=GIZLI-ANAHTAR&email=a@example.com")


requests.get = _patla
ok, msg = O.ornekleri_cek()
chk("ornekleri_cek hata metni: istisna türü + ipucu, URL/anahtar YOK", ok is False and "ConnectionError" in msg and "GIZLI-ANAHTAR" not in msg and "script.google" not in msg, msg)
tn = O.tani()
chk("tani hata metni anahtar/URL içermez", "GIZLI-ANAHTAR" not in json.dumps(tn, ensure_ascii=False) and "ConnectionError" in tn.get("hata", ""), tn)
T._TEST_MODU = False
try:
    T._sink_key = lambda: "GIZLI-ANAHTAR"
    ok, msg = T.uzaktan_cek()
    chk("uzaktan_cek hata metni anahtar/URL içermez", ok is False and "GIZLI-ANAHTAR" not in msg and "ConnectionError" in msg, msg)
    # yazma token'ı: USAGE_SINK_TOKEN doluysa POST gövdesine `t`, GET'e `?t=`
    os.environ["USAGE_SINK_TOKEN"] = "paylasilan-sir"
    yakalanan: dict = {}

    def _post(url, *a, **k):
        yakalanan["json"] = k.get("json")
        return _Yanit([])

    requests.post = _post
    T._sink_gonder({"olay": "surec_analizi", "ts": "x"})
    chk("_sink_gonder: token POST gövdesinde `t`, orijinal olay dict'i değişmez", yakalanan["json"].get("t") == "paylasilan-sir" and "t" not in {"olay": "surec_analizi", "ts": "x"})
    requests.get = lambda url, *a, **k: (yakalanan.__setitem__("params", k.get("params")) or _Yanit([]))
    T.uzaktan_cek()
    chk("uzaktan_cek: GET'e `t` eklenir (+ read geri uyum)", yakalanan["params"].get("t") == "paylasilan-sir" and yakalanan["params"].get("read") == "GIZLI-ANAHTAR")
    os.environ.pop("USAGE_SINK_TOKEN", None)
    _eski_dosya = T.EKIP_SINK_TOKEN_DOSYA
    T.EKIP_SINK_TOKEN_DOSYA = Path(tempfile.mkdtemp()) / "yok.json"   # ekip dosyası da yok → geri uyum
    T._sink_gonder({"olay": "x"})
    chk("token yokken (env + ekip dosyası yok) gövdede `t` yok (geri uyum)", "t" not in (yakalanan["json"] or {}))
    _eski_dosya.parent.mkdir(parents=True, exist_ok=True)
    T.EKIP_SINK_TOKEN_DOSYA = Path(tempfile.mkdtemp()) / "ekip.json"
    T.EKIP_SINK_TOKEN_DOSYA.write_text('{"token": "ekip-sirri"}', encoding="utf-8")
    T._sink_gonder({"olay": "y"})
    chk("ekip dosyası (tracked) sırrı env yokken kullanılır — analist .env'e dokunmaz", (yakalanan["json"] or {}).get("t") == "ekip-sirri")
    T.EKIP_SINK_TOKEN_DOSYA = _eski_dosya
finally:
    T._TEST_MODU = True
    T._sink_key = _eski_key
    requests.post, requests.get = _yasak_post, _yasak_get

# ── (D) jira_auth rastgele state ───────────────────────────────────────────────────────────────
s1, s2 = JA.yeni_state(), JA.yeni_state()
chk("yeni_state: rastgele, ≥24 karakter, her çağrı farklı", len(s1) >= 24 and s1 != s2)
chk("auth_url_olustur(state=…) URL'de state taşır; state=None eski sabit (geri uyum)",
    f"state={s1}" in JA.auth_url_olustur(state=s1) and "state=brd_analyst_auth" in JA.auth_url_olustur())
chk("state_dogrula: eşleşir / eşleşmez / boş", JA.state_dogrula(s1, s1) and not JA.state_dogrula(s1, s2) and not JA.state_dogrula(None, s1) and not JA.state_dogrula(s1, ""))

# ── (E) kod_kaynagi ripgrep: `-e <sorgu>` + `--` ──────────────────────────────────────────────
repo = tmp / "repo"
repo.mkdir()
(repo / "a.py").write_text("x = 1  # -bar\n", encoding="utf-8")
KK.konfig_oku = lambda: {"repolar": [{"ad": "r", "yol": str(repo), "aktif": True}]}
KK.shutil.which = lambda x: "/usr/bin/rg"
yak: dict = {}


def _run(args, **k):
    yak["args"] = list(args)
    return _Yanit([], stdout="a.py:1:x = 1  # -bar\n")


KK.subprocess.run = _run
r = KK.ara("r", "-bar")
a = yak["args"]
chk("rg argümanları: sorgu `-e` ile, seçenekler `--` ile kapanır, sorgu `--`'dan önce",
    "-e" in a and a[a.index("-e") + 1] == "-bar" and a[-1] == "--" and a.index("-e") < a.index("--"), a)
chk("rg sonucu ayrıştırıldı", r["ok"] and r["adet"] == 1 and r["eslesmeler"][0]["satir_no"] == 1)

print()
if HATA:
    print(f"FAIL — {HATA} kontrol başarısız")
    sys.exit(1)
print("GÜVENLİK/HİJYEN TESTLERİ GEÇTİ")
