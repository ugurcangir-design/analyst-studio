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
_eski_cache_dir = base._API_CACHE_DIR
base._API_CACHE_DIR = Path(tempfile.mkdtemp())
base._api_cache_yaz(k_yar, "bozuk yanıt")
chk("api_cache_sil: _api_cagri ile AYNI argümanlardan anahtar türetir, kaydı siler (atomik yazılmış .txt), ikinci çağrı False",
    base._api_cache_oku(k_yar) == "bozuk yanıt" and not list(base._API_CACHE_DIR.glob("*.tmp"))
    and base.api_cache_sil("s", [{"role": "user", "content": "m"}], max_tokens=100, katman="yardimci") is True
    and base._api_cache_oku(k_yar) is None
    and base.api_cache_sil("s", [{"role": "user", "content": "m"}], max_tokens=100, katman="yardimci") is False)
base._API_CACHE_DIR = _eski_cache_dir

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
               ("soru_cozumleme.py", 3), ("sohbet_analiz.py", 2)):   # +1: bozuk yanıtta önbelleksiz tekrar
    chk(f"{mod}: {n} yardımcı çağrı", (kok / mod).read_text(encoding="utf-8").count('katman="yardimci"') == n)
chk("jira_gorevleri: düzeltme yardımcı katmanda",
    'katman="yardimci"' in (kok / "jira_gorevleri.py").read_text(encoding="utf-8").split("def gorev_analiz_duzelt", 1)[1].split("\ndef ", 1)[0])

# ── Faz 2: hedefli cevap uygulama ─────────────────────────────────────────────
duzelt_girdi: list = []
soru_girdi: list = []
_ORJ_DUZELT = jg.gorev_analiz_duzelt   # aşağıda gerçek fonksiyon (asama/özet) test edilir
jg.gorev_analiz_duzelt = lambda gorev, mevcut, talimat, **kw: duzelt_girdi.append((mevcut, talimat)) or (mevcut + "\n\n[İŞLENDİ]")
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
# Özetli girdi: Yönetici Özeti düzeltmeye GİTMEZ, sonuçta güncel sayaçlarla YENİDEN kurulur; RAG yorumu ilk 3 satırda olsa da bulunur
jg._gorev_acik_sorular_uret = lambda md, gorev, cevaplar="", onceki_sorular="": "### Q-T-009: kalan\n- Soru: ?"
duzelt_girdi.clear()
md_ozetli = base.yonetici_ozeti_olustur("## 1. Amaç\nx", acik_sorular="### Q-T-001: a\n### Q-T-002: b") + "<!-- RAG: 2 referans -->\n\n## 1. Amaç\nx\n\n| GET /a | b |"
r3 = jg.gorev_cevap_uygula(gorev, md_ozetli, "Q-T-001: cevap")
chk("cevap: özet + RAG gövdeden ayrıldı (düzeltmeye yalnız saf gövde gitti)", duzelt_girdi[-1][0].startswith("## 1. Amaç") and "Yönetici Özeti" not in duzelt_girdi[-1][0]
    and "RAG:" not in duzelt_girdi[-1][0])
chk("cevap: RAG yorumu geri + özet YENİDEN (kalan 1 soru) + tek özet bloğu", r3["markdown"].startswith("<!-- RAG: 2 referans -->")
    and base.yonetici_ozetini_cikar(r3["markdown"]) != r3["markdown"] and r3["markdown"].count("Yönetici Özeti") == 1
    and "[İŞLENDİ]" in r3["markdown"])
asamalar: list = []
_eski_asama = jg.asama_ayarla
jg.asama_ayarla = lambda ad: asamalar.append(ad)
jg._api_cagri = lambda s, m, **k: "<teknik_analiz>## 1. Amaç\ndüzeltildi\n</teknik_analiz>"
_gercek_duzelt = _ORJ_DUZELT
_gercek_duzelt(gorev, "## 1. Amaç\nx", "düzelt", asama="gorev:cevap")
chk("gorev_analiz_duzelt(asama=…) telemetri etiketi ezilmez ('gorev:cevap')", asamalar[-1] == "gorev:cevap")
_gercek_duzelt(gorev, "## 1. Amaç\nx", "düzelt")
chk("varsayılan etiket 'gorev:duzelt'", asamalar[-1] == "gorev:duzelt")
r4 = _gercek_duzelt(gorev, base.yonetici_ozeti_olustur("## 1. Amaç\nx") + "<!-- RAG: 1 -->\n\n## 1. Amaç\nx", "düzelt")
chk("düzelt: özetli girdi → çıktıda RAG yorumu + tek yeni özet + düzeltilmiş gövde", r4.startswith("<!-- RAG: 1 -->") and r4.count("Yönetici Özeti") == 1
    and "düzeltildi" in r4)
jg.asama_ayarla = _eski_asama
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

# Deterministik yakınsama: cevaplanan soru ID'leri model bıraksa da düşer (owner 2026-10-21 — 'aynı soruyu tekrar çıkarıyor')
_acik = "### Q-T-001: x?\n- Soru: a\n\n### Q-T-004: y?\n- Soru: b\n\n### Q-T-007: yeni?\n- Soru: c"
_dus = jg._cevaplanan_sorulari_dus(_acik, "Q-T-001: cevap var\nQ-T-004: dev ekibi karar verir")
chk("cevaplanan Q-T-001/004 düşer, cevaplanmayan Q-T-007 kalır",
    "Q-T-001" not in _dus and "Q-T-004" not in _dus and "Q-T-007" in _dus)
chk("hepsi cevaplanırsa 'tespit edilmedi'", "tespit edilmedi" in jg._cevaplanan_sorulari_dus("### Q-T-001: x\n- Soru: ?", "Q-T-001: a"))
chk("ID normalize (QT1 == Q-T-001)", "Q-T-001" not in jg._cevaplanan_sorulari_dus("### Q-T-001: x\n- Soru: ?", "QT1: a"))
chk("cevap boşsa açık sorular aynen kalır", jg._cevaplanan_sorulari_dus(_acik, "") == _acik)

print()
if HATA:
    print(f"FAIL — {HATA} kontrol başarısız")
    sys.exit(1)
print("KOTA FAZ 2+3 TESTLERİ GEÇTİ")
