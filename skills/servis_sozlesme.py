"""Kayıtlı Swagger/OpenAPI servislerinden (reference/services/*.json) task'a ALAKALI endpoint sözleşmelerini
(method + path + request/response şeması) çıkarıp analiz bağlamına enjekte eder.

Owner isteri (2026-10-21): BE task analizinde agent, mimari kararı analiste bırakmamalı — önce Swagger'da mevcut
endpoint'i arayıp KULLANMALI, yoksa canlı gözlemle doğrulamalı, ikisinde de gerçekten yoksa yeni endpoint tasarlamalı.
SORUN: task metni iç servis adını (nebula, id-mapping) içermediğinden BM25 retrieval o endpoint'leri yüzeye
çıkarmıyor; agent canlı gözlemde servisi görse de sözleşmeyi (request/response alanları) bağlamda bulamıyordu.
ÇÖZÜM: bu modül, task metni + canlı gözlemde geçen path/kaynak adlarıyla eşleşen endpoint'lerin SÖZLEŞMESİNİ
doğrudan Swagger'dan çekip verir → agent mevcut sözleşmeyi görür, kullanır (ya da yoksa tasarlar).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SERVICES_DIR = BASE_DIR / "reference" / "services"

_TOKEN = re.compile(r"[a-zA-Z][a-zA-Z0-9]+")
_YOL_KAYNAK = re.compile(r"/([a-zA-Z][a-zA-Z0-9-]{2,})")   # path segmentleri (kaynak adları)
_STOP = {"the", "and", "for", "with", "get", "post", "put", "api", "bff", "service", "list", "all", "new"}
# Jenerik path segmentleri — TÜM endpoint'lerde geçtiği için alaka/boost sinyali DEĞİL (yoksa 'bff' herkesi eşler).
_YOL_STOP = {"bff", "api", "v1", "v2", "v3", "service", "services", "external", "internal", "by", "id", "all"}


def _yol_kaynaklari(yol: str) -> set[str]:
    return {s.lower() for s in _YOL_KAYNAK.findall(yol or "") if s.lower() not in _YOL_STOP}


def _tokenle(metin: str) -> set[str]:
    # camelCase + kebab/snake böl → küçük harf token kümesi
    ham = _TOKEN.findall((metin or ""))
    out = set()
    for t in ham:
        for p in re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])", t):
            p = p.lower()
            if len(p) >= 3 and p not in _STOP:
                out.add(p)
    return out


def _sema_coz(sema: dict, bilesenler: dict, derinlik: int = 0) -> dict:
    """OpenAPI şemasını {alan: tip} sözlüğüne indirger ($ref'i 1-2 kat çözer; dizi/obje özetlenir)."""
    if not isinstance(sema, dict) or derinlik > 3:
        return {}
    if "$ref" in sema:
        ad = sema["$ref"].split("/")[-1]
        return _sema_coz(bilesenler.get(ad, {}), bilesenler, derinlik + 1)
    tip = sema.get("type")
    if tip == "array":
        ic = _sema_coz(sema.get("items", {}), bilesenler, derinlik + 1)
        return {"[]": ic} if ic else {"[]": sema.get("items", {}).get("type", "obje")}
    props = sema.get("properties")
    if isinstance(props, dict):
        out = {}
        for ad, alt in list(props.items())[:40]:
            if "$ref" in alt or alt.get("type") in ("object", "array"):
                ic = _sema_coz(alt, bilesenler, derinlik + 1)
                out[ad] = ic if ic else (alt.get("type") or "obje")
            else:
                out[ad] = alt.get("type", "any") + (f"<{alt['format']}>" if alt.get("format") else "")
        return out
    return {}


def _sema_metin(d, kirp: int = 900) -> str:
    try:
        s = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        s = str(d)
    return s[:kirp] + ("…" if len(s) > kirp else "")


def _endpointleri_oku() -> list[dict]:
    """Tüm kayıtlı Swagger'lardan endpoint kayıtları: {servis, method, path, ozet, istek, yanit, token}."""
    kayitlar: list[dict] = []
    try:
        dosyalar = sorted(SERVICES_DIR.glob("*.json"))
    except Exception:
        return kayitlar
    for f in dosyalar:
        try:
            spec = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        bilesenler = (spec.get("components", {}) or {}).get("schemas", {}) or {}
        paths = spec.get("paths", {}) or {}
        for yol, opsler in paths.items():
            if not isinstance(opsler, dict):
                continue
            for method, op in opsler.items():
                if method.lower() not in ("get", "post", "put", "delete", "patch") or not isinstance(op, dict):
                    continue
                ozet = op.get("summary") or op.get("operationId") or ""
                istek = {}
                rb = (op.get("requestBody", {}) or {}).get("content", {}) or {}
                for ct in ("application/json", *rb.keys()):
                    if ct in rb:
                        istek = _sema_coz((rb[ct] or {}).get("schema", {}), bilesenler)
                        break
                yanit = {}
                resps = op.get("responses", {}) or {}
                for kod in ("200", "201", "default"):
                    if kod in resps:
                        rc = (resps[kod] or {}).get("content", {}) or {}
                        for ct in ("application/json", *rc.keys()):
                            if ct in rc:
                                yanit = _sema_coz((rc[ct] or {}).get("schema", {}), bilesenler)
                                break
                        break
                kayitlar.append({
                    "servis": f.stem, "method": method.upper(), "path": yol, "ozet": ozet,
                    "istek": istek, "yanit": yanit,
                    "token": _tokenle(yol + " " + ozet) | _yol_kaynaklari(yol),
                })
    return kayitlar


def endpoint_baglami(sorgu_metni: str, ek_metin: str = "", butce: int = 9000, azami: int = 10) -> str:
    """Task metni (+ canlı gözlem/BFF metni) ile EN ALAKALI kayıtlı endpoint'lerin SÖZLEŞMESİNİ (method+path+
    istek/yanıt şeması) döndürür — agent mevcut servisi görsün ve kullansın (ister dışı endpoint EKLEMEZ; yalnız
    task'a alakalı olanlar). Alaka yoksa/boşsa boş döner (blok eklenmez)."""
    kayitlar = _endpointleri_oku()
    if not kayitlar:
        return ""
    sorgu_tok = _tokenle(sorgu_metni + " " + ek_metin)
    # Canlı gözlem/task metninde GEÇEN gerçek path kaynakları (ör. /bff/nebula/id-mapping-service/...) güçlü sinyal
    gecenler = _yol_kaynaklari(sorgu_metni + " " + ek_metin)
    if not sorgu_tok and not gecenler:
        return ""
    skorlu = []
    for k in kayitlar:
        ortak = len(k["token"] & sorgu_tok)
        # Path kaynağı metinde birebir geçiyorsa büyük boost (gözlemlenen/istenen endpoint)
        path_boost = 5 * len(_yol_kaynaklari(k["path"]) & gecenler)
        skor = ortak + path_boost
        if skor > 0:
            skorlu.append((skor, k))
    if not skorlu:
        return ""
    skorlu.sort(key=lambda x: x[0], reverse=True)
    satirlar = ["### KAYITLI SERVİS SÖZLEŞMELERİ (Swagger — task'a alakalı MEVCUT endpoint'ler)",
                "Aşağıdakiler sistemde ZATEN VAR olan endpoint'lerdir. İhtiyacını karşılayan varsa ÇÖZÜM OLARAK KULLAN "
                "(method+path+alanları aynen), `[K: Swagger:<servis>]` ile. Yoksa canlı gözlemle doğrula; o da yoksa yeni tasarla.\n"]
    toplam = len(satirlar[0]) + len(satirlar[1])
    n = 0
    for skor, k in skorlu:
        if n >= azami:
            break
        blok = f"- **{k['method']} {k['path']}**" + (f" — {k['ozet']}" if k["ozet"] else "") + f"  `[K: Swagger:{k['servis']}]`\n"
        if k["istek"]:
            blok += f"  - İstek: `{_sema_metin(k['istek'])}`\n"
        if k["yanit"]:
            blok += f"  - Yanıt: `{_sema_metin(k['yanit'])}`\n"
        if toplam + len(blok) > butce:
            break
        satirlar.append(blok)
        toplam += len(blok)
        n += 1
    return "".join(satirlar) if n else ""
