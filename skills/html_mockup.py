"""
HTML Prototip Skill — Adım 8.
Süreç analizinden çalışan HTML+CSS+JS prototipi üretir.
"""

from pathlib import Path
from .base import (
    _api_cagri, _kaydet,
    dosya_oku, prompt_yukle,
    OUTPUT_DIR, MAX_CHARS_GENEL,
    canli_uygulama_baglami_hazirla,
)

MAX_TOKENS_MOCKUP  = 12_000   # CLI modunda etkisiz; API modu için canlı gözlem + üretim payı
MAX_CHARS_MOCKUP   = 20_000   # teknik analize dahil ederken uygulanan limit

_MOCKUP_SISTEM_BASE = """\
Deneyimli UI/UX tasarımcısı ve frontend geliştirici olarak süreç analizi dokümanından \
çalışan bir HTML prototipi oluştur.

Gereksinimler:
- Tek HTML dosyası (CSS ve JS gömülü); dış CDN kullanabilirsin
- Süreç analizindeki tüm ana ekranlar/adımlar gezinilebilir olmalı
- Gerçekçi form alanları, butonlar ve örnek veri gösterimi
- Sidebar veya tab ile ekranlar arası geçiş
- Türkçe UI metinleri, profesyonel görünüm
- Tıklanabilir butonlar çalışsın; formlar submit'te sonuç göstersin
{ui_hint}
Yalnızca HTML içeriğini ver — başka açıklama ekleme, kod bloğu (```) işareti kullanma."""

_UI_HINT_YOK = """\

Tasarım rehberi: koyu sidebar + açık içerik alanı; accent rengi #5b5ef4; \
font-family: system-ui; temiz ve minimal."""


def html_mockup_uret() -> Path:
    """
    output/surec-analizi.md → output/mockup.html
    """
    surec_dosya = OUTPUT_DIR / "surec-analizi.md"
    if not surec_dosya.exists():
        raise FileNotFoundError("surec-analizi.md bulunamadı. Önce süreç analizi yapın.")

    surec_metni = dosya_oku(surec_dosya, MAX_CHARS_GENEL)
    icerik_parcalari = [
        {"type": "text", "text": f"### Süreç Analizi\n\n{surec_metni}"},
    ]

    # Canlı uygulama (context_filter live_app: target_url + extra_urls) → Chrome MCP
    # gezinme görevi. URL tanımlıysa prototip, GÖZLEMLENEN ekranın tasarım dilini ve
    # component'lerini BAZ alır; değilse generic tasarım ipucuna düşer (fallback).
    kapsam = None
    gorev_talimati = canli_uygulama_baglami_hazirla()
    if gorev_talimati:
        icerik_parcalari.append({"type": "text", "text": gorev_talimati})
        kapsam = "surec"   # _api_cagri CLI modunda Chrome MCP'yi bu bayrakla açar
    ui_hint = "" if gorev_talimati else _UI_HINT_YOK

    icerik_parcalari.append(
        {"type": "text",
         "text": "Bu süreç ve (görev verildiyse) gözlemlenen canlı ekranı baz alarak, "
                 "tüm component'leri çalışan HTML prototipi oluştur."})

    sistem = (prompt_yukle("html_mockup_base") + "\n" + ui_hint +
              "\nYalnızca HTML içeriğini ver — başka açıklama ekleme, kod bloğu (```) işareti kullanma.")
    mesajlar = [{"role": "user", "content": icerik_parcalari}]
    yanit = _api_cagri(sistem, mesajlar, max_tokens=MAX_TOKENS_MOCKUP,
                       canli_uygulama_kapsami=kapsam)

    # AI bazen ```html ... ``` bloğu içinde döndürür — sadece içeriği al
    yanit = yanit.strip()
    if yanit.startswith("```"):
        satirlar = yanit.splitlines()
        yanit = "\n".join(satirlar[1:])
        if yanit.rstrip().endswith("```"):
            yanit = yanit.rstrip()[:-3].rstrip()

    return _kaydet("mockup.html", yanit)


_MOCKUP_DUZELT_SISTEM = """\
Deneyimli frontend geliştiricisin. Sana MEVCUT bir HTML prototipi ve analistin DÜZELTME \
TALİMATI verilecek. Talimatı uygula ve prototipin TAMAMINI güncellenmiş haliyle döndür.

Kurallar:
- YALNIZ talimatın istediğini değiştir. Geri kalan yapı, içerik, stil, sınıflar ve çalışan \
davranış (butonlar/formlar/sekme geçişleri) AYNEN korunmalı.
- Tek HTML dosyası (CSS ve JS gömülü); dış CDN kullanabilirsin. Türkçe UI metinleri.
- Tıklanabilir butonlar çalışsın; formlar submit'te sonuç göstersin.
- Talimat belirsizse en makul yorumu uygula; prototipi bozma.
- Yalnızca HTML içeriğini ver — başka açıklama ekleme, kod bloğu (```) işareti kullanma."""


def html_mockup_duzelt(talimat: str) -> Path:
    """Sohbetli iteratif düzeltme: output/mockup.html + analist talimatı → güncellenmiş mockup.html.
    Chrome MCP açılmaz (saf HTML düzenleme). onbellek=False: aynı talimat farklı sonuç bekleyebilir."""
    talimat = (talimat or "").strip()
    if not talimat:
        raise ValueError("Düzeltme talimatı boş olamaz.")
    mockup = OUTPUT_DIR / "mockup.html"
    if not mockup.exists():
        raise FileNotFoundError("mockup.html yok. Önce 'HTML Prototip Oluştur' ile prototip üretin.")

    mevcut = mockup.read_text(encoding="utf-8", errors="replace")[:MAX_CHARS_MOCKUP * 4]
    icerik_parcalari = [
        {"type": "text", "text": f"### MEVCUT PROTOTİP (mockup.html)\n\n{mevcut}"},
        {"type": "text", "text": f"### DÜZELTME TALİMATI\n\n{talimat}"},
    ]
    yanit = _api_cagri(_MOCKUP_DUZELT_SISTEM,
                       [{"role": "user", "content": icerik_parcalari}],
                       max_tokens=MAX_TOKENS_MOCKUP, onbellek=False)
    yanit = yanit.strip()
    if yanit.startswith("```"):
        satirlar = yanit.splitlines()
        yanit = "\n".join(satirlar[1:])
        if yanit.rstrip().endswith("```"):
            yanit = yanit.rstrip()[:-3].rstrip()
    return _kaydet("mockup.html", yanit)


# ─── Task Analizi → Ekran Mockup'ı ───────────────────────────────────────────
# Task Analizi ekranında, analiz edilen bir göreve EK yeni bir isteye (ekran/özellik)
# göre HTML mockup üretir. "Mevcut ekranla aynı görünüm" için Task akışının KENDİ
# `live_app_gorev` hedefini Chrome MCP ile gözlemleyip gerçek component/tasarım dilini
# baz alır (Süreç `mockup.html`'inden AYRI dosya: output/gorev-mockup.html).

GOREV_MOCKUP_DOSYA = "gorev-mockup.html"

_GOREV_MOCKUP_SISTEM = """\
Deneyimli UI/UX tasarımcısı ve frontend geliştiricisin. Sana (1) bir Jira görevinin TEKNİK \
ANALİZİ, (2) bu göreve EK yapılacak YENİ İSTE (bir ekran/özellik), ve mümkünse (3) gözlemlenen \
CANLI uygulamanın mevcut ekranları verilecek. Yeni isteyi karşılayan, tek dosyalık ÇALIŞAN bir \
HTML ekran mockup'ı üret.

Kurallar:
- Tek HTML dosyası (CSS ve JS gömülü); dış CDN kullanabilirsin.
- MEVCUT EKRAN TASARIMINI BİREBİR KORU: gözlemlenen canlı uygulamanın renk paleti, tipografi, \
buton/form/tablo component'leri, boşluk ve yerleşim dilini AYNEN kullan — yeni ekran mevcut \
ürünün bir PARÇASI gibi görünsün, kopuk/jenerik durmasın. (Canlı gözlem yoksa tasarım rehberine uy.)
- YENİ İSTE'yi eksiksiz karşıla: ilgili form alanları, butonlar, tablo/liste, durumlar, örnek veri.
- Türkçe UI metinleri, profesyonel görünüm. Tıklanabilir butonlar çalışsın; formlar submit'te sonuç göstersin.
{ui_hint}
Yalnızca HTML içeriğini ver — başka açıklama ekleme, kod bloğu (```) işareti kullanma."""


def _html_fence_soyut(yanit: str) -> str:
    """AI bazen ```html ... ``` bloğu içinde döndürür — yalnız içeriği al."""
    yanit = (yanit or "").strip()
    if yanit.startswith("```"):
        satirlar = yanit.splitlines()
        yanit = "\n".join(satirlar[1:])
        if yanit.rstrip().endswith("```"):
            yanit = yanit.rstrip()[:-3].rstrip()
    return yanit


def gorev_mockup_uret(analiz_md: str, iste_metni: str, baslik: str = "",
                      hedef_tarif: str = "") -> dict:
    """Görev analizi + yeni iste → output/gorev-mockup.html. Task akışının `live_app_gorev`
    hedefini (varsa) gözlemleyip mevcut tasarımı baz alır. Dönen: {dosya, html, boyut, tasarim_kaynagi}."""
    iste_metni = (iste_metni or "").strip()
    if not iste_metni:
        raise ValueError("Yeni iste / ekran açıklaması boş olamaz.")
    analiz_md = (analiz_md or "").strip()

    icerik_parcalari: list = []
    if (baslik or "").strip():
        icerik_parcalari.append({"type": "text", "text": f"### Görev\n{baslik.strip()}"})
    if analiz_md:
        icerik_parcalari.append(
            {"type": "text", "text": f"### Görev Teknik Analizi\n\n{analiz_md[:MAX_CHARS_GENEL]}"})
    icerik_parcalari.append(
        {"type": "text", "text": f"### YENİ İSTE (bu ekranı tasarla)\n\n{iste_metni}"})

    # Canlı uygulama: Task akışının KENDİ hedefi (gorev=True → live_app_gorev); hedef_tarif
    # verilmezse iste metni odaklı gözlem tarifine geçer. URL yoksa generic fallback.
    kapsam = None
    gorev_talimati = canli_uygulama_baglami_hazirla(
        gorev=True, hedef_tarif=(hedef_tarif or iste_metni)[:500])
    if gorev_talimati:
        icerik_parcalari.append({"type": "text", "text": gorev_talimati})
        kapsam = "gorev"
    ui_hint = "" if gorev_talimati else _UI_HINT_YOK

    sistem = _GOREV_MOCKUP_SISTEM.format(ui_hint=ui_hint)
    # Canlı gözlemde taze bak (onbellek=False); gözlem yoksa normal cache.
    yanit = _api_cagri(sistem, [{"role": "user", "content": icerik_parcalari}],
                       max_tokens=MAX_TOKENS_MOCKUP, canli_uygulama_kapsami=kapsam,
                       onbellek=not kapsam)
    yanit = _html_fence_soyut(yanit)
    yol = _kaydet(GOREV_MOCKUP_DOSYA, yanit)
    return {"dosya": yol.name, "html": yanit, "boyut": yol.stat().st_size,
            "tasarim_kaynagi": "canli" if kapsam else "jenerik"}


def gorev_mockup_duzelt(talimat: str) -> dict:
    """Sohbetli iteratif düzeltme — yalnız gorev-mockup.html'i değiştirir (analize DOKUNMAZ).
    Chrome MCP açılmaz (saf HTML düzenleme). Dönen: {dosya, html, boyut}."""
    talimat = (talimat or "").strip()
    if not talimat:
        raise ValueError("Düzeltme talimatı boş olamaz.")
    mockup = OUTPUT_DIR / GOREV_MOCKUP_DOSYA
    if not mockup.exists():
        raise FileNotFoundError("gorev-mockup.html yok. Önce 'Ekran Mockup'ı' ile üretin.")

    mevcut = mockup.read_text(encoding="utf-8", errors="replace")[:MAX_CHARS_MOCKUP * 4]
    icerik_parcalari = [
        {"type": "text", "text": f"### MEVCUT MOCKUP (gorev-mockup.html)\n\n{mevcut}"},
        {"type": "text", "text": f"### DÜZELTME TALİMATI\n\n{talimat}"},
    ]
    yanit = _api_cagri(_MOCKUP_DUZELT_SISTEM,
                       [{"role": "user", "content": icerik_parcalari}],
                       max_tokens=MAX_TOKENS_MOCKUP, onbellek=False)
    yanit = _html_fence_soyut(yanit)
    yol = _kaydet(GOREV_MOCKUP_DOSYA, yanit)
    return {"dosya": yol.name, "html": yanit, "boyut": yol.stat().st_size}


def mockup_oku_kontekst() -> str | None:
    """
    output/mockup.html varsa teknik analize dahil edilecek kısa özet döndür.
    Tüm HTML yerine body içeriği + style özeti — token tasarrufu için.
    """
    mockup_dosya = OUTPUT_DIR / "mockup.html"
    if not mockup_dosya.exists():
        return None

    icerik = mockup_dosya.read_text(encoding="utf-8", errors="replace")
    if len(icerik) <= MAX_CHARS_MOCKUP:
        return icerik

    # Büyük prototiplerde: <body> içeriğini + <style> başını al
    import re
    body_m  = re.search(r'<body[^>]*>(.*?)</body>', icerik, re.DOTALL | re.IGNORECASE)
    style_m = re.search(r'<style[^>]*>(.*?)</style>', icerik, re.DOTALL | re.IGNORECASE)

    parcalar = []
    if style_m:
        style_ozet = style_m.group(1)[:2_000]
        parcalar.append(f"<style>\n{style_ozet}\n/* ... kısaltıldı ... */\n</style>")
    if body_m:
        body_ozet = body_m.group(1)[:MAX_CHARS_MOCKUP - len(parcalar[0]) if parcalar else MAX_CHARS_MOCKUP]
        parcalar.append(f"<body>\n{body_ozet}\n<!-- ... kısaltıldı ... -->\n</body>")

    return "\n".join(parcalar) if parcalar else icerik[:MAX_CHARS_MOCKUP]
