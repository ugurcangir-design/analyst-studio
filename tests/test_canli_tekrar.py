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
yanitlar[:] = [{"result": "a", "num_turns": 1}, {"result": "b", "num_turns": 1}]
r = B._api_cagri_cli("sistem", MSJ, canli_uygulama_kapsami="gorev")
chk("en fazla 2 çağrı; durum yapildi=False + neden 'tekrar denendi'", len(cagrilar) == 2 and r == "b"
    and not durum()["yapildi"] and "tekrar denendi" in durum()["neden"], durum())

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

print()
if _hata:
    print(f"CANLI TEKRAR TESTLERİ BAŞARISIZ ({_hata} hata)")
    sys.exit(1)
print("CANLI TEKRAR TESTLERİ GEÇTİ")
