"""Opt-in EKRAN GÖRÜNTÜSÜ yakalama (FE task'ı için canlı ekranları screenshot'layıp Jira'ya ek olarak koyma).

Owner isteri (2026-10-20): "181 gibi FE task'larında hangi ekranlarda hangi alanların kalkacağı belli; bu ekranların
görüntülerini task'a ekleyip Jira'da görülebilir mi?" → EVET. Bu modül, analizin adlandırdığı ekranlara canlı gidip
her birinin screenshot'ını alır (Playwright `browser_take_screenshot`, DOSYA-ADSIZ → `--output-dir` = EKRAN_GORUNTU_DIR),
sırayla analizden türetilen açıklamalarla eşler, sonra `atlassian_attach` ile Jira task'ına ekler.

NEDEN opt-in + ayrı adım: (a) her screenshot bir araç turu = kota; yalnız gerekli ekranlar çekilir, (b) canlı iç uygulama
görüntüsü gerçek şirket UI'ı (bazen veri) taşır — analist bilinçli tetikler, (c) gözlem/analiz akışını yavaşlatmaz.

Playwright davranışı (config.d.ts): dosya ADI VERİLMEDEN alınan screenshot `outputDir`'e otomatik adla düşer; AD verilirse
workspace köküne yazar. Bu yüzden agent'a ad verdirmeyiz → hepsi EKRAN_GORUNTU_DIR'e düşer, biz sırayla eşleriz.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from .base import (
    EKRAN_GORUNTU_DIR, MAX_TOKENS_KISA,
    _api_cagri, _xml_ayir, _metin_sikistir, asama_ayarla,
)

_LOCK = threading.Lock()   # yakalama serileştirilir (paylaşılan output-dir; opt-in, seyrek)
_MAX_GORUNTU = 8           # task başına üst sınır (kota + Jira ek sayısı)


def _png_listesi(sonra: float = 0.0) -> list[Path]:
    """Çıktı klasöründeki PNG'ler (mtime sıralı). `sonra` verilirse yalnız o andan SONRA düşenler
    (bu yakalamaya ait) — paylaşılan klasörde başka çağrının bıraktığı eski PNG'yi almaz."""
    try:
        return sorted((p for p in EKRAN_GORUNTU_DIR.glob("*.png") if p.stat().st_mtime >= sonra - 1),
                      key=lambda p: p.stat().st_mtime)
    except Exception:
        return []


def _klasor_temizle() -> None:
    # PNG + .yml (canlı gözlem snapshot'ları — paylaşılan --output-dir yüzünden buraya düşer) temizlenir.
    try:
        EKRAN_GORUNTU_DIR.mkdir(parents=True, exist_ok=True)
        for pat in ("*.png", "*.yml", "*.yaml", "*.jpeg", "*.jpg"):
            for p in EKRAN_GORUNTU_DIR.glob(pat):
                p.unlink(missing_ok=True)
    except Exception:
        pass


_SISTEM = (
    "Canlı uygulama EKRAN GÖRÜNTÜSÜ yakalayıcısısın. Görevin: verilen teknik analizin ADLANDIRDIĞI ekran/modalleri canlı "
    "uygulamada açıp HER BİRİNİN ekran görüntüsünü almak. Analiz yazmazsın, değişiklik yapmazsın (kayıt oluşturma/silme "
    "YOK) — yalnız ilgili ekrana/modala git ve görüntü al. Şifre/token yazma."
)


def _yakala_talimati(analiz_md: str) -> str:
    return (
        "### GÖREV — ekran görüntüsü al (en çok " + str(_MAX_GORUNTU) + " görüntü)\n"
        "Aşağıdaki teknik analiz, değişikliğin HANGİ ekranlarda/modallerde olacağını söylüyor. Her biri için:\n"
        "1) O ekrana/sekmeye git; değişiklik bir MODAL içindeyse modalı AÇ (ör. bir satırda Edit/Add). Değişiklik yapma, "
        "KAYDETME; yalnız görüntülemek için aç.\n"
        "2) İlgili alanlar/bölüm görünürken `browser_take_screenshot` ile görüntü al. DOSYA ADI VERME (otomatik adlandırılsın). "
        "Modal açıksa yalnız modalı/alanı kapsayan görüntü yeterli.\n"
        "3) Sıradaki ekrana geç. Aynı ekranı iki kez çekme. Analizde adı geçmeyen ekranı çekme.\n"
        "Her görüntüyü ALDIĞIN SIRAYLA kaydet; sonunda SADECE şu bloğu yaz (görüntü sayısı = aldığın screenshot sayısı):\n"
        "<ekran_goruntu>[{\"sira\":1,\"ekran\":\"menü yolu + modal (ör. Market Setup > Market Per Sport — Edit modalı)\","
        "\"aciklama\":\"görüntüde ne görünüyor / hangi alanlar (kısa)\"}]</ekran_goruntu>\n"
        "Bir ekrana erişemezsen (yetki/veri yok) onu ATLA ve bloğa EKLEME (yalnız gerçekten alınan görüntüleri listele).\n\n"
        "### TEKNİK ANALİZ (ekran adları buradan)\n" + (analiz_md or "")[:8000]
    )


def yakala(analiz_md: str, canli: str, kapsam: str, _ai=None) -> dict:
    """Analizin adlandırdığı ekranların screenshot'larını alır. `canli`: canli_uygulama_baglami_hazirla çıktısı (base+hedef).
    Dönen: {ok, goruntular:[{yol, ekran, aciklama}], neden}. Hata → {ok:False}. Serileştirilmiş (paylaşılan output-dir)."""
    if not (canli or "").strip():
        return {"ok": False, "goruntular": [], "neden": "Canlı uygulama hedefi tanımlı değil (Bağlam Filtresi → Task canlı hedefi)."}
    import time
    with _LOCK:
        _klasor_temizle()
        asama_ayarla("ekran:goruntu")
        t0 = time.time()
        icerik = [{"type": "text", "text": canli}, {"type": "text", "text": _yakala_talimati(analiz_md)}]
        ai = _ai or (lambda s, m: _api_cagri(s, m, max_tokens=MAX_TOKENS_KISA, thinking=False, onbellek=False,
                                             canli_uygulama_kapsami=kapsam, katman="yardimci",
                                             max_turns=max(10, _MAX_GORUNTU * 4), tur_devam=1))
        yanit, kesildi = "", ""
        try:
            yanit = ai(_SISTEM, [{"role": "user", "content": icerik}])
        except Exception as e:
            # Çağrı kesilse de (timeout/limit) o ana dek DISKE DÜŞEN görüntüleri KURTAR — kota boşa gitmesin.
            kesildi = str(e)[:200]
        # Agent'ın bildirdiği sıra/açıklama + diske düşen gerçek PNG'ler (yalnız bu yakalamaya ait)
        try:
            ham = json.loads(_xml_ayir(_metin_sikistir(yanit or ""), "ekran_goruntu") or "[]")
        except Exception:
            ham = []
        meta = [m for m in ham if isinstance(m, dict)][:_MAX_GORUNTU]
        pngler = _png_listesi(sonra=t0)[:_MAX_GORUNTU]
        if not pngler:
            return {"ok": False, "goruntular": [],
                    "neden": (f"Çağrı kesildi ({kesildi}) ve hiç görüntü alınamadı." if kesildi
                              else "Ekran görüntüsü alınamadı (tarayıcı aracı çalışmadı ya da ekranlara erişilemedi).")}
        goruntular = []
        for i, p in enumerate(pngler):
            m = meta[i] if i < len(meta) else {}
            goruntular.append({"yol": str(p), "dosya": p.name,
                               "ekran": str(m.get("ekran") or f"Ekran {i + 1}").strip()[:120],
                               "aciklama": str(m.get("aciklama") or "").strip()[:300]})
        return {"ok": True, "goruntular": goruntular,
                "neden": (f"Çağrı kesildi ama {len(goruntular)} görüntü kurtarıldı ({kesildi})." if kesildi else "")}


def _guvenli_ad(ekran: str, i: int) -> str:
    import re
    taban = re.sub(r"[^A-Za-z0-9]+", "-", (ekran or "")).strip("-").lower()[:50] or f"ekran-{i + 1}"
    return f"{i + 1:02d}-{taban}.png"


def jiraya_ekle(key: str, goruntular: list[dict], cloud_id: str = "") -> dict:
    """Yakalanan PNG'leri Jira task'ına ek olarak yükler. Her ek AYRI try (biri başarısız olsa diğerleri gider).
    Dönen: {ok, eklenen:[{dosya, ekran}], hatalar:[...]}"""
    from .atlassian import atlassian_attach
    eklenen, hatalar = [], []
    for i, g in enumerate(goruntular or []):
        yol = Path(g.get("yol", ""))
        if not yol.exists():
            hatalar.append(f"{g.get('ekran', '?')}: dosya yok")
            continue
        ad = _guvenli_ad(g.get("ekran", ""), i)
        try:
            atlassian_attach(key, ad, yol.read_bytes(), content_type="image/png", cloud_id=cloud_id)
            eklenen.append({"dosya": ad, "ekran": g.get("ekran", "")})
        except Exception as e:
            hatalar.append(f"{ad}: {str(e)[:120]}")
    return {"ok": bool(eklenen), "eklenen": eklenen, "hatalar": hatalar}
