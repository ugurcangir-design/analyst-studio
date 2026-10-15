"""Kabul Kontrolü — geliştirmesi biten (ANALIZ CHECK) task'ı analist/testçi gözüyle CANLI doğrular.

Analist task key'ini verir → (1) task açıklamasındaki analizden DOĞRULANABİLİR kontrol listesi çıkarılır
(alanlar, zorunluluk/validasyon, butonlar, başarılı/başarısız mesajlar, servis çağrıları, roller, boş durum;
1 AI çağrısı) → (2) agent test ortamında uygulamaya girip HER maddeyi fiilen dener (Playwright MCP — tıklar,
form doldurur, kaydeder, ağ isteğini ve ekran mesajını okur; mevcut canlı-gözlem altyapısı) → (3) her madde
✅ Doğrulandı / ❌ Eksik-hatalı / ⚠ Doğrulanamadı + kanıt; SONUÇ: **Teste hazır** (doğrulanabilir maddelerin
hepsi ✅) ya da **Geliştirmeye geri** (≥1 ❌). Rapor task'a YORUM olarak düşer; Jira durumu DEĞİŞMEZ (analist
karar verir — owner kararı). Test ortamında yazma işlemleri GERÇEKTEN uygulanır (`AI-TEST` öneki, raporda listelenir).

Kanallar: Task Analizi ekranı "Kabul Kontrolü" (iş modu `kabul-kontrol`) · Jira yorumu `/analyst_agent kontrol`.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from .base import (
    MAX_TOKENS_KISA, MAX_TOKENS_COMBINED,
    _api_cagri, _xml_ayir, _metin_sikistir, load_context_filter,
    canli_uygulama_baglami_hazirla, extended_thinking_acik,
)

_MAX_MADDE = 25
DURUMLAR = ("dogrulandi", "eksik", "dogrulanamadi")
_SONUC_ETIKET = {"teste_hazir": "✅ TESTE HAZIR", "geri": "❌ GELİŞTİRMEYE GERİ",
                 "dogrulanamadi": "⚠ DOĞRULANAMADI"}

_LISTE_SISTEM = """# ROL
Kıdemli iş analisti / kabul testçisisin. Geliştirmesi tamamlanmış bir Jira task'ının analizinden, uygulamada
FİİLEN DENENEREK doğrulanabilecek kabul maddelerini çıkarırsın.

# NE ÇIKARILIR (her biri tek, somut, denenebilir madde)
- alan: alan var mı, tipi/formatı, zorunluluk, uzunluk/sınır, varsayılan değer, readonly/disabled davranışı
- buton: buton/aksiyon var mı, tıklayınca ne olur (modal, kayıt, yönlendirme, liste yenileme)
- validasyon: boş/geçersiz/sınır dışı değerde beklenen HATA MESAJI (metin biliniyorsa aynen)
- mesaj: başarılı işlem sonrası beklenen mesaj/durum (toast, satır güncelleme, yönlendirme)
- servis: aksiyonun tetiklediği istek (method/path), beklenen status ve yanıt/istek alanları
- veri: listede/detayda gösterilen verinin doğruluğu (kaydedilen = gösterilen, filtre/sıralama)
- rol: yetkili/yetkisiz kullanıcıda davranış (yalnız test hesabıyla denenebiliyorsa)
- bos_durum: kayıt yokken/hata dönünce ekran davranışı

# KURALLAR
- Yalnız analizde/kabul kriterlerinde YAZAN davranışı madde yap; uydurma, "iyi olurdu" ekleme.
- Ekran/tarayıcıdan DOĞRULANAMAYACAK maddeler (arka plan job, DB içi işlem, dış sistem, zamanlanmış görev,
  yetkisiz rol hesabı yoksa) → "denenebilir": false (raporda 'ekran dışı' listelenir, deneme yapılmaz).
- Her madde için `nasil`: ekranda adım adım nasıl denenir (hangi ekran/alan/değer/buton) + `beklenen`: ne
  görülmeli. Kaynak kriter/bölüm `ref` (örn. AC-3, §5 API).
- En fazla 25 madde; en kritik olanlar (kaydet/güncelle/sil akışı, zorunlu alanlar, servis sözleşmesi) önce.

# ÇIKTI
Yalnız şu blok, içinde JSON dizi:
<kabul_listesi>[{"id":"K-01","tur":"alan","madde":"","nasil":"","beklenen":"","ref":"","denenebilir":true}]</kabul_listesi>"""

_SONUC_FORMAT = """
### KABUL KONTROLÜ ÇIKTI BİÇİMİ (zorunlu)
Doğrulamayı bitirince YALNIZ şu bloğu yaz (blok dışına metin yazma, süreç anlatma):
<kabul_sonuc>{"maddeler":[{"id":"K-01","durum":"dogrulandi|eksik|dogrulanamadi","gozlem":"ne yaptın + ne gördün (kısa)","kanit":"[K: Canlı UI:/route] ya da [K: Network:POST /api/x → 200]","neden":"eksik/doğrulanamadı ise neden"}],
"yazma_islemleri":["oluşturulan/güncellenen/silinen AI-TEST kayıtları"],
"gezilemeyen":["gezilemeyen ekran/akış + neden"],
"genel_not":"analist için 1-3 cümle"}</kabul_sonuc>
KURALLAR: her K-id için TAM BİR kayıt; 'dogrulandi' yalnız beklenen davranışı FİİLEN gördüysen (kanıt zorunlu);
beklenen davranış yoksa/farklıysa 'eksik' (gözlemde farkı yaz); deneyemediysen 'dogrulanamadi' (nedeniyle).
Tahmin/varsayım YASAK — kod/sunucu içini görmeden "muhtemelen çalışıyor" DEME. Şifre/token yazma."""


def _json_dizi(metin: str, tag: str):
    ham = _xml_ayir(metin or "", tag)
    try:
        return json.loads(ham)
    except Exception:
        a, b = ham.find("["), ham.rfind("]")
        if tag == "kabul_sonuc":
            a, b = ham.find("{"), ham.rfind("}")
        if a == -1 or b <= a:
            return None
        try:
            return json.loads(ham[a:b + 1])
        except Exception:
            return None


def _liste_normalize(liste) -> list[dict]:
    out: list[dict] = []
    if not isinstance(liste, list):
        return out
    for i, m in enumerate(liste, 1):
        if not isinstance(m, dict) or not str(m.get("madde") or "").strip():
            continue
        out.append({
            "id": str(m.get("id") or f"K-{i:02d}").strip(),
            "tur": str(m.get("tur") or "").strip(),
            "madde": str(m.get("madde")).strip(),
            "nasil": str(m.get("nasil") or "").strip(),
            "beklenen": str(m.get("beklenen") or "").strip(),
            "ref": str(m.get("ref") or "").strip(),
            "denenebilir": m.get("denenebilir") is not False,
        })
        if len(out) >= _MAX_MADDE:
            break
    return out


# ── 1) Kontrol listesi ───────────────────────────────────────────────────────
def kabul_listesi_cikar(gorev: dict, _ai=None) -> list[dict]:
    ai = _ai or (lambda s, m: _api_cagri(s, m, max_tokens=MAX_TOKENS_KISA, thinking=False))
    icerik = [{"type": "text", "text": f"### Jira Görevi: {gorev.get('key', '')}\n\n**Başlık:** {gorev.get('summary', '')}\n\n"
                                       f"**Açıklama / Analiz:**\n{gorev.get('description', '') or '(açıklama yok)'}"},
              {"type": "text", "text": "Bu task için denenebilir kabul maddelerini çıkar."}]
    return _liste_normalize(_json_dizi(ai(_LISTE_SISTEM, [{"role": "user", "content": icerik}]), "kabul_listesi"))


# ── 2) Canlı doğrulama ───────────────────────────────────────────────────────
def _canli_hedef(gorev: dict) -> str | None:
    """Task Analizi'nin kendi live_app_gorev hedefi; yoksa live_app ana adresi (base) + task'tan hedef."""
    ctx = load_context_filter() or {}
    for k in ("live_app_gorev", "live_app"):
        v = ctx.get(k) or {}
        url = str(v.get("target_url", "")).strip() if isinstance(v, dict) else ""
        if url:
            p = urlparse(url)
            if p.scheme and p.netloc:
                hedef = f"{gorev.get('summary', '')}\n\n{(gorev.get('description') or '')[:3000]}".strip()
                return canli_uygulama_baglami_hazirla(base_url_override=f"{p.scheme}://{p.netloc}", hedef_tarif=hedef)
    return None


def _kontrol_talimati(maddeler: list[dict]) -> str:
    satirlar = []
    for m in maddeler:
        if not m["denenebilir"]:
            continue
        satirlar.append(f"- **{m['id']}** [{m['tur']}] {m['madde']}\n  · Nasıl: {m['nasil'] or '—'}\n  · Beklenen: {m['beklenen'] or '—'}"
                        + (f"\n  · Ref: {m['ref']}" if m["ref"] else ""))
    return (
        "### KABUL KONTROLÜ GÖREVİ (gözlem DEĞİL — DOĞRULAMA)\n"
        "Sen bu task'ın kabul testçisisin. Aşağıdaki maddelerin HER BİRİNİ uygulamada FİİLEN dene ve sonucu "
        "kaydet. Analiz yazma, gereksinim türetme — yalnız 'çalışıyor mu?' sorusuna kanıtla cevap ver.\n"
        "- Yazma işlemlerini (kaydet/güncelle/sil) GERÇEKTEN yap (test ortamı); kayıt adlarında `AI-TEST` öneki.\n"
        "- Validasyon maddelerinde boş/geçersiz değeri gerçekten gönder, çıkan mesajı AYNEN kaydet.\n"
        "- Servis maddelerinde tetiklenen isteği `browser_network_requests` → `browser_network_request` ile "
        "yakala (method/path/status + beklenen alanlar var mı).\n"
        "- Bir maddeyi deneyemiyorsan (ekran bulunamadı, yetki, veri yok, hata) 'dogrulanamadi' + neden; "
        "tahmin etme.\n"
        "- Kendi oluşturduğun AI-TEST kayıtlarını mümkünse sonunda sil (yalnız kendininkileri).\n\n"
        "### KONTROL MADDELERİ\n" + "\n".join(satirlar) + "\n" + _SONUC_FORMAT
    )


def _sonuc_normalize(ham, maddeler: list[dict]) -> dict:
    d = ham if isinstance(ham, dict) else {}
    gelen = {str(m.get("id") or "").strip(): m for m in (d.get("maddeler") or []) if isinstance(m, dict)}
    out = []
    for m in maddeler:
        if not m["denenebilir"]:
            out.append({**m, "durum": "ekran_disi", "gozlem": "", "kanit": "", "neden": "Ekrandan doğrulanamaz (arka plan/DB/dış sistem)."})
            continue
        g = gelen.get(m["id"]) or {}
        durum = str(g.get("durum") or "").strip().lower()
        if durum not in DURUMLAR:
            durum = "dogrulanamadi"
        out.append({**m, "durum": durum, "gozlem": str(g.get("gozlem") or "").strip(),
                    "kanit": str(g.get("kanit") or "").strip(),
                    "neden": str(g.get("neden") or ("Agent bu madde için sonuç bildirmedi." if not g else "")).strip()})
    sayim = {k: sum(1 for x in out if x["durum"] == k) for k in (*DURUMLAR, "ekran_disi")}
    if sayim["eksik"]:
        sonuc = "geri"
    elif sayim["dogrulandi"] and not sayim["dogrulanamadi"]:
        sonuc = "teste_hazir"
    elif sayim["dogrulandi"] and sayim["dogrulanamadi"]:
        sonuc = "teste_hazir_kismi"
    else:
        sonuc = "dogrulanamadi"
    return {"maddeler": out, "sayim": sayim, "sonuc": sonuc,
            "yazma_islemleri": [str(x) for x in (d.get("yazma_islemleri") or [])],
            "gezilemeyen": [str(x) for x in (d.get("gezilemeyen") or [])],
            "genel_not": str(d.get("genel_not") or "").strip()}


def canli_dogrula(gorev: dict, maddeler: list[dict], _ai=None) -> dict:
    """Canlı hedef yoksa tüm denenebilir maddeler 'dogrulanamadi' (net neden) — hata fırlatmaz."""
    canli = _canli_hedef(gorev)
    if not canli:
        return _sonuc_normalize({"maddeler": [{"id": m["id"], "durum": "dogrulanamadi",
                                               "neden": "Canlı uygulama hedefi tanımlı değil (Bağlam Filtresi → Task canlı uygulama hedefi)."}
                                              for m in maddeler if m["denenebilir"]],
                                 "genel_not": "Canlı doğrulama yapılamadı: Task canlı uygulama hedefi girilmemiş."}, maddeler)
    sistem = ("Kıdemli kabul testçisisin. Verilen uygulamada, verilen kontrol maddelerini tarayıcı araçlarıyla "
              "fiilen deneyip her biri için kanıtlı sonuç üretirsin. Analiz yazmazsın; yalnız doğrularsın.")
    icerik = [{"type": "text", "text": canli},
              {"type": "text", "text": f"### Task: {gorev.get('key', '')} — {gorev.get('summary', '')}"},
              {"type": "text", "text": _kontrol_talimati(maddeler)}]
    ai = _ai or (lambda s, m: _api_cagri(s, m, max_tokens=MAX_TOKENS_COMBINED, thinking=extended_thinking_acik(),
                                         onbellek=False, canli_uygulama_kapsami="gorev"))
    yanit = _metin_sikistir(ai(sistem, [{"role": "user", "content": icerik}]))
    return _sonuc_normalize(_json_dizi(yanit, "kabul_sonuc"), maddeler)


# ── 3) Rapor ─────────────────────────────────────────────────────────────────
_IKON = {"dogrulandi": "✅", "eksik": "❌", "dogrulanamadi": "⚠", "ekran_disi": "◻"}


def rapor_md(gorev: dict, sonuc: dict) -> str:
    s = sonuc["sayim"]
    etiket = _SONUC_ETIKET.get(sonuc["sonuc"], "✅ TESTE HAZIR (kısmi — doğrulanamayan maddeler var)")
    sat = [f"## 🤖 Kabul Kontrolü — {gorev.get('key', '')}", "",
           f"**Sonuç: {etiket}** · ✅ {s['dogrulandi']} doğrulandı · ❌ {s['eksik']} eksik · "
           f"⚠ {s['dogrulanamadi']} doğrulanamadı · ◻ {s['ekran_disi']} ekran dışı", ""]
    if sonuc["genel_not"]:
        sat += [sonuc["genel_not"], ""]
    sat += ["| # | Madde | Durum | Gözlem / Kanıt |", "|---|---|---|---|"]
    for m in sonuc["maddeler"]:
        g = m["gozlem"] or m["neden"]
        if m["kanit"]:
            g = f"{g} {m['kanit']}".strip()
        sat.append(f"| {m['id']} | {m['madde']}{' _(' + m['ref'] + ')_' if m['ref'] else ''} | "
                   f"{_IKON[m['durum']]} {m['durum'].replace('_', ' ')} | {g.replace('|', '/')} |")
    eksik = [m for m in sonuc["maddeler"] if m["durum"] == "eksik"]
    if eksik:
        sat += ["", "### Geliştirmeye dönecek maddeler"]
        sat += [f"- **{m['id']}** {m['madde']} — beklenen: {m['beklenen'] or '—'} · gözlenen: {m['gozlem'] or m['neden']}" for m in eksik]
    if sonuc["yazma_islemleri"]:
        sat += ["", "### Test ortamında yapılan yazma işlemleri", *[f"- {x}" for x in sonuc["yazma_islemleri"]]]
    if sonuc["gezilemeyen"]:
        sat += ["", "### Gezilemeyen", *[f"- {x}" for x in sonuc["gezilemeyen"]]]
    sat += ["", "_Durum değiştirilmedi — teste iletme / geri gönderme kararı analistindir._"]
    return "\n".join(sat)


def kabul_kontrolu(gorev: dict) -> dict:
    """Tam akış: liste → canlı doğrulama → rapor. {markdown, sonuc, maddeler, sayim}."""
    maddeler = kabul_listesi_cikar(gorev)
    if not maddeler:
        md = (f"## 🤖 Kabul Kontrolü — {gorev.get('key', '')}\n\n**Sonuç: ⚠ DOĞRULANAMADI** — task açıklamasından "
              "denenebilir kabul maddesi çıkarılamadı (analiz/kabul kriteri yok ya da çok kısa).")
        return {"markdown": md, "sonuc": "dogrulanamadi", "maddeler": [], "sayim": {}}
    sonuc = canli_dogrula(gorev, maddeler)
    return {"markdown": rapor_md(gorev, sonuc), "sonuc": sonuc["sonuc"], "maddeler": sonuc["maddeler"],
            "sayim": sonuc["sayim"], "yazma_islemleri": sonuc["yazma_islemleri"]}


def _kisa(metin: str, n: int) -> str:
    metin = re.sub(r"\s+", " ", metin or "").strip()
    return metin if len(metin) <= n else metin[:n - 1] + "…"
