"""İnteraktif Analiz — doküman yüklemeden, SOHBETLE süreç/teknik analiz.

Analist bir isteri/fikir yazar → agent (RAG + domain kuralları + kaynak-öncelikle
topraklanmış) soru sorar / yöntem önerir → adım adım BİRLİKTE olgunlaştırılır.
Hazır olunca kilometre taşı üreticiler (`surec_uret`/`teknik_uret`) MEVCUT süreç/teknik
motorlarını sohbet metnini girdi vererek çalıştırır → standart çıktı dosyaları
(`surec-analizi.md`, `teknik-analiz.md`) → Çıktılar & Revizyon + Jira aynen devreye girer.

Miras (tekrar girilmez): Bağlam Filtresi + uygulama giriş bilgileri (paylaşılan
context_filter.json). Yok: doküman yükleme · özel prompt (hep varsayılan) · manuel
gözlem kapsamı alanı (canlı gözlem yine yapılır — hedef sohbetten/mirastan türetilir).
"""

import json
import time
from pathlib import Path

from .base import (
    _api_cagri, OUTPUT_DIR,
    referans_dosyalari_hazirla, _ref_bloklari_olustur,
    _domain_kurallari_oku,
    MAX_TOKENS_COMBINED,
)

_SOHBET_DIR = OUTPUT_DIR / "sohbet"
_OTURUM_DOSYA = _SOHBET_DIR / "oturum.json"


# ─── Sohbet asistanı sistem promptu ──────────────────────────────────────────

_SOHBET_SISTEM = (
    "Sen MBS (Merkezi Bahis Sistemi) projesinde kıdemli bir iş/teknik analist ve yazılım "
    "mimarısın. Analist sana bir DOKÜMAN olmadan, serbest metinle bir isteri, fikir ya da "
    "\"şöyle yapsak nasıl olur?\" sorusu getiriyor. Amacın onunla SOHBET EDEREK gereksinimi "
    "netleştirmek ve birlikte bir çözüm/süreç olgunlaştırmak — bu bir sohbet, tam rapor DEĞİL.\n\n"
    "DAVRANIŞ:\n"
    "- Kısa, odaklı ve pratik yanıt ver (uzun rapor yazma — o iş 'Süreç/Teknik Analizi Üret' "
    "butonlarında yapılır). Yanıtın konuşma tonunda, madde/başlıkla okunur olsun.\n"
    "- Belirsizlik varsa ÖNCE netleştirici soru sor (en fazla 2-3 soru, en kritik olanlar). "
    "Her şeyi baştan sorma; sohbet ilerledikçe derinleş.\n"
    "- Uygun olduğunda 1-2 somut YÖNTEM/YAKLAŞIM öner, artı-eksileriyle (trade-off) kısaca.\n"
    "- Sana verilen REFERANS BAĞLAM (Swagger/Confluence/Jira/servis) ve domain kurallarını "
    "kullan; gerçek endpoint/tablo/ekran/terimlere atıf yap. Gözlemleyemediğin/bilmediğin şeyi "
    "UYDURMA — 'bunu doğrulamamız gerek' de ve açık soru olarak işaretle.\n"
    "- Kaynak-öncelik: Swagger/canlı gözlem > Confluence > BRD/Süreç > Jira > UI. Çelişkide "
    "gözlemlenebilir gerçek veri kazanır.\n"
    "- Yeterince netleştiğinde analiste 'Süreç Analizi Üret' (ve ardından 'Teknik Analiz Üret') "
    "butonlarıyla formal analizi üretebileceğini HATIRLAT.\n"
    "- Türkçe yaz; teknik terimler İngilizce kalabilir.\n"
)


# ─── Oturum saklama (v1: tek aktif oturum) ───────────────────────────────────

def _bos_oturum() -> dict:
    return {"oturum_id": f"sohbet-{int(time.time())}", "baslik": "", "mesajlar": [],
            "created": time.time(), "guncellendi": time.time()}


def oturum_oku() -> dict:
    if _OTURUM_DOSYA.exists():
        try:
            return json.loads(_OTURUM_DOSYA.read_text(encoding="utf-8"))
        except Exception:
            pass
    return _bos_oturum()


def _oturum_yaz(oturum: dict) -> None:
    _SOHBET_DIR.mkdir(parents=True, exist_ok=True)
    oturum["guncellendi"] = time.time()
    _OTURUM_DOSYA.write_text(json.dumps(oturum, ensure_ascii=False, indent=2), encoding="utf-8")


def oturum_sifirla() -> dict:
    oturum = _bos_oturum()
    _oturum_yaz(oturum)
    return oturum


def _konusma_metni(oturum: dict, son_n: int | None = None) -> str:
    """Sohbeti 'Analist: … / Agent: …' düz metnine çevirir (RAG sorgusu + üretim girdisi)."""
    mesajlar = oturum.get("mesajlar", [])
    if son_n:
        mesajlar = mesajlar[-son_n:]
    satirlar = []
    for m in mesajlar:
        etiket = "Analist" if m.get("rol") == "analist" else "Agent"
        satirlar.append(f"{etiket}: {m.get('metin', '')}")
    return "\n\n".join(satirlar)


# ─── Sohbet turu ─────────────────────────────────────────────────────────────

def sohbet_mesaj(metin: str) -> dict:
    """Analistin mesajını ekler, RAG'li yanıt üretir, ekler ve oturumu döndürür.
    Canlı gözlem YAPILMAZ (sohbet hızlı kalsın); gözlem yalnız üretim adımlarında."""
    metin = (metin or "").strip()
    if not metin:
        raise ValueError("Boş mesaj gönderilemez.")
    oturum = oturum_oku()
    oturum["mesajlar"].append({"rol": "analist", "metin": metin, "ts": time.time()})
    if not oturum.get("baslik"):
        oturum["baslik"] = metin[:60] + ("…" if len(metin) > 60 else "")

    # RAG — sohbet metnini sorgu vererek en alakalı referans parçaları getir (otomatik alaka).
    ref_bloklari: list = []
    try:
        ref_dosyalar = referans_dosyalari_hazirla()
        if ref_dosyalar:
            sorgu = _konusma_metni(oturum, son_n=6)
            ref_bloklari, _ = _ref_bloklari_olustur(ref_dosyalar, sorgu_metni=sorgu)
    except Exception as e:
        print(f"  ⚠ Sohbet RAG getirimi atlandı: {e}")

    mesajlar: list = []
    if ref_bloklari:
        blok = list(ref_bloklari)
        blok.append({"type": "text", "text": "(Yukarısı REFERANS BAĞLAM'dır — sohbete göre kullan.)"})
        blok[-1]["cache_control"] = {"type": "ephemeral"}
        mesajlar.append({"role": "user", "content": blok})
        mesajlar.append({"role": "assistant", "content": [
            {"type": "text", "text": "Referans bağlamı aldım. İsterinizi dinliyorum."}]})
    for m in oturum["mesajlar"]:
        rol = "user" if m.get("rol") == "analist" else "assistant"
        mesajlar.append({"role": rol, "content": [{"type": "text", "text": m.get("metin", "")}]})

    sistem = _SOHBET_SISTEM + _domain_kurallari_oku()
    yanit = _api_cagri(sistem, mesajlar, max_tokens=MAX_TOKENS_COMBINED, thinking=False)
    yanit = (yanit or "").strip()
    oturum["mesajlar"].append({"rol": "agent", "metin": yanit, "ts": time.time()})
    _oturum_yaz(oturum)
    return oturum


# ─── Kilometre taşı üretim — MEVCUT motorları sohbet girdisiyle çalıştır ──────

def _uretim_girdisi(oturum: dict) -> list:
    konusma = _konusma_metni(oturum)
    if not konusma.strip():
        raise ValueError("Önce sohbette isterini yaz (analiz üretilecek içerik yok).")
    return [{"type": "text", "text": (
        "### İnteraktif Analiz Oturumu (analist ↔ agent sohbeti)\n\n"
        "Aşağıda bir isteri/süreç üzerine yapılan sohbet var. Bu sohbette OLGUNLAŞAN "
        "gereksinimi analiz konusu kabul et; analistin son kararlarını/cevaplarını esas al, "
        "açık kalan noktaları 'Açık Sorular'a taşı.\n\n" + konusma)}]


def surec_uret(oturum: dict | None = None) -> Path:
    """Sohbetten süreç analizi üretir (özel prompt YOK, canlı gözlem VAR — miras config).
    surec-analizi.md yazar → Çıktılar/Revizyon/Teknik devreye girer."""
    oturum = oturum or oturum_oku()
    from .surec_analizi import surec_analizi_yap
    return surec_analizi_yap(icerik_override=_uretim_girdisi(oturum),
                             dosya_adi_override="interaktif-analiz", ozel_atla=True)


def teknik_uret() -> tuple[Path, Path]:
    """surec-analizi.md → teknik-analiz.md (özel prompt YOK, canlı gözlem VAR)."""
    from .teknik_analiz import teknik_analiz_yap
    return teknik_analiz_yap(ozel_atla=True)


def surec_var_mi() -> bool:
    return (OUTPUT_DIR / "surec-analizi.md").exists()
