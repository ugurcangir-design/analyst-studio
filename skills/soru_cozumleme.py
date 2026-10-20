"""Açık Soru Öz-Çözümleme — Task Analizi'nin açık sorularını analist görmeden ÖNCE agent kendisi araştırır.

Owner geri bildirimi (2026-10-16): "bu soruları referanslar kısmından ve canlı gözlemden bakarak agent çözemez mi?"
Soru üretimi analizden sonra ayrı/ucuz bir adımda çalışır ve elinde yalnız analiz metni vardır; referanslar soruya göre
değil task metnine göre seçilmiştir. Bu modül her soru için HEDEFLİ araştırma yapar:
  1. kanıt toplama (0 token): sorunun metniyle referans corpus'unda BM25 (Swagger/Confluence/Jira/canlı-app), sorudaki
     endpoint/alan adları için tüketici taraması (`degisiklik_etkisi.tuketici_tara`), Kod Kaynağı bağlıysa kod araması
  2. tek AI çağrısı: her soru → `cevaplandi | kismi | karar_gerekli` + kanıtlı cevap + "canlı gözlemle kesinleşir mi?"
  3. gözlem gereken sorular için TEK odaklı canlı gözlem turu (hedef varsa) → bulgular birleştirilir
  4. soru bloklarına `- Agent durumu / Agent cevabı / Agent kanıtı` satırları eklenir → UI cevap kutusunu ÖNCEDEN doldurur
     ("🤖 agent buldu"), analist onaylar/düzeltir, "Cevapları İşle" aynı akışla çalışır. Analiz yeniden YAZILMAZ (maliyet yok);
     yalnız gerçek karar soruları boş kalır.
Kapatma: `.env` `SORU_COZUMLEME=false` ya da `HIZLI_MOD=true`. Hata → orijinal sorular aynen döner (analiz kırılmaz).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .base import (
    REF_DIR, MAX_TOKENS_KISA, MAX_TOKENS_COMBINED,
    _api_cagri, _xml_ayir, _metin_sikistir, hizli_mod_acik, asama_ayarla,
    referans_dosyalari_hazirla, _ref_dokuman_metinleri,
    canli_uygulama_baglami_hazirla, gorev_live_app_urls, live_app_urls,
)

DURUMLAR = ("cevaplandi", "kismi", "karar_gerekli")
_DURUM_ETIKET = {"cevaplandi": "cevaplandı", "kismi": "kısmen", "karar_gerekli": "karar gerekli"}
_MAX_SORU = 8
_KANIT_BUTCE = 7_000          # soru başına referans parçası karakteri
_MAX_TUKETICI = 8
_MAX_KOD = 6
_BLOK = re.compile(r"(?m)^###\s+(Q-[A-Za-z0-9-]+)\s*:?\s*(.*)$")
_YOL = re.compile(r"(?:GET|POST|PUT|PATCH|DELETE)?\s*(/[A-Za-z0-9_\-{}|./]{4,})")
_KIMLIK = re.compile(r"`([A-Za-z_][A-Za-z0-9_\-./]{2,60})`|\b([a-z]+(?:[A-Z][a-z0-9]+)+|[a-z]+(?:_[a-z0-9]+)+)\b")


def acik_mi() -> bool:
    if hizli_mod_acik():
        return False
    return (os.getenv("SORU_COZUMLEME", "true") or "true").strip().lower() not in ("false", "0", "hayir", "no")


def uygula_acik_mi() -> bool:
    """Kanıtla CEVAPLANAN sorular analize OTOMATİK işlensin mi? (owner 2026-10-19: 'agent cevap bulduğu soruları neden
    analize işlemedi de soru olarak gösterdi — ekstra süre/token'). Varsayılan auto: tek ucuz hedefli düzeltme çağrısı
    (`gorev_analiz_duzelt`: referanssız, gözlemsiz) ile cevaplar ilgili bölümlere işlenir, sorular listeden düşer.
    `SORU_COZUMLEME_UYGULA=onay` → eski davranış (kutular ön-dolu, analist 'Cevapları İşle' der = TAM yeniden üretim)."""
    return (os.getenv("SORU_COZUMLEME_UYGULA", "auto") or "auto").strip().lower() not in ("onay", "manuel", "false", "0")


COZULEN_BASLIK = "## 🤖 Agent'ın çözüp analize işlediği sorular"


def cozulenleri_ayir(acik_md: str) -> tuple[str, list[dict]]:
    """`Agent durumu: cevaplandı` bloklarını açık sorulardan AYIRIR. Dönen: (kalan_md, [{id, soru, cevap, kanit, gozlem}]).
    'kısmen' ve 'karar gerekli' bloklar kalır (analist onayı/kararı gerekir)."""
    kalan = acik_md or ""
    cozulen: list[dict] = []
    for b in _bloklar(acik_md or ""):
        d = re.search(r"(?mi)^-\s*Agent durumu\s*:\s*(.+)$", b["govde"])
        if not d or not d.group(1).strip().lower().startswith("cevap"):
            continue

        def alan(ad, _g=b["govde"]):
            r = re.search(r"(?mi)^-\s*" + re.escape(ad) + r"\s*:\s*(.+)$", _g)
            return r.group(1).strip() if r else ""
        cozulen.append({"id": b["id"], "baslik": b["baslik"], "soru": b["soru"], "cevap": alan("Agent cevabı"),
                        "kanit": alan("Agent kanıtı"), "gozlem": alan("Agent gözlemi"), "bagli": b["bagli"]})
        kalan = kalan.replace(b["metin"], "", 1)
    return re.sub(r"\n{3,}", "\n\n", kalan).strip(), cozulen


def uygulama_talimati(cozulen: list[dict]) -> str:
    """`gorev_analiz_duzelt` için talimat: cevapları ilgili bölümlere MINIMAL işle, belirsizlik işaretlerini kaldır."""
    sat = []
    for c in cozulen:
        sat.append(f"- {c['id']} ({c['bagli'] or 'ilgili bölüm'}): SORU: {c['soru']}\n  CEVAP (kanıtlı): {c['cevap']}"
                   + (f" {c['kanit']}" if c["kanit"] else "") + (f"\n  GÖZLEM: {c['gozlem']}" if c["gozlem"] else ""))
    return ("Aşağıdaki açık sorular referans/kod/canlı gözlem kanıtıyla CEVAPLANDI. Her cevabı analizin İLGİLİ bölümüne "
            "(Bağlı bölüm) minimal biçimde işle: bu konudaki `[K: ❓ Belirsiz]`/'belirsiz'/'netleştirilmeli'/'varsayım' "
            "ifadelerini kaldırıp kesin ifadeye çevir, kanıt etiketini `[K: …]` olarak koru, gerekiyorsa tek cümle/satır ekle. "
            "Başka bölümlere DOKUNMA, analizi büyütme, yeni bölüm açma, soru listesi yazma.\n\n" + "\n".join(sat))


def cozulen_bolumu(cozulen: list[dict]) -> str:
    """Açık sorular md'sine eklenen şeffaflık bölümü (UI katlanmış gösterir; UI parser Q- başlığı olmadığı için soru saymaz)."""
    if not cozulen:
        return ""
    sat = [COZULEN_BASLIK, "", "_Aşağıdaki sorular agent tarafından kanıtla cevaplanıp analize işlendi; onay gerekmez._", ""]
    for c in cozulen:
        sat.append(f"- **{c['id']}** {c['soru']}\n  → {c['cevap']}" + (f" {c['kanit']}" if c["kanit"] else ""))
    return "\n".join(sat) + "\n"


# ── Soru blokları ─────────────────────────────────────────────────────────────
def _bloklar(md: str) -> list[dict]:
    """`### Q-T-001: Başlık` bloklarını ayırır: {id, baslik, govde, metin, alan()}."""
    out = []
    parcalar = re.split(r"(?m)^(?=###\s+Q-)", md or "")
    for p in parcalar:
        m = _BLOK.match(p)
        if not m:
            continue
        govde = p[m.end():]

        def alan(ad, _g=govde):
            r = re.search(r"(?mi)^-\s*" + re.escape(ad) + r"\s*:\s*(.+)$", _g)
            return r.group(1).strip() if r else ""
        out.append({"id": m.group(1), "baslik": m.group(2).strip(), "metin": p, "govde": govde,
                    "soru": alan("Soru") or m.group(2).strip(), "beklenen": alan("Beklenen yanıt") or alan("Beklenen"),
                    "bagli": alan("Bağlı bölüm") or alan("Bağlı"), "zaten": bool(alan("Agent durumu"))})
    return out


def _adaylar(soru: dict) -> list[str]:
    """Sorudaki endpoint yolları + kod kimlikleri (tüketici taraması / kod araması için)."""
    metin = f"{soru['baslik']} {soru['soru']} {soru['beklenen']}"
    ad: list[str] = []
    for m in _YOL.finditer(metin):
        yol = m.group(1).rstrip(".,;:)")
        for parca in re.split(r"[|]", yol):          # `/bff/spectron|fiora/...` → iki yol
            ad.append(parca.strip("/").split("/")[-1])   # son segment (my-permissions)
            ad.append(parca)
    for m in _KIMLIK.finditer(metin):
        ad.append(m.group(1) or m.group(2))
    temiz, gorulen = [], set()
    for a in ad:
        a = (a or "").strip()
        if len(a) < 3 or a.lower() in gorulen or a.lower() in ("get", "post", "put", "delete", "jira", "api", "bff"):
            continue
        gorulen.add(a.lower())
        temiz.append(a)
    return temiz[:8]


# ── Kanıt toplama (0 token) ───────────────────────────────────────────────────
def _corpus(rag_ctx: dict | None = None) -> list[dict]:
    """Referans dosyalarını BM25 için okunmuş metne çevirir (tip: swagger/confluence/jira/canli_uygulama/diger).
    `rag_ctx` (köprü — kendi kendine yeterli bağlam: task keyword'leri) verilirse ekrandaki filtre yerine o kullanılır."""
    dosyalar = (referans_dosyalari_hazirla(ctx_override=rag_ctx) if rag_ctx is not None else referans_dosyalari_hazirla()) or []
    grup: dict[str, list[Path]] = {"swagger": [], "canli_uygulama": [], "confluence": [], "jira": [], "diger": []}
    for f in dosyalar:
        try:
            rel = str(Path(f).relative_to(REF_DIR)).replace("\\", "/")
        except ValueError:
            rel = Path(f).name
        if rel.startswith("services/"):
            grup["swagger"].append(Path(f))
        elif rel.startswith("live-app/"):
            grup["canli_uygulama"].append(Path(f))
        elif rel.startswith("confluence/"):
            grup["confluence"].append(Path(f))
        elif rel.startswith("jira/"):
            grup["jira"].append(Path(f))
        else:
            grup["diger"].append(Path(f))
    konfig = [(k, "", "", v, _KANIT_BUTCE, k == "jira") for k, v in grup.items() if v]
    return _ref_dokuman_metinleri(konfig) if konfig else []


def _referans_kaniti(corpus: list[dict], soru: dict) -> str:
    if not corpus:
        return ""
    from .retrieval import en_alakali_corpus
    sorgu = f"{soru['baslik']} {soru['soru']} {soru['beklenen']} {' '.join(_adaylar(soru))}"
    try:
        r = en_alakali_corpus(corpus, sorgu, _KANIT_BUTCE)
    except Exception:
        return ""
    if r.get("alaka_yok"):
        return ""
    sat = []
    for p in r.get("secilen") or []:
        sat.append(f"[{p.get('tip')}:{p.get('rel')}]\n{(p.get('metin') or '').strip()}")
    return "\n\n".join(sat)[:_KANIT_BUTCE + 500]


def _tuketici_kaniti(soru: dict) -> str:
    adaylar = _adaylar(soru)
    if not adaylar:
        return ""
    try:
        from .degisiklik_etkisi import tuketici_tara
        b = tuketici_tara(adaylar)
    except Exception:
        return ""
    if not b:
        return ""
    sat = [f"- `{x.get('aday')}` → {x.get('kaynak')} · {x.get('nerede')}" + (f" — {x.get('ozet')}" if x.get("ozet") else "")
           for x in b[:_MAX_TUKETICI]]
    return "Tüketici taraması (Swagger/Confluence/Jira referanslarında geçtiği yerler):\n" + "\n".join(sat)


def _kod_kaniti(soru: dict) -> str:
    try:
        from . import kod_kaynagi
        if not kod_kaynagi.yapilandirildi_mi():
            return ""
        repolar = kod_kaynagi.repolar()
    except Exception:
        return ""
    sat = []
    for aday in _adaylar(soru)[:3]:
        for r in repolar[:3]:
            try:
                s = kod_kaynagi.ara(r.get("ad") or r.get("name") or "", aday, limit=_MAX_KOD)
            except Exception:
                continue
            for e in (s.get("eslesmeler") or [])[:_MAX_KOD]:
                sat.append(f"- `{aday}` → {e.get('yol')}:{e.get('satir_no')} — {str(e.get('satir') or '').strip()[:160]}")
    return ("Kod araması (bağlı repo):\n" + "\n".join(sat[:_MAX_KOD * 2])) if sat else ""


def kanit_topla(sorular: list[dict], rag_ctx: dict | None = None) -> dict[str, str]:
    try:
        corpus = _corpus(rag_ctx) if rag_ctx is not None else _corpus()
    except TypeError:          # test enjeksiyonu parametre almıyorsa
        corpus = _corpus()
    out = {}
    for s in sorular:
        parcalar = [x for x in (_referans_kaniti(corpus, s), _tuketici_kaniti(s), _kod_kaniti(s)) if x]
        out[s["id"]] = "\n\n".join(parcalar) if parcalar else "(referanslarda doğrudan kanıt bulunamadı)"
    return out


# ── AI: sınıflandır + cevapla ─────────────────────────────────────────────────
_SISTEM = """# ROL
Kıdemli teknik analistsin. Bir Jira görevinin teknik analizinden çıkan AÇIK SORULARI, analist görmeden ÖNCE sen araştırırsın.
Her soru için toplanmış KANITLAR (Swagger/Confluence/Jira/canlı-app referans parçaları, tüketici taraması, kod araması) verilir.

# GÖREV — her soru için karar ver
- `cevaplandi`: kanıt soruyu NET cevaplıyor → `cevap` (kısa, emir kipinde; geliştiricinin uygulayacağı biçimde) + `kanit`
  (`[K: Swagger:<dosya>]` / `[K: Confluence:<sayfa>]` / `[K: Jira:KEY]` / `[K: Kod:<yol>]`).
- `kismi`: kanıt daraltıyor ama kesin değil → `cevap` = kanıta dayalı en olası yanıt + hangi parça belirsiz.
- `karar_gerekli`: ürün/iş kararı, kanıtla kapanmaz (ör. "boş kümede baseline mi verilsin?") → `cevap` = kararı kolaylaştıran
  özet (seçenekler + kanıtın işaret ettiği taraf), kısa.
- `gozlem_gerekli`: sorunun cevabı CANLI uygulamada gözlenerek kesinleşir mi? (ör. bir ekranın şu an izin kontrolünden geçip
  geçmediği, bir isteğin hangi ekranlarda tetiklendiği) → true + `gozlem_adimi` (uygulamada ne yapılıp neye bakılacak, 1-3 adım).
  Kod/sunucu içi ya da ürün kararı için false.
# KURALLAR
- UYDURMA: kanıtta olmayan endpoint/alan/kural yazma; kanıt yoksa `karar_gerekli` ya da `gozlem_gerekli` de.
- Tüketici taraması bir ucu/alanı başka ekran/servislerde gösteriyorsa bunu "etkilenen tüketiciler" olarak cevaba yaz.
- Şifre/token yazma. Kısa yaz.
# ÇIKTI — yalnız bu blok
<soru_cozum>[{"id":"Q-T-001","durum":"cevaplandi|kismi|karar_gerekli","cevap":"","kanit":"[K: …]","gozlem_gerekli":false,"gozlem_adimi":""}]</soru_cozum>"""

_GOZLEM_FORMAT = """
### GÖZLEM ÇIKTI BİÇİMİ (zorunlu) — gözlem bitince YALNIZ şu blok:
<gozlem_cozum>[{"id":"Q-T-001","sonuc":"cevaplandi|kismi|belirsiz","bulgu":"ne yaptın + ne gördün (kısa)","kanit":"[K: Canlı UI:/route] / [K: Network:GET /x → 200]"}]</gozlem_cozum>
KURALLAR: her id için bir kayıt; 'cevaplandi' yalnız davranışı FİİLEN gördüysen; göremediysen 'belirsiz' + neden. Tahmin YASAK."""


def _json_dizi(metin: str, tag: str):
    ham = _xml_ayir(metin or "", tag)
    try:
        v = json.loads(ham)
        return v if isinstance(v, list) else None
    except Exception:
        a, b = ham.find("["), ham.rfind("]")
        if a == -1 or b <= a:
            return None
        try:
            v = json.loads(ham[a:b + 1])
            return v if isinstance(v, list) else None
        except Exception:
            return None


def _siniflandir(gorev: dict, sorular: list[dict], kanitlar: dict[str, str], _ai=None) -> dict[str, dict]:
    asama_ayarla("soru:cozum")
    ai = _ai or (lambda s, m: _api_cagri(s, m, max_tokens=MAX_TOKENS_KISA, thinking=False, katman="yardimci"))
    parcalar = [f"### Jira Görevi: {gorev.get('key', '')} — {gorev.get('summary', '')}"]
    for s in sorular:
        parcalar.append(f"### {s['id']}: {s['baslik']}\n{s['govde'].strip()}\n\n#### KANITLAR ({s['id']})\n{kanitlar.get(s['id'], '')}")
    parcalar.append("Her soru için karar ver ve bloğu yaz.")
    mesajlar = [{"role": "user", "content": [{"type": "text", "text": p} for p in parcalar]}]
    yanit = ai(_SISTEM, mesajlar)
    ham = _json_dizi(yanit, "soru_cozum")
    if not ham and _ai is None:
        # Bozuk/boş yanıt 7 gün önbellekte kalmasın → BİR KEZ önbelleksiz tekrar
        yanit = _api_cagri(_SISTEM, mesajlar, max_tokens=MAX_TOKENS_KISA, thinking=False, katman="yardimci", onbellek=False)
        ham = _json_dizi(yanit, "soru_cozum")
    out: dict[str, dict] = {}
    for r in ham or []:
        if not isinstance(r, dict):
            continue
        qid = str(r.get("id") or "").strip()
        if not qid:
            continue
        durum = str(r.get("durum") or "").strip().lower()
        out[qid] = {"durum": durum if durum in DURUMLAR else "karar_gerekli",
                    "cevap": str(r.get("cevap") or "").strip(), "kanit": str(r.get("kanit") or "").strip(),
                    "gozlem_gerekli": bool(r.get("gozlem_gerekli")), "gozlem_adimi": str(r.get("gozlem_adimi") or "").strip()}
    return out


# ── Canlı gözlem (tek tur, yalnız işaretli sorular) ───────────────────────────
def _canli_kapsam_sec(canli_kapsam: str | None = None) -> str | None:
    """Gözlem URL kaynağı: açıkça verilen kapsam ('gorev' → live_app_gorev, 'surec' → live_app ana adresi) o alan doluysa;
    yoksa eski sıra: live_app_gorev varsa 'gorev', değilse live_app varsa 'surec', hiçbiri yoksa None."""
    if canli_kapsam == "gorev" and gorev_live_app_urls():
        return "gorev"
    if canli_kapsam == "surec" and live_app_urls():
        return "surec"
    if gorev_live_app_urls():
        return "gorev"
    return "surec" if live_app_urls() else None


def _canli_hedef(sorular_gozlem: list[tuple[dict, dict]], canli_kapsam: str | None = None) -> str | None:
    adimlar = "\n".join(f"- **{s['id']}** {s['soru']}\n  · Gözlem: {c['gozlem_adimi'] or '—'}" for s, c in sorular_gozlem)
    hedef = ("AÇIK SORU DOĞRULAMASI — yalnız aşağıdaki soruları kesinleştirecek kadar gez; analiz yazma.\n" + adimlar
             + "\n" + _GOZLEM_FORMAT)
    kapsam = _canli_kapsam_sec(canli_kapsam)
    if kapsam == "gorev":
        return canli_uygulama_baglami_hazirla(gorev=True, hedef_tarif=hedef)
    if kapsam == "surec":
        from urllib.parse import urlparse
        p = urlparse(live_app_urls()[0])
        if p.scheme and p.netloc:
            return canli_uygulama_baglami_hazirla(base_url_override=f"{p.scheme}://{p.netloc}", hedef_tarif=hedef)
    return None


def soru_tur_butcesi(soru_sayisi: int) -> int:
    """Soru çözüm gözlemi tur tavanı: taban + soru×katsayı (env SORU_GOZLEM_TUR_TABAN/MADDE/TAVAN; vars. 25 + 20×n, ≤ 110)."""
    def _e(ad, v):
        try:
            return int(os.getenv(ad, str(v)))
        except (TypeError, ValueError):
            return v
    return max(_e("SORU_GOZLEM_TUR_TABAN", 25), min(_e("SORU_GOZLEM_TUR_TAVAN", 110), _e("SORU_GOZLEM_TUR_TABAN", 25) + _e("SORU_GOZLEM_TUR_MADDE", 20) * max(1, soru_sayisi)))


def _gozlemle(gorev: dict, sorular_gozlem: list[tuple[dict, dict]], _ai=None, canli_kapsam: str | None = None) -> dict[str, dict]:
    canli = _canli_hedef(sorular_gozlem, canli_kapsam)
    if not canli:
        return {}
    sistem = ("Kıdemli analist/testçisin. Verilen uygulamada yalnız listelenen açık soruları kesinleştirmek için gözlem "
              "yaparsın; her soru için fiilen gördüğünü kanıtla raporlarsın. Analiz yazmazsın.")
    n = max(1, len(sorular_gozlem))
    icerik = [{"type": "text", "text": canli},
              {"type": "text", "text": f"### Task: {gorev.get('key', '')} — {gorev.get('summary', '')}"},
              {"type": "text", "text": (
                  f"### STRATEJİ (tur bütçesi: {soru_tur_butcesi(n)} tur, {n} soru)\n"
                  "- Soruları SIRAYLA al; her soru için gerekli en kısa yolu izle, kanıtı alınca sonrakine geç.\n"
                  "- 'Hangi alanlar gönderiliyor / payload ne' tipi sorularda: ilgili modalı aç, zararsız bir alanı değiştirip KAYDET, "
                  "`browser_network_requests` → ilgili isteği `browser_network_request` ile aç, method/path + istek gövdesindeki ALAN ADLARINI "
                  "aynen yaz (değerleri maskeleyebilirsin). Alanı hiç göndermeme/boş gönderme davranışı soruluyorsa ikinci bir kayıtla dene.\n"
                  "- Aynı sayfanın snapshot'ını ikinci kez alma; menü gezmek yerine doğrudan URL'e git.\n"
                  "- Bütçe dolmadan 'denenmedi' yazma; bir soru gerçekten erişilemiyorsa (yetki/veri yok) nedenini yaz ve sonrakine geç.")}]
    kapsam = _canli_kapsam_sec(canli_kapsam) or "surec"
    asama_ayarla("soru:gozlem")
    # Bütçe soru sayısına göre (eskiden genel 40 tur: 3 soru × modal aç/kaydet/istek yakala sığmıyor, 'tur bütçesi doldu'
    # ile boş dönüyordu — 2026-10-20). Tavana takılırsa 1 devam hakkı (aynı oturum kaldığı sorudan sürer).
    ai = _ai or (lambda s, m, k=kapsam: _api_cagri(s, m, max_tokens=MAX_TOKENS_COMBINED, thinking=False, onbellek=False,
                                                  canli_uygulama_kapsami=k, katman="yardimci",
                                                  max_turns=soru_tur_butcesi(n), tur_devam=1))
    yanit = _metin_sikistir(ai(sistem, [{"role": "user", "content": icerik}]))
    out: dict[str, dict] = {}
    for r in _json_dizi(yanit, "gozlem_cozum") or []:
        if isinstance(r, dict) and r.get("id"):
            out[str(r["id"]).strip()] = {"sonuc": str(r.get("sonuc") or "belirsiz").strip().lower(),
                                         "bulgu": str(r.get("bulgu") or "").strip(), "kanit": str(r.get("kanit") or "").strip()}
    return out


# ── Birleştir + md'ye yaz ─────────────────────────────────────────────────────
def _bloga_yaz(blok: dict, c: dict) -> str:
    metin = blok["metin"].rstrip("\n")
    # eski agent satırları varsa (cevap turu) yenile
    metin = re.sub(r"(?mi)^-\s*Agent (?:durumu|cevabı|kanıtı|gözlemi)\s*:.*\n?", "", metin + "\n").rstrip("\n")
    sat = [metin, f"- Agent durumu: {_DURUM_ETIKET.get(c['durum'], c['durum'])}"]
    if c.get("cevap"):
        sat.append(f"- Agent cevabı: {c['cevap']}")
    if c.get("kanit"):
        sat.append(f"- Agent kanıtı: {c['kanit']}")
    if c.get("gozlem"):
        sat.append(f"- Agent gözlemi: {c['gozlem']}")
    return "\n".join(sat) + "\n"


def cozumle(acik_md: str, gorev: dict, canli: bool = True, _ai=None, _ai_canli=None,
            rag_ctx: dict | None = None, canli_kapsam: str | None = None) -> str:
    """Açık sorular md'sini agent araştırmasıyla zenginleştirir. Hata → orijinal md. Analizi yeniden yazmaz.
    `rag_ctx` / `canli_kapsam`: köprü (ekran_baglami=False) kendi kendine yeterli bağlamını geçirir → kanıt araması
    task keyword'leriyle, gözlem doğru URL kapsamıyla (eskiden ekrandaki filtre + sabit sıra kullanılıyordu)."""
    if not (acik_md or "").strip() or "açık soru tespit edilmedi" in acik_md.lower():
        return acik_md
    try:
        sorular = [b for b in _bloklar(acik_md) if not b["zaten"]][:_MAX_SORU]
        if not sorular:
            return acik_md
        print(f"  🔎 Açık soru öz-çözümleme: {len(sorular)} soru için referans/kod kanıtı toplanıyor...")
        kanitlar = kanit_topla(sorular, rag_ctx=rag_ctx) if rag_ctx is not None else kanit_topla(sorular)
        cozum = _siniflandir(gorev, sorular, kanitlar, _ai=_ai)
        if not cozum:
            return acik_md
        gozlem_listesi = [(s, cozum[s["id"]]) for s in sorular
                          if s["id"] in cozum and cozum[s["id"]]["gozlem_gerekli"] and cozum[s["id"]]["durum"] != "cevaplandi"]
        if canli and gozlem_listesi:
            print(f"  🌐 {len(gozlem_listesi)} soru canlı gözlemle kesinleştiriliyor...")
            try:
                g = _gozlemle(gorev, gozlem_listesi, _ai=_ai_canli, canli_kapsam=canli_kapsam)
            except Exception as e:
                print(f"  ⚠ Soru gözlemi yapılamadı: {str(e)[:160]}")
                g = {}
            for s, c in gozlem_listesi:
                r = g.get(s["id"])
                if not r:
                    continue
                c["gozlem"] = (r["bulgu"] + (f" {r['kanit']}" if r["kanit"] else "")).strip()
                if r["sonuc"] == "cevaplandi":
                    c["durum"] = "cevaplandi"
                    c["cevap"] = (c["cevap"] + " — Canlı gözlem: " + r["bulgu"]).strip(" —") if r["bulgu"] else c["cevap"]
                    if r["kanit"]:
                        c["kanit"] = (c["kanit"] + " " + r["kanit"]).strip()
                elif r["sonuc"] == "kismi" and c["durum"] == "karar_gerekli":
                    c["durum"] = "kismi"
        # md'yi yeniden kur: bloklar sırayla, çözülen bloklara agent satırları
        out = acik_md
        for s in sorular:
            if s["id"] in cozum:
                out = out.replace(s["metin"], _bloga_yaz(s, cozum[s["id"]]), 1)
        n = sum(1 for c in cozum.values() if c["durum"] == "cevaplandi")
        print(f"  ✓ Öz-çözümleme: {n}/{len(sorular)} soru kanıtla cevaplandı, "
              f"{sum(1 for c in cozum.values() if c['durum'] == 'kismi')} kısmen, "
              f"{sum(1 for c in cozum.values() if c['durum'] == 'karar_gerekli')} karar gerekli.")
        return out
    except Exception as e:
        print(f"  ⚠ Açık soru öz-çözümleme atlandı: {str(e)[:160]}")
        return acik_md


def ozet(acik_md: str) -> dict:
    """UI/rapor için sayım: {toplam, cevaplandi, kismi, karar}."""
    b = _bloklar(acik_md or "")
    d = {"toplam": len(b), "cevaplandi": 0, "kismi": 0, "karar": 0}
    for x in b:
        r = re.search(r"(?mi)^-\s*Agent durumu\s*:\s*(.+)$", x["govde"])
        if not r:
            continue
        v = r.group(1).strip().lower()
        if v.startswith("cevap"):
            d["cevaplandi"] += 1
        elif v.startswith("kısmen") or v.startswith("kismen"):
            d["kismi"] += 1
        else:
            d["karar"] += 1
    return d
