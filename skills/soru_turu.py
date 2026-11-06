"""Açık soru TÜRÜ — analistin yükünü gerçek iş kararına indirir (Emin Kaleli geri bildirimi, owner 2026-11-06).

Üç tür (soru bloğunda `- Tür:` satırı; 0 token, deterministik güvenlik ağı):
  is_karari        → yalnız analist/PO cevaplayabilir (ürün niyeti, kapsam, iş kuralı tercihi). Onay kapısı/ZORUNLU yalnız bunlara bakar.
  teknik_arastirma → agent Swagger/canlı gözlem/kod/DB ile bulabilir (hangi servis, repository, index, collation, cache,
                     parametre, mevcut davranış). Analiste SORULMAZ; öz-çözümlemeye gider.
  dogrulanamadi    → araştırıldı, kanıt yok / erişim yok → analizde teknik risk notu; onay engeli DEĞİL.

Model `Tür:` yazmasa ya da yanlış yazsa da `md_tur_etiketle` her bloğa türü yazar (regex kalıpları), `zorunlu_normalize`
iş-kararı dışı bloklardan `Zorunlu: Evet`'i siler, `cevaplananlari_ele` önceki aşamada cevaplanmış soruyu yeniden sorulmaktan
düşürür (benzerlik). base.py'yi IMPORT ETMEZ (run.py/sorular.py'de ucuz).
"""
from __future__ import annotations

import re

TURLER = ("is_karari", "teknik_arastirma", "dogrulanamadi")
TUR_ETIKET = {"is_karari": "İş Kararı", "teknik_arastirma": "Teknik Araştırma", "dogrulanamadi": "Doğrulanamadı"}

SORU_TUR_KURALI = (
    "## EK KURALLAR — Açık Soru TÜRÜ (analist yalnız GERÇEK iş kararını görür)\n\n"
    "Her açık soru bloğuna `- Tür:` satırı ekle; değer ŞUNLARDAN BİRİ:\n"
    "- `İş Kararı` — yalnız analist/PO cevaplayabilir: ürün niyeti, kapsam, iş kuralı tercihi, 'olmalı mı', hangi davranış "
    "isteniyor. Onay için analistin önüne YALNIZ bunlar çıkar. `Zorunlu: Evet` YALNIZ bu türde olabilir.\n"
    "- `Teknik Araştırma` — cevabı Swagger / canlı gözlem / kod / DB / referanstan SENİN bulman gereken konu: sıralama hangi "
    "serviste/katmanda uygulanıyor, repository/sorgu/index/collation, cache, API parametresi, kolon tipi, mevcut davranış. "
    "Bunları analiste SORMA; önce kendin araştır (Swagger bloğu, gözlem raporu, referans). Bulamadıysan bu türle yaz — "
    "agent öz-çözümlemede yeniden araştırır. Zorunlu/Kritik işaretleme.\n"
    "- `Doğrulanamadı` — araştırıldı ama kanıt/erişim yok (ör. DB index'i arayüzden görülemez): analizde teknik risk notu "
    "olarak kalır, analist kararı gerektirmez.\n"
    "SORU SAYISI işin boyutuyla orantılı: tek alan/tek tablo bug'ında EN FAZLA 3 İş Kararı sorusu. Önceki aşamada "
    "cevaplanmış (sana 'KESİN BİLGİ/CEVAPLANAN' diye verilen) konuyu YENİDEN SORMA — cevabı analize işle."
)

_TUR_SATIR = re.compile(r"(?mi)^[ \t]*[-*•]?[ \t]*\*{0,2}T[üu]r\*{0,2}\s*:\s*\*{0,2}\s*([^\n*]+?)\s*\*{0,2}\s*$")
_BLOK_BAS = re.compile(r"(?m)^(#{2,4})\s+((?:Q-T-|Q-K-|Q-|PO-)\d+)\s*:?\s*(.*)$")
_ZORUNLU_SATIR = re.compile(r"(?mi)^[ \t]*[-*•]?[ \t]*\*{0,2}Zorunlu\*{0,2}\s*:\s*\*{0,2}\s*(Evet|Yes|True|E)\b.*(?:\n|$)")
_ONCELIK = re.compile(r"(?mi)^[ \t]*[-*•]?[ \t]*\*{0,2}(?:Öncelik|Oncelik|Önem|Onem)\*{0,2}\s*:\s*\*{0,2}\s*([^\n*]+)")
_SORU_ALAN = re.compile(r"(?mi)^[ \t]*[-*•]?[ \t]*\*{0,2}Soru\*{0,2}\s*:\s*(.+)$")

# Teknik araştırma kalıpları: agent'ın kendi kaynaklarından bulabileceği şeyler.
_TEKNIK = re.compile(
    r"(hangi\s+(?:backend|be\b|bff|servis|serviste|katman|repository|repo|metot|metod|method|tablo|kolon|alan|uç|endpoint|"
    r"sorgu|query|index|indeks)|"
    r"repository|\brepo\b|\bindex\b|indeks|collation|\bcache\b|önbellek|onbellek|\bttl\b|"
    r"(?:api|servis|uç|endpoint|istek|request)\s+(?:parametre|param|query)|parametre(?:si|leri)?\s+(?:var\s*mı|destekl|alıyor|kabul)|"
    r"kolon(?:un)?\s+(?:tipi|türü|veri tipi)|veri\s+tipi|\bvarchar\b|\bstring\b\s+mi|\bnumeric\b|\bsayısal\b\s+mı|"
    r"(?:nerede|hangi\s+katmanda|sunucu(?:da)?\s+mı|client|istemci(?:de)?\s+mi|bff'?de\s+mi|backend'?de\s+mi)\s*(?:uygulan|yapıl|sırala|hesapla)|"
    r"mevcut\s+(?:implementasyon|uygulama|sorgu|davranış(?:ı)?\s+nasıl)|"
    r"(?:sıralama|sort|filtre|sayfalama|pagination)\s+(?:bff|backend|be|sunucu|client|db|veritaban)[a-zçğıöşü]*\s*(?:tarafında|'?d[ae])|"
    r"kod(?:da|unda)?\s+(?:nasıl|nerede|var\s*mı)|swagger'?da|sözleşme(?:si)?\s+(?:ne|nasıl|var\s*mı)|"
    r"uygulan[ıi]yor\b|uygulan[ıi]r\s*m[ıi]\b|tarafında\s*m[ıi]\b|"
    r"\b(?:bff|backend|sunucu|client|istemci|db|veritabanı)[a-zçğıöşü']*\s+m[ıi]\b|"
    r"hangi\s+(?:servisten|servisle|sorguyla|istekle)|tetiklen(?:iyor|en)\s+(?:istek|çağrı|servis))",
    re.I)
# İş kararı kalıpları (teknik kalıpla çakışırsa iş kararı kazanır — 'ürün ne istiyor' sorusu).
_IS = re.compile(
    r"(olmalı\s*mı|istenir\s*mi|istiyor\s*mu|tercih|ürün|product|\bpo\b|iş\s+kural|kapsam(?:a|da)?\s+(?:dahil|alın|var)|"
    r"beklenen\s+davranış|hangi\s+davranış|kabul\s+edilir\s*mi|gösteril(?:meli|sin)\s*mi|karar(?:ı)?\s+(?:verilmeli|gerek)|"
    r"onay|izin\s+verilmeli|yasak|kullanıcı(?:ya)?\s+(?:ne|hangi)|mesaj(?:ı)?\s+ne\s+olmalı|öncelik\s+(?:ne|hangi)|"
    r"olmalı(?:dır)?\b|gerekir\s*mi|isteniyor\s*mu|davranmalı|yapılmalı\s*mı|gösterilmeli)",
    re.I)
_DOGRULANAMADI = re.compile(r"(doğrulanamad|dogrulanamad|erişilemed|erisilemed|gözlemlenemed|gozlemlenemed|kanıt\s+yok|teknik\s+risk)", re.I)


def _kucuk(metin: str) -> str:
    """Türkçe-güvenli küçük harf: 'İ'.lower() → 'i̇' (nokta birleşimli) olduğundan önce İ→i, I→ı çevrilir."""
    return (metin or "").replace("İ", "i").replace("I", "ı").lower()


def tur_coz(deger: str) -> str | None:
    """Açık `Tür:` değerini normalize eder; tanınmazsa None."""
    d = _kucuk(deger).strip()
    if not d:
        return None
    if d.startswith(("iş", "is", "business", "ürün", "urun")):
        return "is_karari"
    if d.startswith(("teknik araş", "teknik aras", "araştır", "arastir", "research", "teknik")) and "risk" not in d:
        return "teknik_arastirma"
    if d.startswith(("doğrulanamad", "dogrulanamad", "teknik risk", "risk", "unverified", "erişilemed")):
        return "dogrulanamadi"
    return None


def tur_belirle(soru, govde: str = "") -> str:
    """Soru dict'i ({soru, baslik, mevcut_durum, tur…}) ya da blok metninden tür. Açık `Tür:` kazanır; yoksa kalıplar."""
    if isinstance(soru, dict):
        acik = tur_coz(soru.get("tur") or "")
        if acik:
            return acik
        metin = " ".join(str(soru.get(k) or "") for k in ("baslik", "soru", "mevcut_durum", "beklenen_yanit", "kategori"))
    else:
        metin = str(soru or "")
        m = _TUR_SATIR.search(metin)
        if m and tur_coz(m.group(1)):
            return tur_coz(m.group(1))
    metin = metin + " " + (govde or "")
    if _DOGRULANAMADI.search(metin) and not _IS.search(metin):
        return "dogrulanamadi"
    if _TEKNIK.search(metin) and not _IS.search(metin):
        return "teknik_arastirma"
    return "is_karari"


def _bloklar(md: str) -> list[dict]:
    """`### Q-…:` bloklarını (bir sonraki aynı/üst seviye başlığa kadar) döndürür."""
    out = []
    basliklar = list(_BLOK_BAS.finditer(md or ""))
    for i, m in enumerate(basliklar):
        bas = m.start()
        son = basliklar[i + 1].start() if i + 1 < len(basliklar) else len(md)
        ust = re.search(r"\n#{1,2}\s", md[m.end():son])
        if ust:
            son = m.end() + ust.start() + 1
        out.append({"id": m.group(2), "baslik": m.group(3).strip(), "bas": bas, "son": son, "metin": md[bas:son]})
    return out


def md_tur_etiketle(md: str) -> str:
    """Her soru bloğuna `- Tür: …` satırı yazar (varsa normalize eder). Soru bloğu olmayan metne dokunmaz."""
    if not md or not _BLOK_BAS.search(md):
        return md
    parcalar, son = [], 0
    for b in _bloklar(md):
        tur = tur_belirle(b["metin"])
        metin = b["metin"]
        if _TUR_SATIR.search(metin):
            metin = _TUR_SATIR.sub(f"- Tür: {TUR_ETIKET[tur]}", metin, count=1)
        else:
            satirlar = metin.split("\n")
            satirlar.insert(1, f"- Tür: {TUR_ETIKET[tur]}")
            metin = "\n".join(satirlar)
        parcalar.append(md[son:b["bas"]])
        parcalar.append(metin)
        son = b["son"]
    parcalar.append(md[son:])
    return "".join(parcalar)


_ONCELIK_SIRA = {"kritik": 0, "yüksek": 1, "yuksek": 1, "orta": 2, "düşük": 3, "dusuk": 3}


def zorunlu_normalize(md: str, tavan: int | None = None) -> str:
    """`Zorunlu: Evet` yalnız İş Kararı bloklarında kalır; `tavan` verilirse (bug/küçük iş) en yüksek öncelikli `tavan`
    kadar zorunlu kalır, diğerlerinin Zorunlu satırı silinir."""
    if not md or not _BLOK_BAS.search(md):
        return md
    bloklar = _bloklar(md)
    adaylar = []
    for b in bloklar:
        if not _ZORUNLU_SATIR.search(b["metin"]):
            continue
        if tur_belirle(b["metin"]) != "is_karari":
            b["sil"] = True
            continue
        om = _ONCELIK.search(b["metin"])
        adaylar.append((_ONCELIK_SIRA.get((om.group(1).strip().lower() if om else ""), 9), b))
    if tavan is not None and len(adaylar) > tavan:
        adaylar.sort(key=lambda x: x[0])
        for _, b in adaylar[tavan:]:
            b["sil"] = True
    parcalar, son = [], 0
    for b in bloklar:
        metin = _ZORUNLU_SATIR.sub("", b["metin"]) if b.get("sil") else b["metin"]
        parcalar.append(md[son:b["bas"]])
        parcalar.append(metin)
        son = b["son"]
    parcalar.append(md[son:])
    return "".join(parcalar)


_STOP = {"ve", "veya", "ile", "için", "icin", "mi", "mı", "mu", "mü", "bir", "bu", "şu", "ne", "nasıl", "nasil", "hangi",
         "olarak", "olan", "olacak", "var", "yok", "ise", "ama", "da", "de", "the", "and", "or", "is", "are", "to", "of"}


def _tokenler(metin: str) -> set[str]:
    kelimeler = re.findall(r"[a-zçğıöşü0-9_]{3,}", _kucuk(metin))
    return {k[:7] for k in kelimeler if k not in _STOP}


def benzer_mi(a: str, b: str, esik: float = 0.45) -> bool:
    """İki soru metni aynı konu mu (kök-kırpılmış kelime kümesi — Jaccard ya da küçük kümenin kapsanması)."""
    ta, tb = _tokenler(a), _tokenler(b)
    if not ta or not tb:
        return False
    kesisim = len(ta & tb)
    jaccard = kesisim / len(ta | tb)
    kapsama = kesisim / min(len(ta), len(tb))
    return jaccard >= esik or (kapsama >= 0.6 and min(len(ta), len(tb)) >= 4)


def cevaplananlari_ele(md: str, cevaplanan: list[dict]) -> tuple[str, list[dict]]:
    """Önceki aşamada CEVAPLANAN sorulara benzeyen yeni blokları düşürür (model 'tekrar sorma' kuralına uymasa da).
    cevaplanan: [{id, soru/baslik, cevap}]. Dönen: (md, elenenler[{id, eski_id}])."""
    if not md or not cevaplanan or not _BLOK_BAS.search(md):
        return md, []
    elenen = []
    out = md
    for b in _bloklar(md):
        sm = _SORU_ALAN.search(b["metin"])
        yeni = (b["baslik"] + " " + (sm.group(1) if sm else "")).strip()
        for c in cevaplanan:
            eski = (str(c.get("baslik") or "") + " " + str(c.get("soru") or "")).strip()
            if benzer_mi(yeni, eski):
                elenen.append({"id": b["id"], "eski_id": c.get("id", ""), "cevap": str(c.get("cevap") or "")[:200]})
                out = out.replace(b["metin"], "", 1)
                break
    if elenen:
        out = re.sub(r"\n{3,}", "\n\n", out).rstrip() + "\n\n## Önceki aşamada cevaplanmış (tekrar sorulmadı)\n" + "\n".join(
            f"- {e['id']} → {e['eski_id']}: {e['cevap']}" for e in elenen) + "\n"
    return out, elenen


def tur_sayilari(md: str) -> dict:
    s = {t: 0 for t in TURLER}
    for b in _bloklar(md or ""):
        s[tur_belirle(b["metin"])] += 1
    return s


_AGENT_DURUM = re.compile(r"(?mi)^[ \t]*[-*•]?[ \t]*\*{0,2}Agent durumu\*{0,2}\s*:\s*(.+)$")


def teknik_kalanlari_dogrulanamadi(md: str) -> tuple[str, int]:
    """Öz-çözümleme SONRASI: hâlâ cevaplanmamış 'Teknik Araştırma' blokları 'Doğrulanamadı'ya çevrilir (analist kararı
    gerektirmez — teknik risk notu olarak kalır; Zorunlu satırı silinir). Dönen: (md, çevrilen sayısı)."""
    if not md or not _BLOK_BAS.search(md):
        return md, 0
    n = 0
    parcalar, son = [], 0
    for b in _bloklar(md):
        metin = b["metin"]
        if tur_belirle(metin) == "teknik_arastirma":
            d = _AGENT_DURUM.search(metin)
            if not (d and d.group(1).strip().lower().startswith("cevap")):
                metin = _TUR_SATIR.sub("- Tür: Doğrulanamadı", metin, count=1) if _TUR_SATIR.search(metin) else metin
                metin = _ZORUNLU_SATIR.sub("", metin)
                n += 1
        parcalar.append(md[son:b["bas"]])
        parcalar.append(metin)
        son = b["son"]
    parcalar.append(md[son:])
    return "".join(parcalar), n


# ─── İş boyutu — doküman akışı (Emin 2026-11-06 #3: 3 satırlık bug için 11 bölüm + 24 soru) ───────────────────
_BUG_KELIME = re.compile(
    r"(^\s*(?:hata|bug|fix|hotfix)\s*[:\-]|çal[ıi][şs]m[ıi]yor|hata\s+(?:al[ıi]yor|veriyor|d[öo]n[üu]yor)|"
    r"\w{3,}[ae]m[ıi]yor\b|yanlış\s+(?:göster|sırala|hesapla|çalış)|hatalı|bozuk|sorun[u]?\b|"
    r"\bbug\b|düzelt(?:il|me)|beklendiği gibi\s+(?:çalışm|gelm|görünm))", re.I)
_JIRA_KEY = re.compile(r"\b([A-Z][A-Z0-9]{2,}-\d+)\b")
BUG_GIRDI_KC = 2_500


def bug_modu_mu(metin: str, girdi_kc: int | None = None) -> bool:
    """Girdi küçük bir hata/düzeltme işi mi? Kısa metin (≤ BUG_GIRDI_KC) + başlık/ilk satırlarda hata ifadesi.
    Uzun BRD'lerde (çok ekranlı iş) 'hata' kelimesi geçse de False."""
    m = (metin or "").strip()
    uzunluk = girdi_kc if girdi_kc is not None else len(m)
    if not m or uzunluk > BUG_GIRDI_KC:
        return False
    return bool(_BUG_KELIME.search(m[:600]))


def jira_anahtari(metin: str) -> str:
    m = _JIRA_KEY.search(metin or "")
    return m.group(1) if m else ""


KISA_MOD_SUREC = (
    "\n\n## ÇIKTI MODU: HATA/BASİT İŞ — KISA-NET (girdi küçük bir düzeltme)\n"
    "Bu girdi tek alan/tek ekranlık bir hata ya da küçük düzeltme. Standart şablonun yalnız İLGİLİ bölümlerini doldur: "
    "Amaç (sorun + beklenen davranış), İş Gereksinimleri (en fazla 3 BR), Ana Akış (yalnız işin dokunduğu adım), Etki Analizi "
    "(tek tablo satırı), Kabul Kriterleri (2-4). İlgisiz bölümleri (paydaş listesi, alternatif akışlar, KPI, rol matrisi vb.) "
    "ATLA — boş başlık yazma. ID şeması (PA-/BR-/AC-) KORUNUR. Açık soru: EN FAZLA 3 ve yalnız İş Kararı türünde; teknik "
    "noktaları (hangi serviste, kolon tipi, sıralama katmanı) soru yapma — Teknik Notlar'a 'gözlem/kaynakla doğrulanacak' yaz."
)
KISA_MOD_TEKNIK = (
    "\n\n## ÇIKTI MODU: HATA/BASİT İŞ — KISA-NET (kaynak girdi küçük bir düzeltme)\n"
    "Geliştirici 20 saniyede ne yapacağını anlamalı. Yalnız şu bölümler: 1. Amaç (sorun + kök neden — Swagger/gözlem/kaynak "
    "kanıtıyla), 2. İş Gereksinimleri (süreç BR ID'leriyle), 3. Teknik Gereksinimler (değişecek nokta: servis/uç/alan/sorgu), "
    "5. API Tasarımı (yalnız değişen uç/parametre), 9. Hata Yönetimi (gerekiyorsa), 11. Kabul Kriterleri (2-4). DB/Role/"
    "Algoritma/Teknik Borç bölümlerini işin dokunmadığı sürece ATLA. Kök nedeni ANALİSTE SORMA — kaynaklardan bul; "
    "bulamadıysan `[K: ❓ Belirsiz]` + 'Doğrulanamadı' notu."
)
