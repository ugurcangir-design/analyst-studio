"""Canlı gözlem PROFİL HAVUZU — paralel akışlar aynı Chrome profilini paylaşmaz (offline, 0 token).

Kapsam:
  1. _slot_al: ardışık çağrılar FARKLI slot verir; _slot_birak sonrası slot yeniden alınır; kilit dosyası pid taşır
  2. bayat kilit (ölü pid) devralınır; başka canlı süreç tutuyorsa atlanır; havuz doluyken bekleme süresi dolunca None
  3. MCP config slot başına ayrı dosya + o slotun --user-data-dir'i; _live_app_cli_argumanlari slot alır, _api_cagri_cli bırakır
  4. oturum kopyalama: ana profil Cookies/Local Storage slota kopyalanır, damga ile tekrar kopyalanmaz, ana yenilenince yeniden
  5. pgrep deseni tam eşleşme (`.live-app-profile` ≠ `.live-app-profiles/slot-1`) · slot_durumu · gitignore · status alanı
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
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
B.LIVE_APP_PROFILE_HAVUZ = tmp / "havuz"
B.LIVE_APP_PROFILE_DIR = tmp / "ana"
B.LIVE_APP_MCP_CONFIG = tmp / "mcp.json"
os.environ["LIVE_APP_PARALEL"] = "3"
B._profil_sureclerini_kapat = lambda profil: 0   # testte süreç öldürme yok
B._SLOT_SAHIPLI.clear()

print("1) al / bırak")
s1 = B._slot_al(bekle_sn=0)
s2 = B._slot_al(bekle_sn=0)
chk("ardışık alımlar farklı slot", s1 and s2 and s1[0] != s2[0] and s1[1] != s2[1], (s1, s2))
chk("kilit dosyası pid taşır", (B.LIVE_APP_PROFILE_HAVUZ / f"slot-{s1[0]}.lock").read_text().strip() == str(os.getpid()))
chk("slot_durumu: 2 dolu / 1 boş", B.slot_durumu() == {"toplam": 3, "dolu": [s1[0], s2[0]], "bos": 1}, B.slot_durumu())
B._slot_birak(s1[0])
s3 = B._slot_al(bekle_sn=0)
chk("bırakılan slot yeniden alınır", s3 and s3[0] == s1[0])
B._slot_birak(s2[0])
B._slot_birak(s3[0])
chk("hepsi bırakıldı", B.slot_durumu()["bos"] == 3 and not B._SLOT_SAHIPLI)

print("2) bayat kilit / dolu havuz")
(B.LIVE_APP_PROFILE_HAVUZ / "slot-1.lock").write_text("999999")        # ölü pid
s = B._slot_al(bekle_sn=0)
chk("ölü pid'li kilit devralınır (slot-1)", s and s[0] == 1)
B._slot_birak(1)
canli = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"])
try:
    (B.LIVE_APP_PROFILE_HAVUZ / "slot-1.lock").write_text(str(canli.pid))
    s = B._slot_al(bekle_sn=0)
    chk("başka canlı süreç tutuyorsa atlanır (slot-2)", s and s[0] == 2, s)
    s_ = B._slot_al(bekle_sn=0)
    chk("3. slot alınır", s_ and s_[0] == 3)
    t0 = time.time()
    chk("havuz dolu + bekleme 0 → None (hemen)", B._slot_al(bekle_sn=0) is None and time.time() - t0 < 3)
    # bekleme: başka thread 1 sn sonra bırakır → bekleyen alır
    threading.Timer(1.0, lambda: B._slot_birak(2)).start()
    t0 = time.time()
    s4 = B._slot_al(bekle_sn=10)
    chk("bekleyen, boşalan slotu alır", s4 and s4[0] == 2 and 0.5 < time.time() - t0 < 9, s4)
    B._slot_birak(2)
    B._slot_birak(3)
finally:
    canli.kill()
    try:
        (B.LIVE_APP_PROFILE_HAVUZ / "slot-1.lock").unlink()
    except Exception:
        pass

print("3) MCP config + argümanlar")
B._npx_yolu_bul = lambda: "/usr/bin/npx"
B.gorev_live_app_urls = lambda: ["https://uat-ornek.local/app"]
args = B._live_app_cli_argumanlari(kapsam="gorev")
cfg = Path(args[args.index("--mcp-config") + 1])
d = json.loads(cfg.read_text())
n = getattr(B._SLOT_TL, "slot", None)
chk("config slot dosyası + o slotun profili", cfg.name == f"mcp.slot-{n}.json" and d["mcpServers"]["playwright"]["args"][-1].endswith(f"slot-{n}"), (cfg, n))
chk("slot bu thread'de tutuluyor", n in B._SLOT_SAHIPLI)
# _api_cagri_cli finally → bırakır (CLI mock)
B._claude_yolu_bul = lambda: "/usr/bin/true"
B._cli_env_hazirla = lambda y: dict(os.environ)
B._cli_durum_yaz = lambda *a, **k: None
B._token_ekle = lambda **k: None
B.GOZLEM_DURUM_DOSYA = tmp / "g.json"
B._cli_calistir = lambda cmd, p, e, timeout=0: subprocess.CompletedProcess(cmd, 0, json.dumps({"result": "ok", "num_turns": 5}), "")
B._slot_birak(n)
B._api_cagri_cli("s", [{"role": "user", "content": [{"type": "text", "text": "x"}]}], canli_uygulama_kapsami="gorev")
chk("_api_cagri_cli sonrası slot serbest", not B._SLOT_SAHIPLI and B.slot_durumu()["bos"] == 3, B.slot_durumu())
B._cli_calistir = lambda cmd, p, e, timeout=0: (_ for _ in ()).throw(RuntimeError("patladı"))
try:
    B._api_cagri_cli("s", [{"role": "user", "content": [{"type": "text", "text": "x"}]}], canli_uygulama_kapsami="gorev")
except RuntimeError:
    pass
chk("CLI hata fırlatsa da slot serbest (finally)", not B._SLOT_SAHIPLI and B.slot_durumu()["bos"] == 3)
B._slot_al_orj = B._slot_al
B._slot_al = lambda bekle_sn=None: None
try:
    B._live_app_cli_argumanlari(kapsam="gorev")
    chk("slot yoksa net hata", False)
except RuntimeError as e:
    chk("slot yoksa net hata", "meşgul" in str(e))
B._slot_al = B._slot_al_orj

print("4) oturum kopyalama")
ana = B.LIVE_APP_PROFILE_DIR / "Default"
(ana / "Local Storage" / "leveldb").mkdir(parents=True)
(ana / "Cookies").write_bytes(b"cookie-v1")
(ana / "Local Storage" / "leveldb" / "000.log").write_bytes(b"ls")
slot = B.LIVE_APP_PROFILE_HAVUZ / "slot-9"
B._slot_oturum_kopyala(slot)
chk("Cookies + Local Storage slota kopyalandı", (slot / "Default/Cookies").read_bytes() == b"cookie-v1" and (slot / "Default/Local Storage/leveldb/000.log").exists())
(slot / "Default/Cookies").write_bytes(b"slot-degisti")
B._slot_oturum_kopyala(slot)
chk("ana yenilenmediyse tekrar kopyalanmaz (damga)", (slot / "Default/Cookies").read_bytes() == b"slot-degisti")
time.sleep(0.05)
(ana / "Cookies").write_bytes(b"cookie-v2")
os.utime(ana / "Cookies", None)
B._slot_oturum_kopyala(slot)
chk("ana profil yenilenince (giriş) slota yeniden kopyalanır", (slot / "Default/Cookies").read_bytes() == b"cookie-v2")

print("5) desen / gitignore / status")
import re  # noqa: E402
kmt = B._pgrep_komutu(B.LIVE_APP_PROFILE_DIR)
chk("pgrep komutu: '--' ayracı (BSD pgrep deseni seçenek sanmasın) + [[:space:]] (macOS ERE'de \\s yok)",
    kmt[:3] == ["pgrep", "-f", "--"] and kmt[3].startswith("--user-data-dir=") and "[[:space:]]" in kmt[3] and "\\s" not in kmt[3], kmt)
desen = kmt[3].replace("[[:space:]]", r"\s")     # Python re için POSIX sınıfı çevrilir
chk("pgrep deseni: ana profil eşleşir, slot dizini EŞLEŞMEZ", re.search(desen, f"chrome --user-data-dir={B.LIVE_APP_PROFILE_DIR} --x")
    and not re.search(desen, f"chrome --user-data-dir={B.LIVE_APP_PROFILE_DIR}s/slot-1 --x"))
gi = Path(B.__file__).parent.parent.joinpath(".gitignore").read_text(encoding="utf-8")
chk("gitignore: havuz + slot config'leri", ".live-app-profiles/" in gi and ".mcp.live-app.*.json" in gi)
src = Path(B.__file__).parent.parent.joinpath("app.py").read_text(encoding="utf-8")
chk("status: slotlar alanı", '"slotlar": _slot_durumu_guvenli()' in src)
src_b = Path(B.__file__).read_text(encoding="utf-8")
chk("analiz yolu ana profili KAPATMAZ (kilit temizleme yalnız giriş penceresinde)", "live_app_kilidi_temizle()           # kapatılmamış giriş penceresi" not in src_b)

print("6) oturum geri yazımı (agent girişi kalıcı)")
B._base_profil_kullanimda = lambda: False
slotA = B.LIVE_APP_PROFILE_HAVUZ / "slot-7"
(slotA / "Default" / "Local Storage" / "leveldb").mkdir(parents=True, exist_ok=True)
time.sleep(0.05)
(slotA / "Default/Cookies").write_bytes(b"agent-session")
(slotA / "Default/Local Storage/leveldb/001.log").write_bytes(b"jwt")
_ileri = time.time() + 30          # gerçekte agent girişi dakikalar sonra olur; 1 sn tolerans (copy2 mtime eşitliği) aşılsın
os.utime(slotA / "Default/Cookies", (_ileri, _ileri))
chk("slot daha yeni → ana profile geri yazıldı + işaret", B._slot_oturum_geri_yaz(slotA, 7) is True
    and (B.LIVE_APP_PROFILE_DIR / "Default/Cookies").read_bytes() == b"agent-session"
    and (B.LIVE_APP_PROFILE_DIR / "Default/Local Storage/leveldb/001.log").exists()
    and json.loads((B.LIVE_APP_PROFILE_DIR / ".oturum-son-giris").read_text())["slot"] == 7)
od = B.oturum_durumu()
chk("oturum_durumu: var + kaynak agent + yaş", od["var"] and od["kaynak"] == "agent" and od["yas_dk"] == 0, od)
chk("ikinci çağrı: slot yeni değil → yazmaz", B._slot_oturum_geri_yaz(slotA, 7) is False)
slotB = B.LIVE_APP_PROFILE_HAVUZ / "slot-8"
B._slot_oturum_kopyala(slotB)
chk("başka slot alımda agent oturumunu devralır", (slotB / "Default/Cookies").read_bytes() == b"agent-session")
time.sleep(0.05)
(slotA / "Default/Cookies").write_bytes(b"newer")
os.utime(slotA / "Default/Cookies", (_ileri + 60, _ileri + 60))
B._base_profil_kullanimda = lambda: True
chk("ana profil başlı Chrome'da açıkken geri yazım atlanır", B._slot_oturum_geri_yaz(slotA, 7) is False
    and (B.LIVE_APP_PROFILE_DIR / "Default/Cookies").read_bytes() == b"agent-session")
B._base_profil_kullanimda = lambda: False
chk("_slot_birak geri yazımı tetikler", (B._slot_birak(7) or True) and (B.LIVE_APP_PROFILE_DIR / "Default/Cookies").read_bytes() == b"newer")
src_p = Path(B.__file__).read_text(encoding="utf-8")
chk("prompt: oturum açıksa giriş atla + logout yok", "Oturum ZATEN AÇIKSA" in src_p and "asla çıkış (logout) yapma" in src_p)
src_app = Path(B.__file__).parent.parent.joinpath("app.py").read_text(encoding="utf-8")
chk("status: oturum alanı", '"oturum": _oturum_durumu_guvenli()' in src_app)

print("7) gerçek pgrep / atomik kilit / Preferences / slot sızıntısı / bırakırken Chrome kapatma")
hedef = tmp / "pgrep-ana"
tasiyan = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)", f"--user-data-dir={hedef}"])
try:
    time.sleep(0.4)
    r1 = subprocess.run(B._pgrep_komutu(hedef), capture_output=True, text=True, timeout=5)
    r2 = subprocess.run(B._pgrep_komutu(tmp / "pgrep-an"), capture_output=True, text=True, timeout=5)   # önek — eşleşmemeli
    chk("gerçek pgrep: profili taşıyan süreç bulunur (exit 0), önek/alt-dizin eşleşmez (exit 1, 'illegal option' exit 2 DEĞİL)",
        str(tasiyan.pid) in r1.stdout.split() and r1.returncode == 0 and r2.returncode == 1 and not r2.stdout.strip(),
        (r1.returncode, r1.stdout, r1.stderr, r2.returncode, r2.stderr))
finally:
    tasiyan.kill()
B._SLOT_SAHIPLI.clear()
for f in B.LIVE_APP_PROFILE_HAVUZ.glob("slot-*.lock"):
    f.unlink()
genc = B.LIVE_APP_PROFILE_HAVUZ / "slot-1.lock"
genc.write_text("")                                   # pid'siz ama TAZE: başka süreç tam o anda yazıyor olabilir
s = B._slot_al(bekle_sn=0)
chk("pid'siz GENÇ (<5 sn) kilit tutuluyor sayılır → slot-2", s and s[0] == 2, s)
B._slot_birak(s[0])
_eski_ts = time.time() - 30
os.utime(genc, (_eski_ts, _eski_ts))
s = B._slot_al(bekle_sn=0)
chk("pid'siz ESKİ boş kilit bayat → slot-1 devralınır, pid ATOMİK yazılı", s and s[0] == 1 and genc.read_text().strip() == str(os.getpid()))
B._slot_birak(1)
chk("geçici kilit dosyası kalmaz", not list(B.LIVE_APP_PROFILE_HAVUZ.glob(".slot-*.tmp")) and not genc.exists())
pref_slot = B.LIVE_APP_PROFILE_HAVUZ / "slot-5"
(pref_slot / "Default").mkdir(parents=True, exist_ok=True)
(pref_slot / "Default" / "Preferences").write_text("{}")
_ileri2 = time.time() + 300
os.utime(pref_slot / "Default" / "Preferences", (_ileri2, _ileri2))
chk("yalnız Preferences yeni → 'giriş yapıldı' sayılmaz (mtime 0, geri yazım YOK)",
    B._oturum_mtime(pref_slot) == 0 and B._slot_oturum_geri_yaz(pref_slot, 5) is False)
chk("flock dosyası havuzda", (B.LIVE_APP_PROFILE_HAVUZ / ".oturum.lock").exists())
_orj_kop = B._slot_oturum_kopyala
B._slot_oturum_kopyala = lambda d: (_ for _ in ()).throw(OSError("disk dolu"))
try:
    B._slot_al(bekle_sn=0)
    chk("kopyalama hatası yükselir", False)
except OSError:
    chk("kopyalama hatası yükselir", True)
B._slot_oturum_kopyala = _orj_kop
chk("alım sonrası hata → slot SIZMAZ (kilit yok, sahipli boş)", not B._SLOT_SAHIPLI and B.slot_durumu()["bos"] == 3, B.slot_durumu())
kapatilan: list = []
B._profil_sureclerini_kapat = lambda profil: kapatilan.append(profil) or 0
s = B._slot_al(bekle_sn=0)
kapatilan.clear()
B._slot_birak(s[0])
chk("_slot_birak: geri yazımdan ÖNCE slot Chrome'u kapatılır", bool(kapatilan) and kapatilan[0].name == f"slot-{s[0]}", kapatilan)
B._profil_sureclerini_kapat = lambda profil: 0

print()
if _hata:
    print(f"PROFİL HAVUZU TESTLERİ BAŞARISIZ ({_hata} hata)")
    sys.exit(1)
print("PROFİL HAVUZU TESTLERİ GEÇTİ")
