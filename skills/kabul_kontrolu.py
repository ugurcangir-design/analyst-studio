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
    canli_uygulama_baglami_hazirla, extended_thinking_acik, asama_ayarla,
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
- KABUL KRİTERLERİ BİRİNCİLDİR: task'ta açık kabul kriterleri (AC-1…, "Kabul Kriterleri" bölümü, numaralı kriter
  listesi) varsa HER kriter için en az bir madde çıkar ve `ref` alanına o kriterin kimliğini (AC-3 gibi) yaz —
  hiçbir kriter atlanmaz; rapor kriter bazında sayılır (toplam / karşılanan / doğrulanamayan).
- BE task'ı ise kriterler ENDPOINT üzerinden doğrulanır: ilgili ekrandaki aksiyonla tetiklenen istek (method/path),
  status, istek/yanıt alanları, hata kodu (ör. silme engeli → 409) → `tur:"servis"`. GET/POST/PUT/DELETE'in hepsi
  test ortamında kullanılabilir. FE task'ı ise ekran davranışı (alan/buton/mesaj/liste) → ilgili türler.
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
"bulgular":["öne çıkan bulgu — kanıtlı, tek cümle (ör. 'Market atanmış grubun silinmesi HTTP 409 ile engelleniyor [K: Network:DELETE /x → 409]')"],
"acik_konular":["netleştirilmesi gereken konu — doğrulanamayan davranış, doküman↔uygulama çelişkisi, yetki senaryosu"],
"yazma_islemleri":["oluşturulan/güncellenen/silinen AI-TEST kayıtları"],
"gezilemeyen":["gezilemeyen ekran/akış + neden"],
"genel_not":"GENEL DEĞERLENDİRME: 2-4 cümle — kapsamın ne kadarı doğrulandı, ana davranışlar çalışıyor mu, en önemli eksik/belirsizlik"}</kabul_sonuc>
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
def _ilgili_tasklar(gorev: dict) -> list[dict]:
    """`gorev_getir` çıktısındaki bağlı task'lar (issuelinks) — BE task'ı FE ekranı üzerinden doğrulanırken
    hedef ekranı ve 'İlgili FE/BE Task' satırını buradan alırız."""
    out = []
    for b in (gorev.get("baglantililar") or []):
        if isinstance(b, dict) and b.get("key"):
            out.append({"key": str(b["key"]), "summary": str(b.get("summary") or ""),
                        "katman": str(b.get("katman") or ""), "iliski": str(b.get("iliski") or "")})
    return out[:8]


def _ilgili_metni(gorev: dict) -> str:
    sat = [f"- {t['key']} ({t['katman'].upper() or 'ilişkili'}; {t['iliski']}): {t['summary']}".replace("; )", ")")
           for t in _ilgili_tasklar(gorev)]
    return ("\n**İlgili task'lar:**\n" + "\n".join(sat) + "\n") if sat else ""


def kabul_listesi_cikar(gorev: dict, _ai=None, talimat: str = "") -> list[dict]:
    asama_ayarla("kabul:liste")
    ai = _ai or (lambda s, m: _api_cagri(s, m, max_tokens=MAX_TOKENS_KISA, thinking=False))
    icerik = [{"type": "text", "text": f"### Jira Görevi: {gorev.get('key', '')}\n\n**Başlık:** {gorev.get('summary', '')}\n"
                                       f"{_ilgili_metni(gorev)}\n"
                                       f"**Açıklama / Analiz:**\n{gorev.get('description', '') or '(açıklama yok)'}"}]
    if (talimat or "").strip():
        icerik.append({"type": "text", "text": f"### Analist talimatı (ortam/odak)\n{talimat.strip()}"})
    icerik.append({"type": "text", "text": "Bu task için denenebilir kabul maddelerini çıkar (kabul kriterleri birincil)."})
    return _liste_normalize(_json_dizi(ai(_LISTE_SISTEM, [{"role": "user", "content": icerik}]), "kabul_listesi"))


# ── 2) Canlı doğrulama ───────────────────────────────────────────────────────
_URL_DESEN = re.compile(r"https?://[^\s<>\"')\]]+")


def _talimat_url(talimat: str) -> str:
    m = _URL_DESEN.search(talimat or "")
    return m.group(0).rstrip(".,;") if m else ""


def _ortam_adi(url: str) -> str:
    """Rapor başlığındaki 'Ortam' — host adından kaba sınıf (DEV/UAT/TEST/PROD) + host."""
    host = urlparse(url).netloc if url else ""
    h = host.lower()
    sinif = next((ad for ip, ad in (("dev", "DEV"), ("uat", "UAT"), ("test", "TEST"), ("stag", "STAGING"), ("prod", "PROD"))
                  if ip in h), "")
    return f"{sinif} ({host})" if sinif and host else (host or "—")


def _hedef_url(talimat: str = "") -> str:
    """Analist talimatında URL varsa O ekran (doğrudan); yoksa live_app_gorev → live_app hedefi."""
    u = _talimat_url(talimat)
    if u:
        return u
    ctx = load_context_filter() or {}
    for k in ("live_app_gorev", "live_app"):
        v = ctx.get(k) or {}
        url = str(v.get("target_url", "")).strip() if isinstance(v, dict) else ""
        if url:
            p = urlparse(url)
            if p.scheme and p.netloc:
                return url
    return ""


def _canli_hedef(gorev: dict, talimat: str = "") -> str | None:
    """Canlı görev bloğu: talimat URL'i varsa doğrudan o ekran, yoksa bağlam filtresi hedefinin ANA adresi (base)
    + task'tan türetilen hedef tarifi (ilgili FE/BE task'lar ve analist talimatı dahil)."""
    url = _hedef_url(talimat)
    if not url:
        return None
    p = urlparse(url)
    base = url if _talimat_url(talimat) else f"{p.scheme}://{p.netloc}"
    hedef = (f"{gorev.get('summary', '')}{_ilgili_metni(gorev)}"
             + (f"\nAnalist talimatı: {talimat.strip()}\n" if (talimat or '').strip() else "")
             + f"\n{(gorev.get('description') or '')[:3000]}").strip()
    return canli_uygulama_baglami_hazirla(base_url_override=base, hedef_tarif=hedef)


def _kontrol_talimati(maddeler: list[dict], talimat: str = "") -> str:
    satirlar = []
    for m in maddeler:
        if not m["denenebilir"]:
            continue
        satirlar.append(f"- **{m['id']}** [{m['tur']}] {m['madde']}\n  · Nasıl: {m['nasil'] or '—'}\n  · Beklenen: {m['beklenen'] or '—'}"
                        + (f"\n  · Ref: {m['ref']}" if m["ref"] else ""))
    return (
        "### KABUL KONTROLÜ GÖREVİ (gözlem DEĞİL — DOĞRULAMA)\n"
        "Sen bu task'ın kabul testçisisin. Yeni task önerme, çok başlıklı analiz yazma, gereksinim türetme — "
        "TEK çıktı: task'taki isterler/kabul kriterleri bu ortamdaki geliştirme tarafından KARŞILANIYOR MU? "
        "Aşağıdaki maddelerin HER BİRİNİ uygulamada FİİLEN dene ve kanıtla cevapla.\n"
        "- BE isterlerini ENDPOINT üzerinden doğrula: ilgili ekrandaki aksiyonu yap, tetiklenen isteği "
        "`browser_network_requests` → `browser_network_request` ile yakala (method/path/status/istek-yanıt alanları, "
        "hata kodu). FE isterlerini ekran davranışından doğrula. Ekran + endpoint BİRLİKTE incelenir.\n"
        "- GET/POST/PUT/DELETE'in HEPSİNİ bu ortamda kullanabilirsin (test ortamı); yıkıcı işlemi yalnız kendi "
        "AI-TEST kaydında yap.\n"
        + (f"- ANALİST TALİMATI (öncelikli ortam/odak): {talimat.strip()}\n" if (talimat or '').strip() else "")
        + "- Yazma işlemlerini (kaydet/güncelle/sil) GERÇEKTEN yap (test ortamı); kayıt adlarında `AI-TEST` öneki.\n"
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
    kriterler = _kriterler(out)
    return {"maddeler": out, "sayim": sayim, "sonuc": sonuc,
            "kriterler": kriterler,
            "kriter_sayim": {k: sum(1 for x in kriterler if x["durum"] == k) for k in (*DURUMLAR, "ekran_disi")},
            "bulgular": [str(x).strip() for x in (d.get("bulgular") or []) if str(x).strip()][:10],
            "acik_konular": [str(x).strip() for x in (d.get("acik_konular") or []) if str(x).strip()][:10],
            "yazma_islemleri": [str(x) for x in (d.get("yazma_islemleri") or [])],
            "gezilemeyen": [str(x) for x in (d.get("gezilemeyen") or [])],
            "genel_not": str(d.get("genel_not") or "").strip()}


_KRITER_ID = re.compile(r"\b(?:AC|KK|KR|K)-?\s?(\d{1,3})\b", re.I)


def _kriter_anahtar(m: dict) -> str:
    """Maddenin bağlı olduğu kabul kriteri (ref: 'AC-3' / '§11 AC-3' → 'AC-3'); ref'siz madde kendi kriteridir."""
    r = _KRITER_ID.search(m.get("ref") or "")
    return f"AC-{int(r.group(1))}" if r else m["id"]


def _kriterler(maddeler: list[dict]) -> list[dict]:
    """Madde sonuçlarını KABUL KRİTERİ düzeyine toplar (analist raporu kriter sayar: toplam/karşılanan/
    doğrulanamayan). Kriter durumu: ≥1 eksik → eksik · denenebilir maddelerin hepsi doğrulandı → dogrulandi ·
    yalnız ekran dışı → ekran_disi · aksi → dogrulanamadi."""
    grup: dict[str, list[dict]] = {}
    for m in maddeler:
        grup.setdefault(_kriter_anahtar(m), []).append(m)
    out = []
    for k, ms in grup.items():
        durumlar = [m["durum"] for m in ms]
        if "eksik" in durumlar:
            d = "eksik"
        elif all(x == "ekran_disi" for x in durumlar):
            d = "ekran_disi"
        elif all(x in ("dogrulandi", "ekran_disi") for x in durumlar):
            d = "dogrulandi"
        else:
            d = "dogrulanamadi"
        out.append({"kriter": k, "durum": d, "madde_idler": [m["id"] for m in ms],
                    "baslik": ms[0]["madde"] if len(ms) == 1 else f"{len(ms)} madde"})
    return out


def canli_dogrula(gorev: dict, maddeler: list[dict], _ai=None, talimat: str = "") -> dict:
    """Canlı hedef yoksa tüm denenebilir maddeler 'dogrulanamadi' (net neden) — hata fırlatmaz."""
    canli = _canli_hedef(gorev, talimat)
    if not canli:
        return _sonuc_normalize({"maddeler": [{"id": m["id"], "durum": "dogrulanamadi",
                                               "neden": "Canlı uygulama hedefi tanımlı değil (Bağlam Filtresi → Task canlı uygulama hedefi)."}
                                              for m in maddeler if m["denenebilir"]],
                                 "genel_not": "Canlı doğrulama yapılamadı: Task canlı uygulama hedefi girilmemiş."}, maddeler)
    sistem = ("Kıdemli kabul testçisisin. Verilen uygulamada, verilen kontrol maddelerini tarayıcı araçlarıyla "
              "fiilen deneyip her biri için kanıtlı sonuç üretirsin. Analiz yazmazsın; yalnız doğrularsın.")
    icerik = [{"type": "text", "text": canli},
              {"type": "text", "text": f"### Task: {gorev.get('key', '')} — {gorev.get('summary', '')}"},
              {"type": "text", "text": _kontrol_talimati(maddeler, talimat)}]
    asama_ayarla("kabul:dogrula")
    ai = _ai or (lambda s, m: _api_cagri(s, m, max_tokens=MAX_TOKENS_COMBINED, thinking=extended_thinking_acik(),
                                         onbellek=False, canli_uygulama_kapsami="gorev"))
    yanit = _metin_sikistir(ai(sistem, [{"role": "user", "content": icerik}]))
    return _sonuc_normalize(_json_dizi(yanit, "kabul_sonuc"), maddeler)


# ── 3) Rapor ─────────────────────────────────────────────────────────────────
_IKON = {"dogrulandi": "✅", "eksik": "❌", "dogrulanamadi": "⚠", "ekran_disi": "◻"}


def rapor_md(gorev: dict, sonuc: dict, ortam: str = "") -> str:
    """Analist rapor yapısı (ekip promptundan): başlık bloğu (Task · Konu · Ortam · İlgili task) → Doğrulama Sonucu
    (KRİTER bazlı sayım) → Genel değerlendirme → Öne çıkan bulgular → kriter/madde tablosu → Geliştirmeye dönecek
    maddeler → Netleştirilmesi gereken konular → yazma işlemleri → gezilemeyen → Sonuç cümlesi (doğrulanamayan
    varsa 'tüm kapsam doğrulandı sayılmaz'). Jira durumu değişmez notu."""
    s = sonuc["sayim"]
    ks = sonuc.get("kriter_sayim") or s
    kriterler = sonuc.get("kriterler") or []
    acik = sonuc.get("acik_konular") or []
    etiket = _SONUC_ETIKET.get(sonuc["sonuc"], "✅ TESTE HAZIR (kısmi — doğrulanamayan maddeler var)")
    ilgili = ", ".join(f"{t['key']} ({t['katman'].upper()})" if t["katman"] else t["key"] for t in _ilgili_tasklar(gorev)) or "—"
    key = gorev.get("key", "")
    sat = [f"## 🤖 Kabul Kontrolü — {key}", "",
           f"**Task:** {key} · **Konu:** {gorev.get('summary', '')} · **Ortam:** {ortam or '—'} · **İlgili task:** {ilgili}", "",
           f"**Sonuç: {etiket}**", "",
           "### Doğrulama Sonucu",
           f"- Toplam kabul kriteri: {len(kriterler)}",
           f"- Karşılanan: {ks.get('dogrulandi', 0)}",
           f"- Karşılanmayan: {ks.get('eksik', 0)}",
           f"- Doğrulanamayan: {ks.get('dogrulanamadi', 0)}"
           + (f" ({', '.join(k['kriter'] for k in kriterler if k['durum'] == 'dogrulanamadi')})" if ks.get('dogrulanamadi') else ""),
           f"- Ekran dışı (denenmedi): {ks.get('ekran_disi', 0)}",
           f"- Netleştirilmesi gereken konu: {len(acik)}", ""]
    if sonuc["genel_not"]:
        sat += [f"**Genel değerlendirme:** {sonuc['genel_not']}", ""]
    if sonuc.get("bulgular"):
        sat += ["### Öne çıkan bulgular", *[f"- {b}" for b in sonuc["bulgular"]], ""]
    sat += ["### Kriter bazında sonuç", "| Kriter | Madde | Durum | Gözlem / Kanıt |", "|---|---|---|---|"]
    for m in sonuc["maddeler"]:
        g = m["gozlem"] or m["neden"]
        if m["kanit"]:
            g = f"{g} {m['kanit']}".strip()
        sat.append(f"| {_kriter_anahtar(m)} | {m['id']} · {m['madde']} | "
                   f"{_IKON[m['durum']]} {m['durum'].replace('_', ' ')} | {g.replace('|', '/')} |")
    eksik = [m for m in sonuc["maddeler"] if m["durum"] == "eksik"]
    if eksik:
        sat += ["", "### Geliştirmeye dönecek maddeler"]
        sat += [f"- **{m['id']}** ({_kriter_anahtar(m)}) {m['madde']} — beklenen: {m['beklenen'] or '—'} · gözlenen: {m['gozlem'] or m['neden']}" for m in eksik]
    if acik:
        sat += ["", "### Netleştirilmesi gereken konular", *[f"- {x}" for x in acik]]
    if sonuc["yazma_islemleri"]:
        sat += ["", "### Test ortamında yapılan yazma işlemleri", *[f"- {x}" for x in sonuc["yazma_islemleri"]]]
    if sonuc["gezilemeyen"]:
        sat += ["", "### Gezilemeyen", *[f"- {x}" for x in sonuc["gezilemeyen"]]]
    # Sonuç cümlesi — analist formatı: karşılanan sayısı + doğrulanamayan varsa kapsam uyarısı
    cum = [f"{ks.get('dogrulandi', 0)} kabul kriteri karşılanmıştır."]
    if ks.get("eksik"):
        cum.append(f"{ks['eksik']} kriter karşılanmamıştır → geliştirmeye geri.")
    if ks.get("dogrulanamadi"):
        dk = ", ".join(k["kriter"] for k in kriterler if k["durum"] == "dogrulanamadi")
        cum.append(f"{dk} ile doğrulanamayan senaryolar tamamlanmadan tüm kapsamın doğrulandığı kabul edilmemelidir.")
    sat += ["", f"**Sonuç:** {' '.join(cum)}", "",
            "_Durum değiştirilmedi — teste iletme / geri gönderme kararı analistindir._"]
    return "\n".join(sat)


def kabul_kontrolu(gorev: dict, talimat: str = "") -> dict:
    """Tam akış: liste → canlı doğrulama → rapor. {markdown, sonuc, maddeler, sayim, kriter_sayim, ...}.
    `talimat`: analistin opsiyonel ortam/ekran URL'i + odak notu (UI prompt'u · köprü `kontrol <talimat>`)."""
    maddeler = kabul_listesi_cikar(gorev, talimat=talimat)
    if not maddeler:
        md = (f"## 🤖 Kabul Kontrolü — {gorev.get('key', '')}\n\n**Sonuç: ⚠ DOĞRULANAMADI** — task açıklamasından "
              "denenebilir kabul maddesi çıkarılamadı (analiz/kabul kriteri yok ya da çok kısa).")
        return {"markdown": md, "sonuc": "dogrulanamadi", "maddeler": [], "sayim": {}}
    sonuc = canli_dogrula(gorev, maddeler, talimat=talimat)
    ortam = _ortam_adi(_hedef_url(talimat))
    return {"markdown": rapor_md(gorev, sonuc, ortam), "sonuc": sonuc["sonuc"], "maddeler": sonuc["maddeler"],
            "sayim": sonuc["sayim"], "kriter_sayim": sonuc.get("kriter_sayim", {}), "kriterler": sonuc.get("kriterler", []),
            "bulgular": sonuc.get("bulgular", []), "acik_konular": sonuc.get("acik_konular", []),
            "yazma_islemleri": sonuc["yazma_islemleri"], "ortam": ortam}


def _kisa(metin: str, n: int) -> str:
    metin = re.sub(r"\s+", " ", metin or "").strip()
    return metin if len(metin) <= n else metin[:n - 1] + "…"
