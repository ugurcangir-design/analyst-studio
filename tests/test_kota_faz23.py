"""Kota Faz 2 + Faz 3 — hedefli 'Cevapları İşle' + model katmanları (offline, 0 token; AI/CLI MOCK).

Faz 2: `gorev_cevap_uygula` cevapları MEVCUT analize hedefli düzeltmeyle işler (gözlem/RAG/öz-çözümleme tekrarı yok),
kalan soruları yakınsar; RAG yorumu korunur; mevcut analiz yoksa ValueError (çağıran tam üretime düşer); `CEVAP_HEDEFLI`.
App iş modu `cevap` aynı yolu kullanır. Faz 3: `cli_model_katman` (ana/yardimci/hafif → CLAUDE_CLI_MODEL /
CLI_MODEL_YARDIMCI / CLI_MODEL_HAFIF), `_api_cagri` katmanı açık parametreden ya da model sabitinden türetir ve
`_api_cagri_cli`'ya geçirir; önbellek anahtarı katmana göre ayrışır; yardımcı çağrı noktaları (gözlem, giriş, kabul,
soru çözümleme, düzelt) katman='yardimci' geçer."""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("AUTO_UPDATE", "false")
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("JIRA_KOPRU", "false")
os.environ.setdefault("SIRKET_EPOSTA_DOMAIN", "example.com")
os.environ.pop("CLI_MODEL_YARDIMCI", None)
os.environ.pop("CLI_MODEL_HAFIF", None)
os.environ["CLAUDE_CLI_MODEL"] = "claude-opus-5-5"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import skills.base as base                 # noqa: E402
import skills.jira_gorevleri as jg         # noqa: E402

HATA = 0


def chk(ad: str, kosul: bool) -> None:
    global HATA
    print(("  ✓ " if kosul else "  ✗ ") + ad)
    if not kosul:
        HATA += 1


# ── Faz 3: katman → model ─────────────────────────────────────────────────────
chk("ana katman = CLAUDE_CLI_MODEL", base.cli_model_katman("ana") == "claude-opus-5-5")
chk("boş katman = ana", base.cli_model_katman("") == "claude-opus-5-5")
chk("yardimci varsayılan sonnet", base.cli_model_katman("yardimci") == "sonnet")
chk("hafif varsayılan haiku", base.cli_model_katman("hafif") == "haiku")
os.environ["CLI_MODEL_YARDIMCI"] = "claude-sonnet-5-5"
chk("yardimci env ile ezilir (restart'sız)", base.cli_model_katman("yardimci") == "claude-sonnet-5-5")
os.environ["CLI_MODEL_YARDIMCI"] = ""
chk("boş env → varsayılan", base.cli_model_katman("yardimci") == "sonnet")
os.environ.pop("CLI_MODEL_YARDIMCI", None)

_eski_cli = base.USE_CLAUDE_CLI
base.USE_CLAUDE_CLI = True
k_ana = base._api_cache_key("s", [{"role": "user", "content": "m"}], base.MODEL_ANALIZ, 100, False, "ana")
k_yar = base._api_cache_key("s", [{"role": "user", "content": "m"}], base.MODEL_ANALIZ, 100, False, "yardimci")
chk("önbellek anahtarı katmana göre ayrışır (aynı girdi, farklı model)", k_ana != k_yar)

yakalanan: list = []


def _sahte_cli(sistem, mesajlar, canli_uygulama_kapsami=None, max_turns=None, katman="ana", **kw):
    yakalanan.append(katman)
    return "<x>ok</x>"


_eski_cli_fn = base._api_cagri_cli
base._api_cagri_cli = _sahte_cli
base._api_cagri("s", [{"role": "user", "content": "a"}], onbellek=False)
base._api_cagri("s", [{"role": "user", "content": "b"}], model=base.MODEL_HAFIF, onbellek=False)
base._api_cagri("s", [{"role": "user", "content": "c"}], model=base.MODEL_YARDIMCI, onbellek=False)
base._api_cagri("s", [{"role": "user", "content": "d"}], katman="yardimci", onbellek=False)
base._api_cagri("s", [{"role": "user", "content": "e"}], model=base.MODEL_HAFIF, katman="ana", onbellek=False)
chk("katman türetme: varsayılan ana · MODEL_HAFIF→hafif · MODEL_YARDIMCI→yardimci · açık katman · açık katman model sabitini ezer",
    yakalanan == ["ana", "hafif", "yardimci", "yardimci", "ana"])
chk("jira_gorevleri MODEL_HAFIF sabiti base ile aynı (hafif katman türetmesi çalışsın)", jg.MODEL_HAFIF == base.MODEL_HAFIF)
base._api_cagri_cli = _eski_cli_fn
base.USE_CLAUDE_CLI = _eski_cli

# Yardımcı çağrı noktaları gerçekten katman geçiyor mu (kaynak düzeyinde — davranış testi yukarıda)
kok = Path(__file__).resolve().parents[1] / "skills"
for mod, n in (("gozlem.py", 1), ("canli_giris.py", 1), ("bff_kesif.py", 1), ("kabul_kontrolu.py", 2),
               ("soru_cozumleme.py", 2), ("sohbet_analiz.py", 1)):
    chk(f"{mod}: {n} yardımcı çağrı", (kok / mod).read_text(encoding="utf-8").count('katman="yardimci"') == n)
chk("jira_gorevleri: düzeltme yardımcı katmanda",
    'katman="yardimci"' in (kok / "jira_gorevleri.py").read_text(encoding="utf-8").split("def gorev_analiz_duzelt", 1)[1].split("\ndef ", 1)[0])

# ── Faz 2: hedefli cevap uygulama ─────────────────────────────────────────────
duzelt_girdi: list = []
soru_girdi: list = []
jg.gorev_analiz_duzelt = lambda gorev, mevcut, talimat: duzelt_girdi.append((mevcut, talimat)) or (mevcut + "\n\n[İŞLENDİ]")
jg._gorev_acik_sorular_uret = lambda md, gorev, cevaplar="", onceki_sorular="": soru_girdi.append((cevaplar, onceki_sorular)) or "Q-T-002: kalan?"

gorev = {"key": "MBSTRADE-7", "summary": "Filtre alanı", "description": "açıklama"}
md = "<!-- RAG: a, b -->\n# Analiz\n\n## 3. Kural\n`[K: ❓ Belirsiz]` alan zorunlu mu?"
r = jg.gorev_cevap_uygula(gorev, md, "Q-T-001: alan zorunlu değil", onceki_sorular="Q-T-001: zorunlu mu?")
chk("hedefli: düzeltme çağrısı mevcut gövdeyle (RAG yorumu gövdeden çıkarılmış)", duzelt_girdi and duzelt_girdi[0][0].startswith("# Analiz"))
chk("hedefli: talimat cevapları ve işleme kurallarını içerir",
    "Q-T-001: alan zorunlu değil" in duzelt_girdi[0][1] and "Analist cevabı" in duzelt_girdi[0][1] and "DOKUNMA" in duzelt_girdi[0][1])
chk("hedefli: RAG yorumu sonuçta korunur + düzeltilmiş gövde", r["markdown"].startswith("<!-- RAG: a, b -->") and "[İŞLENDİ]" in r["markdown"])
chk("hedefli: kalan sorular yakınsama ile (cevaplar + önceki sorular geçer)",
    r["acik_sorular"] == "Q-T-002: kalan?" and soru_girdi[0] == ("Q-T-001: alan zorunlu değil", "Q-T-001: zorunlu mu?"))
chk("hedefli: sonuç bayrağı", r.get("hedefli") is True)
try:
    jg.gorev_cevap_uygula(gorev, "", "Q-T-001: x")
    chk("mevcut analiz yoksa ValueError", False)
except ValueError:
    chk("mevcut analiz yoksa ValueError (çağıran tam üretime düşer)", True)
try:
    jg.gorev_cevap_uygula(gorev, md, "  ")
    chk("boş cevap ValueError", False)
except ValueError:
    chk("boş cevap ValueError", True)
jg._gorev_acik_sorular_uret = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("soru üretimi düştü"))
r2 = jg.gorev_cevap_uygula(gorev, md, "Q-T-001: x")
chk("soru üretimi düşerse cevaplar yine işlenir (acik boş)", "[İŞLENDİ]" in r2["markdown"] and r2["acik_sorular"] == "")
os.environ["CEVAP_HEDEFLI"] = "false"
chk("CEVAP_HEDEFLI=false kapatır", jg.cevap_hedefli_acik() is False)
os.environ.pop("CEVAP_HEDEFLI", None)
chk("varsayılan açık", jg.cevap_hedefli_acik() is True)

# ── App iş modu 'cevap' → hedefli yol (Flask test client, görev dict'li adım → Jira gerekmez) ──
_tmp = Path(tempfile.mkdtemp())
import app as A                            # noqa: E402
A.OUTPUT_DIR = _tmp
A._kimlik_tam_mi = lambda *a, **k: True   # kimlik kapısı (test)
A._gorev_egitim_topla = lambda *a, **k: None
A._telemetri_olay = lambda *a, **k: None
cagri: list = []
jg.gorev_cevap_uygula = lambda gorev, mevcut, cevaplar, onceki_sorular="": cagri.append(("hedefli", gorev["key"], mevcut, cevaplar)) or {
    "markdown": mevcut + "\n\n[CEVAP]", "acik_sorular": "", "hedefli": True}
# app.py motoru fonksiyon içinde `from skills.jira_gorevleri import …` ile alır → MODÜL özniteliği mock'lanır
jg.gorev_analiz_et = lambda *a, **k: cagri.append(("tam",)) or {"markdown": "TAM", "acik_sorular": ""}
jg.gorev_getir = lambda key: gorev
c = A.app.test_client()
H = {"Origin": "http://localhost"}
adim = [{"key": "MBSTRADE-7", "mode": "cevap", "markdown": "# Mevcut analiz\n\nx", "cevaplar": "Q-T-001: evet",
         "onceki_sorular": "Q-T-001: ?", "gorev": gorev}]
r = c.post("/api/jira/gorev/is/baslat", json={"adimlar": adim}, headers=H)
chk("iş başlatıldı (mode cevap, görev dict'li → Jira bağlantısı istenmez)", r.status_code == 200 and r.get_json().get("job"))
job = r.get_json()["job"]
for _ in range(100):
    d = c.get(f"/api/jira/gorev/is/durum?job={job}", headers=H).get_json()
    if d.get("durum") in ("bitti", "hata", "durduruldu"):
        break
    time.sleep(0.05)
son = (d.get("sonuclar") or {}).get("MBSTRADE-7") or {}
chk("iş tamamlandı ve sonuç hedefli yoldan geldi (tam üretim YOK)",
    d.get("durum") == "bitti" and cagri and cagri[-1][0] == "hedefli" and "[CEVAP]" in son.get("markdown", "") and not any(x[0] == "tam" for x in cagri))
cagri.clear()
adim2 = [{"key": "MBSTRADE-7", "mode": "cevap", "markdown": "", "cevaplar": "Q-T-001: evet", "gorev": gorev}]
job2 = c.post("/api/jira/gorev/is/baslat", json={"adimlar": adim2}, headers=H).get_json()["job"]
for _ in range(100):
    d = c.get(f"/api/jira/gorev/is/durum?job={job2}", headers=H).get_json()
    if d.get("durum") in ("bitti", "hata", "durduruldu"):
        break
    time.sleep(0.05)
chk("editör boşsa (mevcut analiz yok) tam üretime düşer", d.get("durum") == "bitti" and cagri and cagri[-1][0] == "tam")

print()
if HATA:
    print(f"FAIL — {HATA} kontrol başarısız")
    sys.exit(1)
print("KOTA FAZ 2+3 TESTLERİ GEÇTİ")
