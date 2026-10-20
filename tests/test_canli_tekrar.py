"""Canlı gözlem — model araç çağırmama tespiti + otomatik tekrar (offline, 0 token, CLI MOCK).

Teşhis (2026-10-16): MCP sunucusu bağlı olduğu hâlde model büyük promptlarda tarayıcı talimatını
atlayıp tek turda araçsız yanıt üretiyordu (num_turns=1). Kapsam:
  1. canlı kapsamda prompt sonuna ZORUNLU İLK EYLEM direktifi eklenir; kapsam yokken eklenmez
  2. num_turns<=1 → sertleştirilmiş uyarıyla İKİNCİ çağrı; ikinci başarılıysa onun yanıtı + durum yapildi=True
  3. ikinci de başarısızsa durum yapildi=False + neden 'tekrar denendi'
  4. LIVE_APP_TEKRAR=false → tek çağrı, neden yazılır
  5. live_app_kilidi_temizle: pgrep yolu hata verse de fırlatmaz
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("BILDIRIM", "false")

from skills import base as B  # noqa: E402

_hata = 0


def chk(ad, kosul, ek=""):
    global _hata
    if not kosul:
        _hata += 1
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if ek and not kosul else ""))


tmp = Path(tempfile.mkdtemp())
B.GOZLEM_DURUM_DOSYA = tmp / ".gozlem-durum.json"
B._claude_yolu_bul = lambda: "/usr/bin/true"
B._cli_env_hazirla = lambda yol: dict(os.environ)
B._cli_durum_yaz = lambda *a, **k: None
B._token_ekle = lambda **k: None
B._live_app_cli_argumanlari = lambda kapsam=None: (["--mcp-config", "x", "--allowedTools", "mcp__playwright__browser_navigate"] if kapsam else [])
cagrilar: list[str] = []
yanitlar: list[dict] = []


def sahte_cli(cmd, prompt, env, timeout=0):
    cagrilar.append(prompt)
    v = yanitlar.pop(0)
    return subprocess.CompletedProcess(cmd, 0, json.dumps(v), "")


B._cli_calistir = sahte_cli
MSJ = [{"role": "user", "content": [{"type": "text", "text": "Hedef URL'yi gözle"}]}]


def durum():
    return json.loads(B.GOZLEM_DURUM_DOSYA.read_text(encoding="utf-8"))


print("1) direktif yerleşimi")
cagrilar.clear()
yanitlar[:] = [{"result": "## Rapor\nok", "num_turns": 8, "permission_denials": []}]
r = B._api_cagri_cli("sistem", MSJ, canli_uygulama_kapsami="gorev")
chk("canlı kapsam: prompt SONU zorunlu ilk eylem direktifi", cagrilar[0].rstrip().endswith(B._LIVE_APP_ZORUNLU_ILK_ADIM.rstrip())
    and "browser_navigate" in B._LIVE_APP_ZORUNLU_ILK_ADIM)
chk("başarılı gözlem → tek çağrı, durum yapildi + neden boş", len(cagrilar) == 1 and durum()["yapildi"] and durum()["neden"] == "" and r == "## Rapor\nok")
cagrilar.clear()
yanitlar[:] = [{"result": "x", "num_turns": 1}]
B._api_cagri_cli("sistem", MSJ)
chk("kapsam yokken direktif eklenmez", "ZORUNLU İLK EYLEM" not in cagrilar[0])

print("2) araç çağırmama → otomatik tekrar")
cagrilar.clear()
yanitlar[:] = [{"result": "araçsız yanıt", "num_turns": 1, "permission_denials": []},
                                 {"result": "## Gözlemli rapor", "num_turns": 11, "permission_denials": []}]
r = B._api_cagri_cli("sistem", MSJ, canli_uygulama_kapsami="surec")
chk("iki çağrı; ikinci prompt sertleştirilmiş uyarı taşır", len(cagrilar) == 2 and "ÖNCEKİ DENEMEDE" in cagrilar[1] and "ÖNCEKİ DENEMEDE" not in cagrilar[0])
chk("ikinci yanıt döner + durum yapildi=True (11 tur)", r == "## Gözlemli rapor" and durum()["yapildi"] and durum()["num_turns"] == 11)

print("3) ikinci de başarısız")
cagrilar.clear()
yanitlar[:] = [{"result": "a", "num_turns": 1}, {"result": "a2", "num_turns": 1}, {"result": "b", "num_turns": 1}]
B.time.sleep = lambda s: None   # test hızlı
r = B._api_cagri_cli("sistem", MSJ, canli_uygulama_kapsami="gorev")
chk("en fazla 1+2 çağrı; durum yapildi=False + neden '2 tekrar denendi'", len(cagrilar) == 3 and r == "b"
    and not durum()["yapildi"] and "2 tekrar denendi" in durum()["neden"], (len(cagrilar), durum()))

print("4) LIVE_APP_TEKRAR=false")
os.environ["LIVE_APP_TEKRAR"] = "false"
cagrilar.clear()
yanitlar[:] = [{"result": "a", "num_turns": 1}, {"result": "OLMAMALI", "num_turns": 9}]
r = B._api_cagri_cli("sistem", MSJ, canli_uygulama_kapsami="gorev")
chk("tek çağrı + neden 'araç çağırmadı'", len(cagrilar) == 1 and r == "a" and "aracı çağırmadı" in durum()["neden"], (len(cagrilar), r, durum()))
os.environ.pop("LIVE_APP_TEKRAR", None)
cagrilar.clear()
yanitlar[:] = [{"result": "a", "num_turns": 5, "permission_denials": [{"tool_name": "mcp__playwright__browser_navigate"}]}]
B._api_cagri_cli("sistem", MSJ, canli_uygulama_kapsami="gorev")
chk("izinli araç reddi → tekrar YOK, neden 'reddedildi'", len(cagrilar) == 1 and "reddedildi" in durum()["neden"])
cagrilar.clear()
yanitlar[:] = [{"result": "tool_use: browser_navigate\nLet me start.", "num_turns": 1}, {"result": "## ok", "num_turns": 7}]
r = B._api_cagri_cli("sistem", MSJ, canli_uygulama_kapsami="gorev")
chk("pseudo araç metni → tekrar + ikinci başarılı", r == "## ok" and len(cagrilar) == 2 and durum()["yapildi"])

print("5) kilit temizliği dayanıklı")
B.LIVE_APP_PROFILE_DIR = tmp / "profil"
B.LIVE_APP_PROFILE_DIR.mkdir()
_orj = B.subprocess.run
B.subprocess.run = lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("pgrep yok"))
try:
    B.live_app_kilidi_temizle()
    chk("pgrep yokken fırlatmaz", True)
except Exception as e:
    chk("pgrep yokken fırlatmaz", False, str(e))
finally:
    B.subprocess.run = _orj

print("6) Durdur bayrağı / sessiz düşüş / ham çıktı / limit / roller / canlı kapsamda API fallback YOK")
cagrilar.clear()
yanitlar[:] = [{"subtype": "error_max_turns", "is_error": True, "session_id": "sid-d", "num_turns": 40},
               {"result": "OLMAMALI", "num_turns": 2}]


def durduran_cli(cmd, prompt, env, timeout=0):
    r = sahte_cli(cmd, prompt, env, timeout=timeout)
    B.cli_proc_durdur(B.threading.get_ident())   # ilk koşu biter bitmez analist Durdur'a bastı (süreç yok → False döner)
    return r


B._cli_calistir = durduran_cli
try:
    B._api_cagri_cli("sistem", MSJ, canli_uygulama_kapsami="gorev")
    chk("koşular ARASINDA Durdur → sonraki alt-süreç başlamaz (DurdurulduError)", False)
except B.DurdurulduError:
    chk("koşular ARASINDA Durdur → sonraki alt-süreç başlamaz (DurdurulduError)", len(cagrilar) == 1, len(cagrilar))
B._cli_calistir = sahte_cli
cagrilar.clear()
yanitlar[:] = [{"result": "temiz", "num_turns": 1}]
chk("taze üst-düzey çağrı Durdur bayrağını temizler", B._api_cagri_cli("sistem", MSJ) == "temiz")
# sessiz düşüş: kapsam istendi ama MCP/URL yok
B._live_app_cli_argumanlari = lambda kapsam=None: []
cagrilar.clear()
yanitlar[:] = [{"result": "gözlemsiz", "num_turns": 1}]
r = B._api_cagri_cli("sistem", MSJ, canli_uygulama_kapsami="gorev")
chk("kapsam istendi ama MCP/URL yok → analiz üretilir AMA durum yapildi=False, neden 'MCP/URL yok'",
    r == "gözlemsiz" and len(cagrilar) == 1 and not durum()["yapildi"] and durum()["neden"] == "MCP/URL yok", durum())
B._live_app_cli_argumanlari = lambda kapsam=None: (["--mcp-config", "x", "--allowedTools", "mcp__playwright__browser_navigate"] if kapsam else [])
# ham (JSON olmayan) çıktı da redaksiyondan geçer; JSON liste gövde AttributeError vermez
_orj_ctx = B.load_context_filter
B.load_context_filter = lambda: {"live_app_auth": {"password": "GizliSifre1"}}
B._cli_calistir = lambda cmd, p, e, timeout=0: subprocess.CompletedProcess(cmd, 0, "düz metin GizliSifre1 ile", "")
chk("JSON olmayan ham çıktı şifre redaksiyonundan geçer", B._api_cagri_cli("sistem", MSJ) == "düz metin «redakte» ile")
B.load_context_filter = _orj_ctx
B._cli_calistir = lambda cmd, p, e, timeout=0: subprocess.CompletedProcess(cmd, 0, json.dumps([1, 2]), "")
chk("JSON liste gövde → AttributeError yok, ham döner", B._api_cagri_cli("sistem", MSJ) == "[1, 2]")
B._cli_calistir = lambda cmd, p, e, timeout=0: subprocess.CompletedProcess(
    cmd, 0, json.dumps({"is_error": True, "api_error_status": 429, "result": "You've hit your limit · resets 3:50pm (Europe/Istanbul)"}), "")
try:
    B._api_cagri_cli("sistem", MSJ)
    chk("is_error 429 + exit 0 → CliLimitError", False)
except B.CliLimitError as e:
    chk("is_error 429 + exit 0 → CliLimitError + reset ayıklandı", e.reset == "3:50pm (Europe/Istanbul)", e.reset)
B._cli_calistir = sahte_cli
# roller: tek kullanıcı mesajı AYNEN; çok mesajda [ANALİST]/[ASİSTAN]
tek = B._mesajlari_birlestir("SYS", [{"role": "user", "content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]}])
chk("tek kullanıcı mesajı: biçim AYNEN (rol öneki yok)", tek == "SYS\n\n" + "\n\n" + "─" * 60 + "\n" + "\n\n" + "a\n\nb", repr(tek))
cok = B._mesajlari_birlestir("SYS", [{"role": "user", "content": "soru"}, {"role": "assistant", "content": "cevap"}, {"role": "user", "content": "devam"}])
chk("çok mesaj: [ANALİST]/[ASİSTAN] önekleri sırayla", "[ANALİST]:\nsoru" in cok and "[ASİSTAN]:\ncevap" in cok
    and cok.index("[ANALİST]:\nsoru") < cok.index("[ASİSTAN]:\ncevap") < cok.index("[ANALİST]:\ndevam"), cok)
# _api_cagri: canlı kapsamda önbellek NE okunur NE yazılır; CLI limiti → canlıda API fallback YOK, canlı değilse var ama cache'e yazılmaz
B._API_CACHE_DIR = tmp / "cache"
_eski_use, _eski_cli_fn, _eski_direct = B.USE_CLAUDE_CLI, B._api_cagri_cli, B._api_cagri_direct
_eski_key = os.environ.get("ANTHROPIC_API_KEY")
B.USE_CLAUDE_CLI = True
k_canli = B._api_cache_key("s2", MSJ, B.MODEL_ANALIZ, B.MAX_TOKENS_UZUN, False, "ana")
B._api_cache_yaz(k_canli, "ESKİ GÖZLEM")
B._api_cagri_cli = lambda *a, **k: "TAZE"
chk("canlı kapsam: 7 günlük önbellek OKUNMAZ (taze sonuç) ve YAZILMAZ (eski kayıt olduğu gibi)",
    B._api_cagri("s2", MSJ, canli_uygulama_kapsami="gorev") == "TAZE" and B._api_cache_oku(k_canli) == "ESKİ GÖZLEM")
chk("gözlemsiz çağrı önbelleği okur (eski davranış)", B._api_cagri("s2", MSJ) == "ESKİ GÖZLEM")
B._api_cagri_cli = lambda *a, **k: (_ for _ in ()).throw(B.CliLimitError("limit", reset="x"))
direct: list = []
B._api_cagri_direct = lambda *a, **k: direct.append(1) or "API SONUCU"
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
os.environ.pop("CLI_LIMIT_API_FALLBACK", None)
try:
    B._api_cagri("s3", MSJ, canli_uygulama_kapsami="gorev")
    chk("canlı kapsamda CLI limiti → API fallback YOK", False)
except B.CliLimitError:
    chk("canlı kapsamda CLI limiti → CliLimitError yükselir, _api_cagri_direct ÇAĞRILMAZ (tarayıcısız 'gözlem' uydurulmaz)", not direct)
k3 = B._api_cache_key("s3", MSJ, B.MODEL_ANALIZ, B.MAX_TOKENS_UZUN, False, "ana")
chk("canlı olmayan çağrıda fallback çalışır; API sonucu CLI anahtarına YAZILMAZ",
    B._api_cagri("s3", MSJ) == "API SONUCU" and direct and B._api_cache_oku(k3) is None)
B.USE_CLAUDE_CLI, B._api_cagri_cli, B._api_cagri_direct = _eski_use, _eski_cli_fn, _eski_direct
if _eski_key is None:
    os.environ.pop("ANTHROPIC_API_KEY", None)
else:
    os.environ["ANTHROPIC_API_KEY"] = _eski_key

print()
if _hata:
    print(f"CANLI TEKRAR TESTLERİ BAŞARISIZ ({_hata} hata)")
    sys.exit(1)
print("CANLI TEKRAR TESTLERİ GEÇTİ")
