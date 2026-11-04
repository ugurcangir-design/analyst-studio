"""Otomatik mockup — Faz 2: YAMA tabanlı üretim (gerçek ekran + değişiklik).

Mockup = `ekran_yakala` baseline'ı (gerçek HTML/CSS) + modelin ürettiği KÜÇÜK yama listesi. Model ekranı çizmez; yalnız
`<mockup_yama>` JSON döner (add/remove/replace/disable/enable/text/attr + CSS selector + AC etiketi + not). Yama tarayıcı
tarafında uygulanır (gömülü JS: `document.querySelectorAll` → tam selector desteği, cssselect bağımlılığı yok; iframe
`allow-scripts` ve headless PNG'de de çalışır) ve değişen öğeler "redline" ile işaretlenir (sağ altta legend, R tuşu
açar/kapar). Ekran hiç yoksa (yeni ekran) en yakın ekranın baseline'ı KABUK olarak kullanılır: içerik alanı boşaltılır,
model yalnız içerik alanını `replace` eder (menü/üst bar/CSS gerçek üründen).
Tek çağrı, yardımcı katman (Sonnet), girdi ≈ analizin ilgili bölümleri (≤12k) + sadeleştirilmiş DOM (≤60k kc).
Çıktı: `output/gorev-mockup.html` (+ `.png` headless render, `.json` meta) — Task Analizi mockup paneli aynı dosyayı okur.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from .base import OUTPUT_DIR, _api_cagri, _kaydet, _xml_ayir, asama_ayarla, logger
from . import ekran_yakala as EY

GOREV_MOCKUP_DOSYA = "gorev-mockup.html"
SUREC_MOCKUP_DOSYA = "mockup.html"
_OPLAR = {"add", "remove", "replace", "disable", "enable", "text", "attr", "style"}
_KONUMLAR = {"before", "after", "prepend", "append"}
_AZAMI_YAMA = 40
_ILGILI_BASLIK = re.compile(
    r"(amaç|hedef|iş gereksinim|gereksinim|ekran|bileşen|arayüz|ui|ux|frontend|fe |görünüm|etkileşim|akış|"
    r"hata yönetimi|boş durum|kabul kriter|kapsam|değişiklik|sorun|çözüm)", re.I)


def _max_tokens() -> int:
    try:
        return int(os.getenv("MOCKUP_YAMA_MAX_TOKENS", "6000"))
    except (TypeError, ValueError):
        return 6000


# ── analizden ilgili bölümler ───────────────────────────────────────────────────────────────────────────
def ilgili_bolumler(analiz_md: str, azami_kc: int = 12000) -> str:
    """Analizin UI'ya dokunan bölümlerini (başlık eşleşmesi) toplar; eşleşme yoksa baştan kırpar."""
    md = (analiz_md or "").strip()
    if not md:
        return ""
    parcalar = re.split(r"(?m)^(?=#{1,3} )", md)
    secilen = [p for p in parcalar if p.startswith("#") and _ILGILI_BASLIK.search(p.splitlines()[0])]
    metin = "\n".join(secilen) if secilen else md
    return metin[:azami_kc] + ("\n…(kırpıldı)" if len(metin) > azami_kc else "")


# ── prompt ──────────────────────────────────────────────────────────────────────────────────────────────
_SISTEM = """\
Deneyimli UI/UX tasarımcısı ve frontend geliştiricisin. Sana bir ekranın GERÇEK (sadeleştirilmiş) HTML'i ve o ekranda
yapılacak değişikliği anlatan analiz verilecek. Ekranı YENİDEN ÇİZMEZSİN; yalnız analizin gerektirdiği DEĞİŞİKLİKLERİ
küçük bir yama listesi olarak üretirsin. Yama tarayıcıda `document.querySelectorAll(selector)` ile uygulanır.

ÇIKTI — yalnız şu blok, başka metin yok:
<mockup_yama>{"ozet":"1-2 cümle: ne değişti","yamalar":[{"op":"add|remove|replace|disable|enable|text|attr|style",
"selector":"CSS selector (gerçek HTML'deki class/aria-label/metin yapısından; :has(), :nth-child, [aria-label=...] serbest)",
"konum":"before|after|prepend|append (yalnız add)","html":"eklenecek/yerine konacak HTML (add/replace)","text":"yeni metin (text)",
"attr":{"ad":"değer"} (attr; değer null → kaldır),"style":"css (style)","ac":"AC-n (varsa)","not":"neden (kısa)"}]}</mockup_yama>

KURALLAR:
- GERÇEK YAPIYI KULLAN: yeni öğe eklerken mevcut benzer öğenin class'larını ve markup desenini kopyala (aynı buton/alan/tablo
  stili) — ürünün parçası gibi görünsün. Yeni CSS yazma; gerekiyorsa `style` op ile küçük inline stil.
- SELECTOR KESİN VE DAR olsun: verilen HTML'de gerçekten var olan class/aria-label/metin yapısına dayan. Tablo satırı
  bazlı kural (ör. 'eşlenmiş satırda düğme pasif') için satırı ayırt eden GERÇEK ipucunu kullan (ör. `tr:has(a[href*="open="])`).
  Örnek satır sayısı kırpılmıştır; selector TÜM satırlara uygulanır.
- disable: `disabled` + `aria-disabled="true"` uygulanır; attr ile title/tooltip da ekle. remove: öğeyi gizler (DOM'dan silmez).
- Analizdeki her görünür değişikliğe en az bir yama; kabul kriteri varsa `ac` ile bağla. Analizde olmayan şeyi ekleme.
- Gerçekçi veri: yeni sütun/alan için örnek değerler gerçek satırların verisiyle uyumlu olsun; sihirli sayılar yok.
- En fazla 40 yama. JSON geçerli olsun (çift tırnak, kaçış).\
"""

_SISTEM_YENI_EKRAN = """\
Deneyimli UI/UX tasarımcısı ve frontend geliştiricisin. Sana ürünün MEVCUT bir ekranının GERÇEK (sadeleştirilmiş) HTML'i
KABUK olarak verilecek (yan menü, üst bar, gerçek CSS class'ları) ve analiz YENİ bir ekran istiyor. Kabuğu koru; yalnız içerik
alanını (`{icerik_selector}`) yeni ekranla DEĞİŞTİR. Yeni ekranı kabuktaki component desenleriyle (aynı kart/tablo/form/buton
class'ları) kur — yeni CSS yazma, küçük inline stil serbest.

ÇIKTI — yalnız şu blok:
<mockup_yama>{"ozet":"…","yamalar":[{"op":"replace","selector":"{icerik_selector}","html":"<yeni içerik>","not":"…"},
… (gerekirse yan menüye `add` ile yeni menü maddesi; mevcut desenle)]}</mockup_yama>
Analizdeki alanlar/aksiyonlar/durumlar eksiksiz görünsün; kabul kriterleri varsa `ac` ile bağla; gerçekçi örnek veri kullan.\
"""


def _icerik_selector(html: str) -> str:
    for s in ("main", "[role=main]", "#__next > div > div:last-child", "body > div:last-child"):
        if re.search(r"<main\b", html) if s == "main" else (s in html or s.startswith("#") or s.startswith("body")):
            return s
    return "main"


# ── yama üretimi (tek AI çağrısı) ──────────────────────────────────────────────────────────────────────
def yama_uret(analiz_md: str, baseline_html: str, iste: str = "", baslik: str = "", yeni_ekran: bool = False,
              _ai=None) -> dict:
    """Dönen: {ok, ozet, yamalar[], ham, neden}. Geçersiz op/selector'lar elenir; hiç yama kalmazsa ok=False."""
    dom = EY.sadelestir(baseline_html)
    icerik_sel = _icerik_selector(baseline_html)
    sistem = _SISTEM_YENI_EKRAN.replace("{icerik_selector}", icerik_sel) if yeni_ekran else _SISTEM
    parcalar = []
    if (baslik or "").strip():
        parcalar.append({"type": "text", "text": f"### Görev\n{baslik.strip()}"})
    bol = ilgili_bolumler(analiz_md)
    if bol:
        parcalar.append({"type": "text", "text": f"### Analiz (ilgili bölümler)\n\n{bol}"})
    if (iste or "").strip():
        parcalar.append({"type": "text", "text": f"### Ek iste / ekran açıklaması\n{iste.strip()[:3000]}"})
    parcalar.append({"type": "text", "text": ("### MEVCUT EKRAN HTML (sadeleştirilmiş — kabuk)" if yeni_ekran
                                               else "### MEVCUT EKRAN HTML (sadeleştirilmiş)") + "\n```html\n" + dom + "\n```"})
    asama_ayarla("mockup:yama")
    ai = _ai or (lambda s, m: _api_cagri(s, m, max_tokens=_max_tokens(), thinking=False, katman="yardimci"))
    try:
        ham = ai(sistem, [{"role": "user", "content": parcalar}])
    except Exception as e:
        return {"ok": False, "ozet": "", "yamalar": [], "ham": "", "neden": f"AI çağrısı başarısız: {e}"}
    yamalar, ozet, neden = _yama_ayikla(ham)
    if not yamalar:
        return {"ok": False, "ozet": ozet, "yamalar": [], "ham": ham, "neden": neden or "Geçerli yama üretilmedi."}
    return {"ok": True, "ozet": ozet, "yamalar": yamalar, "ham": ham, "neden": ""}


def _yama_ayikla(ham: str) -> tuple[list, str, str]:
    metin = _xml_ayir(ham or "", "mockup_yama") or (ham or "")
    metin = re.sub(r"^```(?:json)?\s*|\s*```$", "", metin.strip())
    try:
        veri = json.loads(metin)
    except Exception:
        m = re.search(r"\{.*\}", metin, re.S)
        try:
            veri = json.loads(m.group(0)) if m else {}
        except Exception:
            return [], "", "Yama JSON'u ayrıştırılamadı."
    if isinstance(veri, list):
        veri = {"yamalar": veri}
    yamalar = []
    for y in (veri.get("yamalar") or [])[:_AZAMI_YAMA]:
        if not isinstance(y, dict):
            continue
        op = str(y.get("op") or "").strip().lower()
        sel = str(y.get("selector") or "").strip()
        if op not in _OPLAR or not sel:
            continue
        if op in ("add", "replace") and not str(y.get("html") or "").strip():
            continue
        if op == "text" and y.get("text") is None:
            continue
        if op == "attr" and not isinstance(y.get("attr"), dict):
            continue
        if op == "style" and not str(y.get("style") or "").strip():
            continue
        if op == "add":
            y["konum"] = y.get("konum") if y.get("konum") in _KONUMLAR else "after"
        yamalar.append({k: y[k] for k in ("op", "selector", "konum", "html", "text", "attr", "style", "ac", "not") if k in y})
    return yamalar, str(veri.get("ozet") or "")[:400], ""


# ── statik ön-kontrol (0 token): selector'daki id/class/aria ipuçları baseline'da var mı ─────────────────
_TOKEN = re.compile(r"[#.]([A-Za-z0-9_-]+)|\[aria-label\*?=\"?([^\]\"]+)\"?\]|\[href\*=\"?([^\]\"]+)\"?\]")


def selector_on_kontrol(yamalar: list, baseline_html: str) -> list[dict]:
    """Her yama için {idx, selector, suphe:bool, eksik:[token]} — tarayıcı uygulamadan önce muhtemelen eşleşmeyecekleri işaretler."""
    rapor = []
    for i, y in enumerate(yamalar):
        eksik = []
        for m in _TOKEN.finditer(y.get("selector", "")):
            tok = next(t for t in m.groups() if t)
            if tok not in baseline_html:
                eksik.append(tok)
        rapor.append({"idx": i, "selector": y.get("selector", ""), "suphe": bool(eksik), "eksik": eksik})
    return rapor


# ── mockup HTML (baseline + gömülü yama + redline) ───────────────────────────────────────────────────────
_UYGULAYICI_JS = r"""
(function(){
  var Y = window.__MOCKUP_YAMA || {yamalar:[]}; var rapor = []; var sira = 0;
  function isaretle(el, tur, y, ilk){ if(!el || !el.setAttribute) return; el.setAttribute('data-mockup', tur);
    // numara rozeti yama başına YALNIZ ilk eşleşen öğede (ikon kolonlarında her satıra rozet basmak okunmazlık yaratıyordu)
    if(ilk && !y.__no){ y.__no = ++sira; } if(ilk && !el.hasAttribute('data-mockup-no')){ el.setAttribute('data-mockup-no', String(y.__no)); el.setAttribute('data-mockup-not', (y.ac?y.ac+' · ':'')+(y['not']||'')); } }
  function parca(html){ var t=document.createElement('template'); t.innerHTML=html.trim(); return Array.from(t.content.childNodes); }
  Y.yamalar.forEach(function(y, i){
    var els; try { els = Array.from(document.querySelectorAll(y.selector)); } catch(e){ rapor.push({i:i, hata:'selector geçersiz: '+e.message, n:0}); return; }
    if(!els.length){ rapor.push({i:i, n:0, hata:'eşleşme yok'}); return; }
    els.forEach(function(el, k){ var ilk = (k===0);
      switch(y.op){
        case 'add': { var ns = parca(y.html||''); ns.forEach(function(n){ var ref = el;
            if(y.konum==='before') el.parentNode.insertBefore(n, el);
            else if(y.konum==='prepend') el.insertBefore(n, el.firstChild);
            else if(y.konum==='append') el.appendChild(n);
            else el.parentNode.insertBefore(n, el.nextSibling);
            if(n.nodeType===1) isaretle(n,'new',y,ilk); }); break; }
        case 'replace': { var ns2 = parca(y.html||''); ns2.forEach(function(n){ el.parentNode.insertBefore(n, el); if(n.nodeType===1) isaretle(n,'changed',y,ilk); }); el.remove(); break; }
        case 'remove': el.style.display='none'; el.setAttribute('data-mockup','removed'); break;
        case 'disable': el.setAttribute('disabled',''); el.setAttribute('aria-disabled','true'); el.classList.add('Mui-disabled'); el.style.pointerEvents='none'; el.style.opacity='0.45'; isaretle(el,'changed',y,ilk); break;
        case 'enable': el.removeAttribute('disabled'); el.setAttribute('aria-disabled','false'); el.classList.remove('Mui-disabled'); el.style.pointerEvents=''; el.style.opacity=''; isaretle(el,'changed',y,ilk); break;
        case 'text': el.textContent = y.text; isaretle(el,'changed',y,ilk); break;
        case 'attr': Object.keys(y.attr||{}).forEach(function(k){ if(y.attr[k]===null) el.removeAttribute(k); else el.setAttribute(k, String(y.attr[k])); }); isaretle(el,'changed',y,ilk); break;
        case 'style': el.setAttribute('style', (el.getAttribute('style')||'')+';'+y.style); isaretle(el,'changed',y,ilk); break;
      }
    });
    rapor.push({i:i, n:els.length});
  });
  window.__MOCKUP_RAPOR = rapor;
  // legend
  var leg = document.createElement('div'); leg.id='mockup-legend';
  var basarisiz = rapor.filter(function(r){return !r.n;}).length;
  leg.innerHTML = '<b>MOCKUP</b> · '+(Y.ozet||'')+'<br><span class="mk-new">■</span> yeni &nbsp;<span class="mk-chg">■</span> değişti &nbsp;<span class="mk-rem">■</span> kaldırıldı'
    + (basarisiz? ' &nbsp;<span style="color:#b91c1c">⚠ '+basarisiz+' yama eşleşmedi</span>':'') + ' &nbsp;<small>(R: vurguyu aç/kapat)</small>'
    + '<ol>' + Y.yamalar.map(function(y,i){ var r=rapor[i]||{}; return '<li'+(r.n?'':' class="mk-fail"')+'>'+(y.__no?'<span class="mk-no">'+y.__no+'</span> ':'')+(y.ac?'<b>'+y.ac+'</b> ':'')+(y['not']||y.op)+(r.n?' <small>('+r.n+' öğe)</small>':' — eşleşmedi')+'</li>'; }).join('') + '</ol>';
  document.body.appendChild(leg);
  document.addEventListener('keydown', function(e){ if((e.key||'').toLowerCase()==='r') document.documentElement.classList.toggle('mockup-redline-off'); });
})();
"""
_REDLINE_CSS = """
[data-mockup="new"]{outline:2px solid #16a34a !important;outline-offset:2px;box-shadow:0 0 0 4px rgba(22,163,74,.15) !important;position:relative}
[data-mockup="changed"]{outline:2px dashed #d97706 !important;outline-offset:1px}
[data-mockup="changed"]:not([data-mockup-no])::after{content:none}
[data-mockup="removed"]{display:none !important}
[data-mockup]::after{content:attr(data-mockup-no);position:absolute;top:-10px;right:-10px;background:#111827;color:#fff;font:600 10px/16px system-ui;border-radius:8px;padding:0 5px;z-index:9999}
[data-mockup="changed"]::after{background:#d97706}
.mockup-redline-off [data-mockup]{outline:none !important;box-shadow:none !important}
.mockup-redline-off [data-mockup]::after,.mockup-redline-off #mockup-legend{display:none}
#mockup-legend{position:fixed;right:14px;bottom:14px;max-width:360px;background:#fff;border:1px solid #e5e7eb;border-radius:10px;box-shadow:0 8px 30px rgba(0,0,0,.18);padding:10px 12px;font:12px/1.5 system-ui;color:#111827;z-index:99999}
#mockup-legend ol{margin:6px 0 0 16px;padding:0;max-height:180px;overflow:auto}#mockup-legend .mk-fail{color:#b91c1c}
#mockup-legend .mk-no{display:inline-block;min-width:16px;text-align:center;background:#111827;color:#fff;border-radius:8px;font-size:10px;line-height:16px}
#mockup-legend .mk-new{color:#16a34a}#mockup-legend .mk-chg{color:#d97706}#mockup-legend .mk-rem{color:#b91c1c}
"""


def mockup_olustur(baseline_html: str, yamalar: list, ozet: str = "", baslik: str = "", kaynak_url: str = "") -> str:
    """Baseline + gömülü yama JSON + uygulayıcı JS + redline CSS → tek dosyalık mockup HTML."""
    veri = json.dumps({"ozet": ozet, "yamalar": yamalar}, ensure_ascii=False).replace("</", "<\\/")
    ek = (f"<style id=\"mockup-redline\">{_REDLINE_CSS}</style>\n"
          f"<script id=\"mockup-yama\">window.__MOCKUP_YAMA={veri};</script>\n"
          f"<script id=\"mockup-uygula\">{_UYGULAYICI_JS}</script>\n")
    html = baseline_html
    if "</body>" in html:
        html = html.replace("</body>", ek + "</body>", 1)
    else:
        html += ek
    not_ = (f"<!-- Analyst Studio mockup · {baslik} · kaynak: {kaynak_url} · {time.strftime('%Y-%m-%d %H:%M')} · "
            f"{len(yamalar)} yama (gerçek ekran + değişiklik) -->\n")
    return not_ + html


# ── uçtan uca: yakala → yama → kaydet (+PNG) ────────────────────────────────────────────────────────────
def uret(analiz_md: str, url: str, iste: str = "", baslik: str = "", yeni_ekran: bool = False,
         dosya: str = GOREV_MOCKUP_DOSYA, bekle: str = "", yeniden: bool = False, _ai=None, _yakala=None) -> dict:
    """Dönen: {ok, dosya, html, yol, png, ozet, yamalar, kaynak_url, tasarim_kaynagi:'canli-baseline', eslesmeyen, neden}.
    Yakalama düşerse ok=False + `fallback=True` (çağıran eski sıfırdan-üretim yoluna düşebilir)."""
    yak = (_yakala or EY.yakala)(url, bekle=bekle, yeniden=yeniden)
    if not yak.get("ok"):
        return {"ok": False, "fallback": True, "neden": f"Ekran yakalanamadı: {yak.get('neden', '')}", "yakalama": yak}
    try:
        baseline = Path(yak["baseline"]).read_text(encoding="utf-8")
    except Exception as e:
        return {"ok": False, "fallback": True, "neden": f"Baseline okunamadı: {e}"}
    y = yama_uret(analiz_md, baseline, iste=iste, baslik=baslik, yeni_ekran=yeni_ekran, _ai=_ai)
    if not y["ok"]:
        return {"ok": False, "fallback": True, "neden": y["neden"], "ham": y.get("ham", "")[:2000], "yakalama": yak}
    onk = selector_on_kontrol(y["yamalar"], baseline)
    supheli = [r for r in onk if r["suphe"]]
    if supheli:
        logger.warning("Mockup yama: %d selector baseline'da bulunmayan ipucu içeriyor: %s", len(supheli),
                       [s["eksik"] for s in supheli][:5])
    html = mockup_olustur(baseline, y["yamalar"], y["ozet"], baslik, yak.get("url", url))
    yol = _kaydet(dosya, html)
    png = ""
    try:
        from .html_render import html_to_png
        png_yolu = OUTPUT_DIR / (Path(dosya).stem + ".png")
        if html_to_png(yol, png_yolu, genislik=1560, yukseklik=1100):
            png = str(png_yolu)
    except Exception as e:
        logger.info("Mockup PNG üretilemedi: %s", e)
    meta = {"dosya": dosya, "kaynak_url": yak.get("url", url), "baseline": yak.get("baseline"), "live_png": yak.get("png", ""),
            "png": png, "ozet": y["ozet"], "yamalar": y["yamalar"], "supheli_selector": supheli, "yeni_ekran": yeni_ekran,
            "baslik": baslik, "ts": time.time(), "tasarim_kaynagi": "canli-baseline"}
    try:
        (OUTPUT_DIR / (Path(dosya).stem + ".yama.json")).write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass
    return {"ok": True, "dosya": yol.name, "yol": str(yol), "html": html, "png": png, "ozet": y["ozet"], "yamalar": y["yamalar"],
            "kaynak_url": yak.get("url", url), "tasarim_kaynagi": "canli-baseline", "eslesmeyen": supheli,
            "yakalama_onbellek": bool(yak.get("yeniden_kullanildi")), "neden": ""}
