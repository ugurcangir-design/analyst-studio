"""Faz 0 ölçüm + Faz 1 gözlem fazı (offline, 0 token, AI/CLI MOCK).

Kapsam:
  1. gozlem.rapor_al: küçük prompt (referans/few-shot yok), <gozlem_raporu> parse, etiketsiz gövde kabul, dosya + meta;
     yeniden=False + taze → önbellekten (AI çağrılmaz); yeniden=True → her zaman gözler; blok yok → ok False, analiz kırılmaz
  2. rapor_blogu / gozlem_yok_blogu metinleri
  3. gorev_analiz_et: canlı blok varken analiz çağrısı TARAYICISIZ (kapsam yok) + rapor bloğu promptta; cevap turu
     yeniden=False; gözlem başarısız → 'YAPILAMADI' bloğu; fe_be → TEK gözlem iki analiz
  4. surec/teknik motorları: kaynakta gözlem fazı + canli_uygulama_kapsami yok
  5. Faz 0: _api_cagri max_turns → --max-turns; error_max_turns → --resume ile tamamlatma; cagri.jsonl kaydı (aşama/tur/token);
     cagri_ozeti toplama; asama_ayarla etiketleri; snapshot diyeti kuralı promptta; uç + UI paneli
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("BILDIRIM", "false")

from skills import base as B  # noqa: E402
from skills import gozlem as GZ  # noqa: E402

_hata = 0


def chk(ad, kosul, ek=""):
    global _hata
    if not kosul:
        _hata += 1
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if ek and not kosul else ""))


tmp = Path(tempfile.mkdtemp())
GZ.GOZLEM_DIR = tmp / "gozlem"
GZ._api_cagri = lambda *a, **k: (_ for _ in ()).throw(AssertionError("Gerçek AI çağrısı!"))
GZ.gozlem_durum_oku = lambda: {"yapildi": True, "num_turns": 12}
yak: dict = {}
RAPOR = "<gozlem_raporu>\n## Ekran ve Navigasyon\n- /sports `[K: Canlı UI:/sports]`\n\n## Aksiyonlar → Servis Çağrıları\n| Kaydet | POST /bff/sports | 201 | id | liste yenilendi |\n`[K: Network:POST /bff/sports → 201]`\n</gozlem_raporu>"


def ai(cevap):
    def f(s, m):
        yak["sistem"] = s
        yak["metin"] = "\n".join(p["text"] for p in m[0]["content"])
        yak["n"] = yak.get("n", 0) + 1
        return cevap
    return f


CANLI = "### CANLI UYGULAMA MCP/CHROME GÖREVİ\n1. https://uat-ornek.local/app/sports\n### OTOMATİK GİRİŞ\n…"

print("1) rapor_al")
r = GZ.rapor_al(CANLI, "gorev", gorev_ozet="S" * 5000, yeniden=True, _ai=ai(RAPOR))
chk("ok + md + dosya + meta; prompt küçük (referans yok, özet kırpık)", r["ok"] and "POST /bff/sports" in r["md"] and Path(r["yol"]).exists()
    and "GÖZLEM RAPORU BİÇİMİ" in yak["metin"] and "kırpıldı" in yak["metin"] and "ONAYLI ÖRNEK" not in yak["metin"] and len(yak["metin"]) < 9000, len(yak["metin"]))
yak["n"] = 0
OZ = "S" * 5000
r2 = GZ.rapor_al(CANLI, "gorev", gorev_ozet=OZ, yeniden=False, _ai=ai(RAPOR))
chk("yeniden=False + taze → önbellekten, AI çağrılmadı", r2["yeniden_kullanildi"] and yak["n"] == 0 and r2["md"] == r["md"])
r2b = GZ.rapor_al(CANLI, "gorev", gorev_ozet="BAŞKA task odağı", yeniden=False, _ai=ai(RAPOR))
chk("önbellek GÖREV ODAĞINA göre: aynı URL, farklı task → yeniden gözler (başkasının raporu devralınmaz)",
    yak["n"] == 1 and not r2b["yeniden_kullanildi"] and r2b["anahtar"] != r2["anahtar"])
yak["n"] = 0
r3 = GZ.rapor_al(CANLI, "gorev", gorev_ozet=OZ, yeniden=True, _ai=ai(RAPOR))
chk("yeniden=True → her zaman gözler", yak["n"] == 1 and not r3["yeniden_kullanildi"])
os.environ["GOZLEM_RAPOR_GECERLILIK"] = "1"
time.sleep(1.1)
GZ.rapor_al(CANLI, "gorev", gorev_ozet=OZ, yeniden=False, _ai=ai(RAPOR))
chk("geçerlilik dolunca yeniden gözler", yak["n"] == 2)
os.environ.pop("GOZLEM_RAPOR_GECERLILIK", None)
r_bos = GZ.rapor_al(CANLI + "q", "gorev", _ai=ai("<gozlem_raporu>\n## Ekran ve Navigasyon\n- bir şey\n\n## Aksiyonlar → Servis Çağrıları\n| Aksiyon | İstek |\n</gozlem_raporu>"))
chk("kanıt etiketi YOKSA ok=False (şablondaki '## Aksiyonlar' başlığı kanıt değil) → taze sayılmaz", not r_bos["ok"] and r_bos["md"]
    and not GZ.taze_mi(GZ.rapor_oku(r_bos["anahtar"])))
GZ.gozlem_durum_oku = lambda: {"yapildi": True, "num_turns": 12, "zaman": "2020-01-01T00:00:00"}
r_eski = GZ.rapor_al(CANLI + "w", "gorev", _ai=ai(RAPOR))
chk("bu çağrıdan ÖNCE yazılmış .gozlem-durum.json (başka akışın kalıntısı) 'yapıldı' sayılmaz → ok=False", not r_eski["ok"])
GZ.gozlem_durum_oku = lambda: {"yapildi": True, "num_turns": 12, "zaman": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() + 5))}
chk("bu çağrıdan SONRA yazılmış durum → ok", GZ.rapor_al(CANLI + "w2", "gorev", _ai=ai(RAPOR))["ok"])
GZ.gozlem_durum_oku = lambda: {"yapildi": True, "num_turns": 12}
r4 = GZ.rapor_al(CANLI + "x", "gorev", _ai=ai("## Ekran ve Navigasyon\n- /x `[K: Canlı UI:/x]`\n\n## Aksiyonlar → Servis Çağrıları\n- yok"))
chk("etiketsiz ama gövdeli yanıt kabul", r4["ok"] and "## Ekran" in r4["md"])
r5 = GZ.rapor_al(CANLI + "y", "gorev", _ai=ai("blok yok"))
chk("blok yok → ok False + neden (fırlatmaz)", not r5["ok"] and "üretilemedi" in r5["neden"])
GZ.gozlem_durum_oku = lambda: {"yapildi": False, "num_turns": 1}
r6 = GZ.rapor_al(CANLI + "z", "gorev", _ai=ai(RAPOR))
chk("makine-doğrulama 'yapılmadı' → ok False (taze sayılmaz)", not r6["ok"] and not GZ.taze_mi(GZ.rapor_oku(r6["anahtar"])))
GZ.gozlem_durum_oku = lambda: {"yapildi": True, "num_turns": 12}
r7 = GZ.rapor_al(CANLI, "gorev", _ai=lambda s, m: (_ for _ in ()).throw(RuntimeError("MCP yok")))
chk("AI hatası → ok False, neden", not r7["ok"] and "çalıştırılamadı" in r7["neden"])

print("2) bloklar")
b = GZ.rapor_blogu(r)
chk("rapor bloğu: başlık + 'tarayıcı aracı YOK' + md", b.startswith("### CANLI UYGULAMA GÖZLEM RAPORU") and "tarayıcı aracı YOK" in b and "POST /bff/sports" in b)
chk("önbellek notu", "önbellekten" in GZ.rapor_blogu(r2))
chk("gözlem yok bloğu", "YAPILAMADI" in GZ.gozlem_yok_blogu("x") and "Belirsiz" in GZ.gozlem_yok_blogu("x"))
chk("rapor bloğu çelişkiyi Açık Sorular'a değil `[K: ❓ Belirsiz]`'e yönlendirir (analiz çağrısı soru üretmez)",
    "Açık Sorular'a yaz" not in b and "❓ Belirsiz" in b)
chk("rapor_soru_blogu: soru aşamasına kısa özet (≤~4k) / rapor yoksa boş", GZ.rapor_soru_blogu(r).startswith("### CANLI GÖZLEM RAPORU (özet")
    and "POST /bff/sports" in GZ.rapor_soru_blogu(r) and GZ.rapor_soru_blogu(None) == "" and len(GZ.rapor_soru_blogu({"md": "x" * 9000})) < 4400)

print("3) gorev_analiz_et — analiz çağrısı tarayıcısız")
from skills import jira_gorevleri as JG  # noqa: E402
JG.referans_dosyalari_hazirla = lambda *a, **k: []
JG.load_context_filter = lambda *a, **k: {}
JG._gorev_acik_sorular_uret = lambda *a, **k: ""
import skills.ornek_havuzu as OH  # noqa: E402
OH.ornek_bloklari = lambda *a, **k: []
JG.canli_uygulama_baglami_hazirla = lambda *a, **k: CANLI
cag: list = []


def _api(s, m, **k):
    cag.append({"kw": k, "metin": "\n".join(p.get("text", "") for p in m[0]["content"] if isinstance(p, dict))})
    return "<teknik_analiz>## 1. Amaç\nx\n</teknik_analiz>"


JG._api_cagri = _api
gz_cag: list = []
GZ.rapor_al = (lambda canli, kapsam, gorev_ozet="", yeniden=True, max_turns=None, _ai=None:
               (gz_cag.append({"kapsam": kapsam, "yeniden": yeniden}) or {"ok": True, "md": "## Aksiyonlar\n- POST /bff/x `[K: Network:POST /bff/x → 201]`", "ts": time.time()}))
G = {"key": "MBS-1", "summary": "s", "description": "d" * 50, "issuetype": "Görev"}
JG.gorev_analiz_et(G)
chk("gözlem fazı çağrıldı (gorev, yeniden=True); analiz çağrısında kapsam YOK + rapor bloğu", gz_cag == [{"kapsam": "gorev", "yeniden": True}]
    and cag[-1]["kw"].get("canli_uygulama_kapsami") is None and "CANLI UYGULAMA GÖZLEM RAPORU" in cag[-1]["metin"]
    and "MCP/CHROME GÖREVİ" not in cag[-1]["metin"], (gz_cag, cag[-1]["kw"]))
gz_cag.clear()
JG.gorev_analiz_et(G, cevaplar="Q-T-001: evet")
chk("cevap turu → yeniden=False (taze rapor yeniden kullanılır)", gz_cag == [{"kapsam": "gorev", "yeniden": False}])
gz_cag.clear()
GZ.rapor_al = lambda *a, **k: (gz_cag.append(1) or {"ok": False, "md": "", "neden": "tarayıcı yok"})
JG.gorev_analiz_et(G)
chk("gözlem başarısız → analiz gözlemsiz, 'YAPILAMADI' bloğu, kapsam yok", "GÖZLEMİ YAPILAMADI" in cag[-1]["metin"] and cag[-1]["kw"].get("canli_uygulama_kapsami") is None)
GZ.rapor_al = lambda *a, **k: {"ok": False, "md": "## Ekran\n- uydurma olabilir", "neden": "araç çalışmadı", "ts": time.time()}
JG.gorev_analiz_et(G)
chk("ok=False ama md DOLU rapor gerçek veri diye ENJEKTE EDİLMEZ (YAPILAMADI bloğu)", "GÖZLEMİ YAPILAMADI" in cag[-1]["metin"]
    and "uydurma olabilir" not in cag[-1]["metin"])
gz_cag.clear()
GZ.rapor_al = (lambda canli, kapsam, gorev_ozet="", yeniden=True, max_turns=None, _ai=None:
               (gz_cag.append({"kapsam": kapsam}) or {"ok": True, "md": "## A `[K: Canlı UI:/x]`", "ts": time.time()}))
JG.gorev_analiz_et(G, canli_baglam_override=CANLI, canli_kapsam="gorev")
chk("canli_kapsam açıkça verilince override'da bile o kapsam kullanılır (köprü: URL kaynağına göre)", gz_cag == [{"kapsam": "gorev"}])
gz_cag.clear()
JG.gorev_analiz_et(G, canli_baglam_override=CANLI)
chk("canli_kapsam verilmezse eski davranış (override → 'surec')", gz_cag == [{"kapsam": "surec"}])
gz_cag.clear()
GZ.rapor_al = lambda *a, **k: (gz_cag.append(1) or {"ok": True, "md": "## Aksiyonlar\n- x", "ts": time.time()})
soru_cag: list = []
JG._gorev_acik_sorular_uret = lambda teknik, gorev, **k: (soru_cag.append(teknik) or "")
cag.clear()
JG.gorev_fe_be_analiz(G)
chk("FE+BE ayrı → TEK gözlem, iki analiz (ikisinde de rapor)", len(gz_cag) == 1 and all("GÖZLEM RAPORU" in c["metin"] for c in cag[-2:]))
chk("FE+BE ayrı → açık soru aşaması İKİ katman üzerinden TEK kez (iki kez değil)", len(soru_cag) == 1 and "Katman analizi 2" in soru_cag[0])
JG._gorev_acik_sorular_uret = lambda *a, **k: ""
# FE girdisi: BE sözleşmesi öne alınır (baştan 4000 kırpmada sondaki sözleşme kaybolmasın)
BE_MD = "## 📋 Yönetici Özeti\n- x\n\n---\n\n<!-- RAG: 1 -->\n\n## 1. Amaç\n" + ("a" * 5000) + "\n\n## 7. Bağımlılık ve Arayüz (FE↔BE)\n- GET /bff/x → {id,name}\n"
fe_in = JG._fe_icin_be_sozlesme(BE_MD)
chk("_fe_icin_be_sozlesme: sözleşme bölümü ÖNDE, özet/RAG yok, ≤6k", fe_in.startswith("### BE SÖZLEŞMESİ") and "GET /bff/x" in fe_in[:300]
    and "Yönetici Özeti" not in fe_in and "RAG:" not in fe_in and len(fe_in) <= 6100, fe_in[:120])
chk("_fe_icin_be_sozlesme: sözleşme başlığı yoksa SON 4k (sözleşme genelde sonda)", JG._fe_icin_be_sozlesme("## 1. Amaç\n" + "b" * 7000 + "\nSON").endswith("SON"))
JG.canli_uygulama_baglami_hazirla = lambda *a, **k: ""
gz_cag.clear()
JG.gorev_analiz_et(G)
chk("canlı hedef yoksa gözlem fazı hiç çağrılmaz", gz_cag == [])

print("4) süreç/teknik motorları")
for mod in ("surec_analizi", "teknik_analiz"):
    src = Path(JG.__file__).parent.joinpath(f"{mod}.py").read_text(encoding="utf-8")
    chk(f"{mod}: gözlem fazı + analiz çağrısında canli_uygulama_kapsami yok", "_gz.rapor_al(canli_baglam, \"surec\"" in src
        and "canli_uygulama_kapsami=(\"surec\" if canli_baglam else None)" not in src and "asama_ayarla(" in src)

print("5) Faz 0 ölçüm + tur tavanı")
B.CAGRI_LOG = tmp / "cagri.jsonl"
B._claude_yolu_bul = lambda: "/usr/bin/true"
B._cli_env_hazirla = lambda y: dict(os.environ)
B._cli_durum_yaz = lambda *a, **k: None
B._token_ekle = lambda **k: None
B.GOZLEM_DURUM_DOSYA = tmp / "g.json"
B._live_app_cli_argumanlari = lambda kapsam=None: (["--mcp-config", "x"] if kapsam else [])
B._slot_birak = lambda n=None: None
cmds: list = []
yanitlar: list = []


def sahte_cli(cmd, prompt, env, timeout=0):
    cmds.append((list(cmd), prompt))
    return subprocess.CompletedProcess(cmd, 0, json.dumps(yanitlar.pop(0)), "")


B._cli_calistir = sahte_cli
MSJ = [{"role": "user", "content": [{"type": "text", "text": "gözle"}]}]
B.asama_ayarla("test:asama")
cmds.clear()
yanitlar[:] = [{"result": "## R", "num_turns": 9, "usage": {"input_tokens": 10, "output_tokens": 20, "cache_creation_input_tokens": 30, "cache_read_input_tokens": 400}}]
B._api_cagri_cli("s", MSJ, canli_uygulama_kapsami="gorev", max_turns=25)
chk("canlı çağrıda --max-turns 25", "--max-turns" in cmds[0][0] and cmds[0][0][cmds[0][0].index("--max-turns") + 1] == "25")
chk("canlı çağrıda İLK denemede yerleşik araçlar KAPALI (--tools ''; ~27k/tur tasarruf), slash kapalı, boş MCP config YOK (Playwright strict)",
    "--tools" in cmds[0][0] and cmds[0][0][cmds[0][0].index("--tools") + 1] == "" and "--disable-slash-commands" in cmds[0][0]
    and str(B.MCP_BOS_CONFIG) not in cmds[0][0])
os.environ["LIVE_APP_YERLESIK_ARACLAR"] = "true"
cmds.clear()
yanitlar[:] = [{"result": "## R", "num_turns": 9}]
B._api_cagri_cli("s", MSJ, canli_uygulama_kapsami="gorev")
chk("LIVE_APP_YERLESIK_ARACLAR=true → canlıda araçlar açık (eski davranış)", "--tools" not in cmds[0][0])
os.environ.pop("LIVE_APP_YERLESIK_ARACLAR", None)
cmds.clear()
yanitlar[:] = [{"result": "x", "num_turns": 1}]
B._api_cagri_cli("s", MSJ)
chk("gözlemsiz çağrıda --max-turns yok", "--max-turns" not in cmds[0][0])
chk("YALIN CLI: yerleşik araçlar + slash kapalı; gözlemsizde boş strict MCP", "--tools" in cmds[0][0] and cmds[0][0][cmds[0][0].index("--tools") + 1] == ""
    and "--disable-slash-commands" in cmds[0][0] and "--strict-mcp-config" in cmds[0][0] and str(B.MCP_BOS_CONFIG) in cmds[0][0] and B.MCP_BOS_CONFIG.exists())
os.environ["CLI_YALIN"] = "false"
cmds.clear()
yanitlar[:] = [{"result": "x", "num_turns": 1}]
B._api_cagri_cli("s", MSJ)
chk("CLI_YALIN=false → eski davranış", "--tools" not in cmds[0][0] and "--strict-mcp-config" not in cmds[0][0])
os.environ.pop("CLI_YALIN", None)
os.environ["LIVE_APP_MAX_TUR"] = "33"
cmds.clear()
yanitlar[:] = [{"result": "x", "num_turns": 5}]
B._api_cagri_cli("s", MSJ, canli_uygulama_kapsami="gorev")
chk("varsayılan tavan env'den (33)", cmds[0][0][cmds[0][0].index("--max-turns") + 1] == "33")
os.environ.pop("LIVE_APP_MAX_TUR", None)
cmds.clear()
yanitlar[:] = [{"subtype": "error_max_turns", "is_error": True, "session_id": "sid-1", "num_turns": 40},
                            {"result": "<gozlem_raporu>tamam</gozlem_raporu>", "num_turns": 2, "usage": {"input_tokens": 1}}]
r = B._api_cagri_cli("s", MSJ, canli_uygulama_kapsami="gorev")
chk("tavana takıldı → --resume sid ile araçsız tamamlatma, sonuç ikinci çağrıdan", len(cmds) == 2 and "--resume" in cmds[1][0]
    and "sid-1" in cmds[1][0] and cmds[1][0][cmds[1][0].index("--max-turns") + 1] == "3" and "ARAÇ KULLANMA" in cmds[1][1] and "tamam" in r, cmds[1][0])
satirlar = [json.loads(sat) for sat in B.CAGRI_LOG.read_text(encoding="utf-8").splitlines()]
chk("tavan koşusu + tamamlatma kullanımı BİRİKİMLİ kaydedildi (tur 40+2=42, girdi 1) ve araçsız tekrar TETİKLENMEDİ (2 çağrı)",
    satirlar[-1]["tur"] == 42 and satirlar[-1]["girdi"] == 1 and len(cmds) == 2, satirlar[-1])
# tur_devam: tavana takılınca bütçe yenilenip AYNI oturum sürdürülür (kabul kontrolü / BFF), sonra tamamlatma
cmds.clear()
yanitlar[:] = [{"subtype": "error_max_turns", "is_error": True, "session_id": "sid-2", "num_turns": 40, "usage": {"cache_read_input_tokens": 1000}},
               {"subtype": "error_max_turns", "is_error": True, "session_id": "sid-2", "num_turns": 40, "usage": {"cache_read_input_tokens": 2000}},
               {"result": "<kabul_sonuc>{}</kabul_sonuc>", "num_turns": 3, "usage": {"cache_read_input_tokens": 50}}]
r = B._api_cagri_cli("s", MSJ, canli_uygulama_kapsami="gorev", max_turns=60, tur_devam=2)
chk("tur_devam=2: iki devam --resume + aynı tavan (60) + 'bütçen YENİLENDİ' promptu; 2. devam bitirdi → tamamlatma GEREKMEDİ; 3 çağrı, tekrar yok",
    len(cmds) == 3 and "--resume" in cmds[1][0] and cmds[1][0][cmds[1][0].index("--max-turns") + 1] == "60"
    and "YENİLENDİ" in cmds[1][1] and "YENİLENDİ" in cmds[2][1] and "--resume" in cmds[2][0] and "kabul_sonuc" in r, [c[0][-3:] for c in cmds])
satirlar = [json.loads(sat) for sat in B.CAGRI_LOG.read_text(encoding="utf-8").splitlines()]
chk("devam koşuları birikimli: tur 83, cache_oku 3050, max_tur_takildi", satirlar[-1]["tur"] == 83 and satirlar[-1]["cache_oku"] == 3050 and satirlar[-1]["max_tur_takildi"] is True, satirlar[-1])
cmds.clear()
yanitlar[:] = [{"subtype": "error_max_turns", "is_error": True, "session_id": "sid-3", "num_turns": 40},
               {"result": "<gozlem_raporu>t</gozlem_raporu>", "num_turns": 2}]
B._api_cagri_cli("s", MSJ, canli_uygulama_kapsami="gorev")
chk("tur_devam verilmezse (gözlem fazı) devam YOK — doğrudan tamamlatma (2 çağrı)", len(cmds) == 2 and "ARAÇ KULLANMA" in cmds[1][1])
satirlar = [json.loads(sat) for sat in B.CAGRI_LOG.read_text(encoding="utf-8").splitlines()]
cmds.clear()
B.time.sleep = lambda s: None
yanitlar[:] = [{"result": "tool_use: browser_navigate", "num_turns": 1}, {"result": "## R", "num_turns": 6}]
B._api_cagri_cli("s", MSJ, canli_uygulama_kapsami="gorev")
chk("araçsız ilk tur → tekrar; ilk denemede --tools '' VAR, tekrar denemesinde YOK (yerleşik araçlar açık)",
    len(cmds) == 2 and "--tools" in cmds[0][0] and "--tools" not in cmds[1][0], [c[0] for c in cmds])
satirlar = [json.loads(sat) for sat in B.CAGRI_LOG.read_text(encoding="utf-8").splitlines()]
chk("cagri.jsonl: aşama/model/canlı/tur/token/max_tur_takildi", satirlar[0]["asama"] == "test:asama" and satirlar[0]["canli"] is True
    and satirlar[0]["tur"] == 9 and satirlar[0]["cache_oku"] == 400 and any(r["max_tur_takildi"] for r in satirlar), satirlar[0])
oz = B.cagri_ozeti(gun=1)
chk("cagri_ozeti: toplam + aşama satırı", oz["toplam"]["cagri"] == len(satirlar) and any(a["asama"] == "test:asama" and a["cache_oku"] >= 400 for a in oz["asamalar"]))
# Tamamlatma koşusunda tarayıcı araçları FİİLEN kapalı (--disallowedTools) + yine tavana takılırsa kısmi çıktı kurtarılır
cmds.clear()
yanitlar[:] = [{"subtype": "error_max_turns", "is_error": True, "session_id": "sid-4", "num_turns": 40},
               {"subtype": "error_max_turns", "is_error": True, "session_id": "sid-4", "num_turns": 3, "result": "## Kısmi rapor"}]
r = B._api_cagri_cli("s", MSJ, canli_uygulama_kapsami="gorev")
chk("tamamlatma: --disallowedTools playwright araçları; ikinci tavan → kısmi 'result' kurtarılır (hata değil)",
    "--disallowedTools" in cmds[1][0] and "mcp__playwright__browser_navigate" in cmds[1][0][cmds[1][0].index("--disallowedTools") + 1]
    and r == "## Kısmi rapor" and len(cmds) == 2, (cmds[1][0], r))
# Başarısız bitişte önceki koşuların kullanımı yine kaydedilir (basarisiz=True) — TEK satır (çift sayım yok)
onceki_n = len(B.CAGRI_LOG.read_text(encoding="utf-8").splitlines())
cmds.clear()
yanitlar[:] = [{"subtype": "error_max_turns", "is_error": True, "session_id": "sid-5", "num_turns": 40, "usage": {"input_tokens": 7}},
               {"is_error": True, "result": "patladı", "num_turns": 1}]
try:
    B._api_cagri_cli("s", MSJ, canli_uygulama_kapsami="gorev")
    chk("son koşu hata → RuntimeError", False)
except RuntimeError:
    satirlar = [json.loads(sat) for sat in B.CAGRI_LOG.read_text(encoding="utf-8").splitlines()]
    chk("son koşu hata verse de tavan koşusunun kullanımı kaydedildi (basarisiz, tur 41, girdi 7) — tek satır",
        len(satirlar) == onceki_n + 1 and satirlar[-1]["basarisiz"] is True and satirlar[-1]["tur"] == 41 and satirlar[-1]["girdi"] == 7, satirlar[-1])
# Toplam süre bütçesi: her alt-süreç timeout'u kalan bütçeyle sınırlı
os.environ["LIVE_APP_TOPLAM_SURE"] = "200"
os.environ["LIVE_APP_CLI_TIMEOUT"] = "720"
zamanlar: list = []


def olcen_cli(cmd, prompt, env, timeout=0):
    zamanlar.append(timeout)
    return sahte_cli(cmd, prompt, env, timeout=timeout)


B._cli_calistir = olcen_cli
yanitlar[:] = [{"subtype": "error_max_turns", "is_error": True, "session_id": "sid-6", "num_turns": 40}, {"result": "ok", "num_turns": 2}]
B._api_cagri_cli("s", MSJ, canli_uygulama_kapsami="gorev")
chk("LIVE_APP_TOPLAM_SURE=200: ilk koşu ≤200 (720 değil), tamamlatma 60..200", len(zamanlar) == 2 and zamanlar[0] <= 200 and 60 <= zamanlar[1] <= 200, zamanlar)
B._cli_calistir = sahte_cli
os.environ.pop("LIVE_APP_TOPLAM_SURE", None)
os.environ.pop("LIVE_APP_CLI_TIMEOUT", None)
# RAG corpus: live-app altındaki ÜRETİLMİŞ dosyalar (gözlem raporları, BFF ham/meta) referans sayılmaz
la = tmp / "live-app"
(la / "gozlem").mkdir(parents=True)
(la / "bff").mkdir()
for ad in ("gozlem/abc.md", "gozlem/abc.json", "bff/k.md", "bff/k.json", "bff/k.ham.txt", "ekran.md"):
    (la / ad).write_text("x", encoding="utf-8")
_eski_dirs = (B.CONF_DIR, B.JIRA_REF_DIR, B.SERVIS_DIR, B.LIVE_APP_DIR)
B.CONF_DIR = B.JIRA_REF_DIR = B.SERVIS_DIR = tmp / "yok"
B.LIVE_APP_DIR = la
adlar = sorted(p.relative_to(la).as_posix() for p in B.referans_dosyalari_hazirla({}))
chk("RAG corpus: live-app/gozlem/** + bff/*.json + bff/*.ham.txt HARİÇ; bff/*.md ve diğer gözlem dosyaları dahil", adlar == ["bff/k.md", "ekran.md"], adlar)
B.CONF_DIR, B.JIRA_REF_DIR, B.SERVIS_DIR, B.LIVE_APP_DIR = _eski_dirs
src_b = Path(B.__file__).read_text(encoding="utf-8")
chk("snapshot diyeti kuralı canlı promptta", "TUR DİYETİ" in src_b and "ikinci kez ALMA" in src_b)
import app as A  # noqa: E402
src_app = Path(A.__file__).read_text(encoding="utf-8")
ui = Path(A.__file__).parent.joinpath("templates/index.html").read_text(encoding="utf-8")
chk("uç + Kullanım Raporu paneli", '"/api/usage/cagri-ozet"' in src_app and "kuCagriOzetYukle" in ui and "Aşama bazlı tüketim" in ui)
for mod, et in (("soru_cozumleme", "soru:cozum"), ("bff_kesif", '"bff"'), ("canli_giris", '"giris"'), ("kabul_kontrolu", "kabul:dogrula")):
    chk(f"aşama etiketi: {mod}", et in Path(JG.__file__).parent.joinpath(f"{mod}.py").read_text(encoding="utf-8"))

print()
if _hata:
    print(f"GÖZLEM FAZI TESTLERİ BAŞARISIZ ({_hata} hata)")
    sys.exit(1)
print("GÖZLEM FAZI TESTLERİ GEÇTİ")
