"""Analiz İnceleme Arşivi — analistlerin agent'la ürettiği HER analizi (onaylanmasa da) owner görebilsin
(owner 2026-11-06: 'analistlerin agent üzerinden oluşturduğu analizleri incelemek, sorunları tespit etmek').

Yakalama: süreç/teknik analiz bitince (workflow geçişi), İnteraktif Analiz üretimi, Task analizi (FE/BE dahil).
Kayıt: `output/analiz-arsiv/<id>.json` (yerel, gitignore) + merkezi sink'e `olay='ornek'`, `tip='inceleme:<tip>'`
(Apps Script 'Ornekler' sekmesi — DEĞİŞİKLİK GEREKMEZ; few-shot havuzu `ornekleri_cek`/`ornek_bloklari` yalnız
surec/teknik tipini aldığı için bu kayıtlar eğitime KARIŞMAZ). Soru sayıları (tür bazlı) sink'in koruduğu `ozet`
alanına gömülür (`_ozet_gom`/`_ozet_coz`). İçerik `_redakte` ile sır/şifreden arındırılır, ≤45k.
Owner: Kullanım Raporu → Ölçüm & Teşhis → 'Analiz İnceleme' (uzaktan çek, aç, not). Hata → sessiz (akış bozulmaz).
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

from .base import OUTPUT_DIR

ARSIV_DIR = OUTPUT_DIR / "analiz-arsiv"
UZAK_DIR = ARSIV_DIR / "uzak"
NOT_DOSYA = ARSIV_DIR / "notlar.json"
_ICERIK_KC = 45_000
_ID = re.compile(r"^inc-[0-9a-f]{16}$")
_OZET_DESEN = re.compile(r"⟨inc\s+([^⟩]*)⟩")


def _ozet_gom(kaynak: str, s: dict) -> str:
    parca = ",".join(f"{k}={int(s.get(k) or 0)}" for k in ("is", "teknik", "dogru", "zorunlu", "toplam"))
    return f"{(kaynak or '')[:220]} ⟨inc {parca}⟩"


def _ozet_coz(ozet: str) -> tuple[str, dict]:
    m = _OZET_DESEN.search(ozet or "")
    if not m:
        return (ozet or "").strip(), {}
    s = {}
    for p in m.group(1).split(","):
        if "=" in p:
            k, v = p.split("=", 1)
            try:
                s[k.strip()] = int(v)
            except ValueError:
                pass
    return _OZET_DESEN.sub("", ozet).strip(), s


def soru_ozeti(sorular_md: str, icerik_md: str = "") -> dict:
    """0 token: soru sayıları tür bazlı (iş kararı / teknik / doğrulanamadı) + zorunlu + toplam."""
    try:
        from .soru_turu import tur_sayilari, _ZORUNLU_SATIR
        md = (sorular_md or "") if (sorular_md or "").strip() else (icerik_md or "")
        t = tur_sayilari(md)
        return {"is": t["is_karari"], "teknik": t["teknik_arastirma"], "dogru": t["dogrulanamadi"],
                "zorunlu": len(_ZORUNLU_SATIR.findall(md)), "toplam": sum(t.values())}
    except Exception:
        return {"is": 0, "teknik": 0, "dogru": 0, "zorunlu": 0, "toplam": 0}


def kaydet(tip: str, kaynak: str, icerik_md: str, sorular_md: str = "", jira_key: str = "",
           proje: str = "") -> dict | None:
    """Analizi arşive yazar + sink'e gönderir. tip: surec | teknik | task | sohbet-surec | sohbet-teknik. Fail-safe."""
    try:
        from .ornek_havuzu import _redakte, _sink_push, _test_modu
        icerik = _redakte(icerik_md or "").strip()
        if len(icerik) < 200:
            return None
        if len(icerik) > _ICERIK_KC:
            icerik = icerik[:_ICERIK_KC] + "\n\n…(arşiv kırpıldı)"
        try:
            from . import telemetri
            kimlik = telemetri.analist_kimlik_oku()
            analist, eposta = kimlik.get("ad_soyad", ""), kimlik.get("eposta", "")
        except Exception:
            analist, eposta = "", ""
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        s = soru_ozeti(sorular_md, icerik)
        oid = "inc-" + hashlib.sha1(f"{tip}|{ts}|{eposta}|{icerik[:3000]}".encode()).hexdigest()[:16]
        kayit = {"id": oid, "tip": f"inceleme:{tip}", "ts": ts, "analist": analist, "eposta": eposta,
                 "proje": (proje or "").strip(), "jira_key": (jira_key or "").strip(),
                 "ozet": _ozet_gom(kaynak, s), "icerik": icerik + (("\n\n---\n\n## Açık Sorular (arşiv)\n\n" + _redakte(sorular_md))
                                                                 if (sorular_md or "").strip() and sorular_md.strip() not in icerik else "")}
        ARSIV_DIR.mkdir(parents=True, exist_ok=True)
        (ARSIV_DIR / f"{oid}.json").write_text(json.dumps(kayit, ensure_ascii=False), encoding="utf-8")
        if not _test_modu():
            _sink_push(kayit)
        _buda()
        return kayit
    except Exception:
        return None


def _buda(azami: int = 200) -> None:
    try:
        d = sorted((p for p in ARSIV_DIR.glob("inc-*.json")), key=lambda p: p.stat().st_mtime)
        for p in d[:-azami] if len(d) > azami else []:
            p.unlink(missing_ok=True)
    except Exception:
        pass


def _oku_dizin(dizin: Path, uzak: bool) -> list[dict]:
    out = []
    try:
        for p in dizin.glob("inc-*.json"):
            try:
                k = json.loads(p.read_text(encoding="utf-8"))
                k["uzak"] = uzak
                out.append(k)
            except Exception:
                continue
    except Exception:
        pass
    return out


def notlar() -> dict:
    try:
        return json.loads(NOT_DOSYA.read_text(encoding="utf-8")) if NOT_DOSYA.exists() else {}
    except Exception:
        return {}


def not_yaz(oid: str, metin: str) -> bool:
    if not _ID.match(oid or ""):
        return False
    n = notlar()
    if (metin or "").strip():
        n[oid] = {"not": metin.strip()[:2000], "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    else:
        n.pop(oid, None)
    ARSIV_DIR.mkdir(parents=True, exist_ok=True)
    NOT_DOSYA.write_text(json.dumps(n, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def liste() -> list[dict]:
    """Yerel + uzak kayıtların özeti (içeriksiz), en yeni önce; aynı id tek kez."""
    n = notlar()
    gorulen: set[str] = set()
    out = []
    for k in _oku_dizin(ARSIV_DIR, False) + _oku_dizin(UZAK_DIR, True):
        if k.get("id") in gorulen:
            continue
        gorulen.add(k.get("id"))
        kaynak, s = _ozet_coz(k.get("ozet", ""))
        out.append({"id": k.get("id"), "tip": str(k.get("tip", "")).replace("inceleme:", ""), "ts": k.get("ts", ""),
                    "analist": k.get("analist", ""), "eposta": k.get("eposta", ""), "proje": k.get("proje", ""),
                    "jira_key": k.get("jira_key", ""), "kaynak": kaynak, "sorular": s, "uzak": k.get("uzak", False),
                    "boyut": len(k.get("icerik") or ""), "not": (n.get(k.get("id")) or {}).get("not", "")})
    return sorted(out, key=lambda x: str(x.get("ts", "")), reverse=True)


def oku(oid: str) -> dict | None:
    if not _ID.match(oid or ""):
        return None
    for dizin in (ARSIV_DIR, UZAK_DIR):
        p = dizin / f"{oid}.json"
        if p.exists():
            try:
                k = json.loads(p.read_text(encoding="utf-8"))
                kaynak, s = _ozet_coz(k.get("ozet", ""))
                return {**k, "kaynak": kaynak, "sorular": s, "not": (notlar().get(oid) or {}).get("not", "")}
            except Exception:
                return None
    return None


def cek() -> tuple[bool, str]:
    """Merkezi sink'ten ekibin arşiv kayıtlarını (tip 'inceleme:*') indirir → uzak/ dizini. Owner e-posta kapısı sink'te."""
    try:
        from .ornek_havuzu import _test_modu, _redakte
        if _test_modu():
            return False, "test modu — ağ erişimi kapalı."
        from . import telemetri
        import requests
        url = telemetri._sink_url()
        if not url:
            return False, "Sink URL yok."
        params = {"ornekler": "1"}
        try:
            eposta = (telemetri.analist_eposta_oku() or "").strip()
            if eposta:
                params["email"] = eposta
        except Exception:
            pass
        try:
            key = telemetri._sink_key()
            if key:
                params["read"] = key
        except Exception:
            pass
        try:
            tok = telemetri._yazma_token()
            if tok:
                params["t"] = tok
        except Exception:
            pass
        r = requests.get(url, params=params, timeout=25)
        veri = r.json()
        if not isinstance(veri, list):
            return False, (veri.get("error") if isinstance(veri, dict) else "") or "Yetki yok ya da beklenmeyen yanıt."
        UZAK_DIR.mkdir(parents=True, exist_ok=True)
        n = 0
        for o in veri:
            if not isinstance(o, dict) or not str(o.get("tip") or "").startswith("inceleme:"):
                continue
            oid = str(o.get("id") or "").strip()
            if not _ID.match(oid):
                continue
            kayit = {k: (str(o.get(k) or "")) for k in ("id", "tip", "ts", "analist", "eposta", "proje", "jira_key", "ozet")}
            kayit["icerik"] = _redakte(str(o.get("icerik") or ""))[:_ICERIK_KC]
            (UZAK_DIR / f"{oid}.json").write_text(json.dumps(kayit, ensure_ascii=False), encoding="utf-8")
            n += 1
        return True, f"{n} arşiv kaydı çekildi."
    except Exception as e:
        return False, f"Çekilemedi: {str(e)[:160]}"
