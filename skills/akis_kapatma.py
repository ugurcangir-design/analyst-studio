"""Akış Kapatma (Faz 3) — analizdeki süreç/işleyiş boşluklarını bulur ve YERİNDE kapatır.

Faz 1'deki bütünlük kuralları modelin kendi kontrolüdür, Faz 2'deki akış bütünlük denetimi boşluğu
yalnız GÖSTERİR. Bu adım boşluğu KAPATIR:
  1. Tespit (1 AI çağrısı): analiz + kaynak (süreç: girdi doküman · teknik: süreç analizi · Task: görev)
     uçtan uca yürütülür → gerçek boşluklar (ekran eşleşmesi, giriş-çıkış, karar dalı, veri sürekliliği,
     etki, tanımsız referans). Kozmetik/üslup YOK, en fazla 8.
  2. Kapatma: bilgi analizde ya da kaynakta VARSA yalnız ilgili bölüm minimal düzenlenir (bölüm başına
     1 AI çağrısı, aynı bölümün boşlukları birleşir). Korumalar: başlık korunur · kısalma yok (kesik çıktı)
     · büyüme sınırı (analiz BÜYÜMESİN) → ihlalde düzeltme reddedilir, boşluk açık soruya döner.
  3. Bilgi yoksa açık soru (riskliyse `Zorunlu: Evet`).

Dosya tabanlı akışlarda (süreç/teknik) sonuç TEK revizyon olarak kaydedilir → Revizyon ekranından
Geri Al. Özet `output/.akis-kapatma.json` (onay kapısında "N boşluk kapatıldı · M soru açıldı").
Kapatma: `.env` `AKIS_KAPATMA=false` ya da `HIZLI_MOD=true`. Hata → analiz ASLA kırılmaz (None döner).
"""

from __future__ import annotations

import json
import os
import re
import time

from .base import (
    OUTPUT_DIR, MAX_TOKENS_KISA, MAX_TOKENS_UZUN,
    _api_cagri, _xml_ayir, hizli_mod_acik,
)
from .revizyon_ai import bolum_bul, bolumlere_ayir

RAPOR_DOSYA = OUTPUT_DIR / ".akis-kapatma.json"
_MAX_BOSLUK = 8
_MAX_BOLUM_KRK = 30_000      # bundan büyük bölüm düzenlenmez (çıktı kesilme riski) → soru
_MAX_ANALIZ_KRK = 60_000
_MAX_KAYNAK_KRK = 30_000
_TURLER = {
    "ekran_eslesme": "Süreç ↔ ekran",
    "giris_cikis": "Giriş–çıkış",
    "karar_dali": "Karar dalı",
    "veri_surekliligi": "Veri sürekliliği",
    "etki": "Etki",
    "tanimsiz": "Tanımsız referans",
}

_TESPIT_SISTEM = """# ROL
Kıdemli iş/sistem analistisin. Görevin bir analiz dokümanındaki akışı uçtan uca zihninde yürütüp,
geliştirme yapılırken ya da test edilirken süreçsel/işleyiş olarak takılınacak BOŞLUKLARI bulmak.
Amaç analizi büyütmek DEĞİL; akışı kapatmak.

# NE ARANIR (yalnız GERÇEK boşluk)
- ekran_eslesme: süreç adımının ekranda karşılığı yok · buton/aksiyonun süreçte işlevi tanımsız · ekran hiçbir adıma bağlı değil
- giris_cikis: akışın başlangıç koşulu ya da bir aksiyondan sonra ekranın durumu/yönlendirmesi tanımsız
- karar_dali: bir koşulun dalı (hatalı/boş/yok/yetkisiz) tanımsız ya da dalın ana akışa dönüşü belirsiz
- veri_surekliligi: girilen/değişen veri sonraki adımda ya da onu gösteren ekranda kopuk · durum (status) geçişi eksik
- etki: değişikliğin etkilediği ekran/süreç akışta işlenmemiş
- tanimsiz: tanımı olmayan adım/akış/ekran referansı

# NE ARANMAZ
Kozmetik, üslup, biçim, "daha detaylı olabilir" önerisi, analiz kapsamı dışı konu, ZATEN açık soru olarak
sorulmuş konu. Boşluk yoksa boş liste dön. EN FAZLA 8 boşluk — en kritik olanlar.

# KAPATMA KARARI
- "duzelt": boşluğu kapatacak bilgi analizin KENDİSİNDE ya da verilen KAYNAKTA AÇIKÇA var. "talimat":
  hangi öğede NEYİN minimal eklenip düzeltileceği, bilgiyle birlikte (bir cümle / bir tablo satırı / bir
  dönüş noktası düzeyinde; yeni bölüm YOK). Kaynakta olmayan bilgiyle düzeltme ÖNERME.
- "soru": bilgi yok → "soru": analist/PO'ya net, tek konulu soru. Cevapsız kalırsa veri kaybı/bozulma,
  başka ekranın kırılması ya da testin beklenen sonucunun bilinmemesi doğuyorsa "zorunlu": true.
- "hedef": boşluğun bulunduğu öğenin ID'si (PA-003, EK-002, AF-001, BR-004, T-BE-02…) ya da ID yoksa
  bulunduğu bölüm başlığının metni.

# ÇIKTI
Yalnız şu blok, içinde JSON dizi:
<akis_bosluklari>[{"hedef": "", "tur": "", "bosluk": "", "kapatma": "duzelt", "talimat": "", "soru": "", "zorunlu": false}]</akis_bosluklari>"""

_DUZELT_SISTEM = """# ROL
Bir analiz dokümanının TEK bir bölümünde akış boşluklarını cerrahi hassasiyetle kapatan kıdemli analistsin.

# GÖREV
Aşağıdaki boşlukları bu bölümde MİNİMAL değişiklikle kapat:
{talimatlar}

# KESİN KURALLAR
- Yalnız eksik halkayı ekle/düzelt (bir cümle, bir tablo satırı, bir dönüş noktası). Mevcut içeriği yeniden
  YAZMA, KISALTMA, genişletme; ilgisiz satıra dokunma.
- Yeni bilgi UYDURMA — yalnız talimattaki bilgiyi kullan. Kaynak etiketlerini ([K: …]) ve ID'leri koru.
- Bölümün başlık satırını AYNEN koru. Yalnız düzenlenmiş bölümü döndür — açıklama, giriş/kapanış cümlesi YOK.

# BÖLÜM
{bolum}"""


def etkin() -> bool:
    """`AKIS_KAPATMA=false` ya da HIZLI_MOD → kapalı (token tasarrufu)."""
    if (os.getenv("AKIS_KAPATMA", "true") or "").strip().lower() in ("false", "0", "hayir", "no"):
        return False
    try:
        return not hizli_mod_acik()
    except Exception:
        return True


# ── 1) Tespit ────────────────────────────────────────────────────────────────
def _json_dizi(metin: str) -> list:
    ham = _xml_ayir(metin or "", "akis_bosluklari")
    try:
        d = json.loads(ham)
    except Exception:
        bas, son = ham.find("["), ham.rfind("]")
        if bas == -1 or son <= bas:
            return []
        try:
            d = json.loads(ham[bas:son + 1])
        except Exception:
            return []
    return d if isinstance(d, list) else []


def _normalize(liste: list) -> list[dict]:
    sonuc: list[dict] = []
    for b in liste:
        if not isinstance(b, dict):
            continue
        hedef = str(b.get("hedef") or "").strip()
        bosluk = str(b.get("bosluk") or "").strip()
        if not bosluk:
            continue
        kapatma = "duzelt" if str(b.get("kapatma") or "").strip().lower() == "duzelt" else "soru"
        talimat = str(b.get("talimat") or "").strip()
        if kapatma == "duzelt" and (not talimat or not hedef):
            kapatma = "soru"
        z = b.get("zorunlu")
        sonuc.append({
            "hedef": hedef, "tur": str(b.get("tur") or "").strip(), "bosluk": bosluk,
            "kapatma": kapatma, "talimat": talimat,
            "soru": str(b.get("soru") or "").strip() or bosluk,
            "zorunlu": z is True or str(z).strip().lower() in ("true", "evet", "yes", "1"),
        })
        if len(sonuc) >= _MAX_BOSLUK:
            break
    return sonuc


def _tespit_ai(analiz: str, kaynak: str, ek_bulgular: str, tip: str) -> list[dict]:
    icerik = [{"type": "text", "text": f"### Analiz ({tip})\n\n{analiz[:_MAX_ANALIZ_KRK]}"}]
    if kaynak.strip():
        icerik.append({"type": "text", "text": f"### Kaynak\n\n{kaynak[:_MAX_KAYNAK_KRK]}"})
    if ek_bulgular.strip():
        icerik.append({"type": "text", "text": "### Deterministik akış denetimi bulguları (bunları da değerlendir)\n\n"
                                               + ek_bulgular.strip()})
    icerik.append({"type": "text", "text": "Akışı uçtan uca yürüt ve boşlukları çıkar."})
    yanit = _api_cagri(_TESPIT_SISTEM, [{"role": "user", "content": icerik}],
                       max_tokens=MAX_TOKENS_KISA, thinking=False)
    return _normalize(_json_dizi(yanit))


# ── 2) Kapatma ───────────────────────────────────────────────────────────────
def _hedef_bolum(md: str, hedef: str) -> dict | None:
    """Boşluğun düzeltileceği bölüm: hedef bir ID ise ID'nin TANIMLANDIĞI satırı (`**PA-001:**`,
    `| BR-002 |`, başlıkta ID) içeren EN DERİN bölüm — ID'nin yalnız ATIF aldığı bölüm değil
    (ör. 'Bağlı adım: PA-001' yazan ekran). Tanım bulunamazsa revizyon_ai.bolum_bul davranışı."""
    m = re.fullmatch(r"\s*([A-Za-z]{1,5}(?:-[A-Za-z]{1,3})?-\d{1,4})\s*", hedef or "")
    if m:
        i = re.escape(m.group(1))
        t = re.search(rf"(?:^\|\s*|\*\*|^#{{1,6}}[^\n]*?)\b{i}\b", md, re.MULTILINE)
        if t:
            adaylar = [b for b in bolumlere_ayir(md)
                       if b["seviye"] > 0 and b["baslangic"] <= t.start() < b["bitis"]]
            if adaylar:
                return max(adaylar, key=lambda b: b["seviye"])
    return bolum_bul(md, hedef)


def _duzelt_ai(talimatlar: str, bolum: str) -> str:
    sistem = _DUZELT_SISTEM.format(talimatlar=talimatlar, bolum=bolum)
    # Çıktı = bölümün tamamı → limit bölüm boyuna göre (Türkçe ~2.5 krk/token) + pay
    limit = min(MAX_TOKENS_UZUN, max(MAX_TOKENS_KISA, int(len(bolum) / 2.5) + 1500))
    return _api_cagri(sistem, [{"role": "user", "content": [
        {"type": "text", "text": "Boşlukları bu bölümde kapat ve yalnız bölümü döndür."}]}],
        max_tokens=limit, onbellek=False)


def _ilk_satir(metin: str) -> str:
    return (metin.strip().splitlines() or [""])[0].strip()


def _duzeltme_gecerli(eski: str, yeni: str) -> str | None:
    """Kabul → None; red → neden. Analiz BÜYÜMESİN + kesik/bozuk çıktı geri yazılmasın."""
    if not yeni.strip():
        return "boş çıktı"
    if _ilk_satir(eski).lstrip("#").strip() != _ilk_satir(yeni).lstrip("#").strip():
        return "başlık değişti"
    if len(yeni) < len(eski) * 0.9:
        return "bölüm kısaldı (kesik/silinmiş içerik)"
    if len(yeni) - len(eski) > max(600, int(len(eski) * 0.5)):
        return "fazla büyüdü"
    return None


def akis_kapat(analiz: str, kaynak: str = "", tip: str = "surec", ek_bulgular: str = "",
               *, _tespit_fn=None, _duzelt_fn=None) -> dict:
    """Saf çekirdek (dosyaya dokunmaz): {markdown, sorular:[boşluk…], rapor}.
    `_tespit_fn(analiz, kaynak, ek, tip)` / `_duzelt_fn(talimatlar, bolum)` yalnız test enjeksiyonu."""
    tespit = _tespit_fn or _tespit_ai
    duzelt = _duzelt_fn or _duzelt_ai
    bosluklar = tespit(analiz, kaynak, ek_bulgular, tip)
    md = analiz
    sorular = [b for b in bosluklar if b["kapatma"] == "soru"]
    reddedilen: list[dict] = []
    kapatilan: list[dict] = []

    # Aynı bölümün boşluklarını tek çağrıda birleştir (bölüm ilk çözümlemede belirlenir)
    gruplar: dict[tuple, list[dict]] = {}
    for b in (x for x in bosluklar if x["kapatma"] == "duzelt"):
        bol = _hedef_bolum(md, b["hedef"])
        if bol is None or len(bol["icerik"]) > _MAX_BOLUM_KRK:
            b["neden"] = "bölüm bulunamadı" if bol is None else "bölüm çok büyük"
            sorular.append(b)
            reddedilen.append(b)
            continue
        gruplar.setdefault((bol["baslik"], bol["baslangic"]), []).append(b)

    for (_baslik, _), grup in gruplar.items():
        # Önceki düzeltmeler ofsetleri kaydırmış olabilir → bölümü GÜNCEL metinde yeniden bul
        bol = _hedef_bolum(md, grup[0]["hedef"])
        neden = None
        if bol is None:
            neden = "bölüm bulunamadı"
        else:
            talimatlar = "\n".join(f"- [{b['hedef']}] {b['talimat']}" for b in grup)
            try:
                yeni = duzelt(talimatlar, bol["icerik"]).strip("\n") + "\n"
                kuyruk = "\n" if bol["icerik"].endswith("\n\n") else ""
                neden = _duzeltme_gecerli(bol["icerik"], yeni)
                if neden is None:
                    md = md[:bol["baslangic"]] + yeni + kuyruk + md[bol["bitis"]:]
            except Exception as e:
                neden = f"düzeltme hatası: {e}"
        if neden:
            for b in grup:
                b["neden"] = neden
                sorular.append(b)
                reddedilen.append(b)
        else:
            kapatilan.extend(grup)

    rapor = {
        "ts": time.time(), "tip": tip,
        "bosluk": len(bosluklar), "kapatilan": len(kapatilan), "soru": len(sorular),
        "zorunlu": sum(1 for b in sorular if b["zorunlu"]), "reddedilen": len(reddedilen),
        "detay": [{"hedef": b["hedef"], "tur": _TURLER.get(b["tur"], b["tur"]), "bosluk": b["bosluk"][:200],
                   "sonuc": "kapatıldı" if b in kapatilan else "soru", "neden": b.get("neden", "")}
                  for b in bosluklar][:20],
    }
    return {"markdown": md, "sorular": sorular, "rapor": rapor}


# ── 3) Açık soru blokları ────────────────────────────────────────────────────
def soru_bloklari(sorular: list[dict], onek: str, mevcut_metin: str) -> str:
    """Boşlukları `### <onek>-NNN:` soru bloklarına çevirir (numara mevcut en büyükten devam eder)."""
    if not sorular:
        return ""
    desen = re.compile(rf"\b{re.escape(onek)}-(\d+)\b")
    no = max((int(m) for m in desen.findall(mevcut_metin or "")), default=0)
    bloklar: list[str] = []
    for b in sorular:
        no += 1
        baslik = (b["bosluk"][:70] + ("…" if len(b["bosluk"]) > 70 else "")).replace("\n", " ")
        satirlar = [f"### {onek}-{no:03d}: {baslik}",
                    "- Kategori: Akış Bütünlüğü" + (f" ({_TURLER[b['tur']]})" if b["tur"] in _TURLER else ""),
                    f"- Öncelik: {'Kritik' if b['zorunlu'] else 'Yüksek'}"]
        if b["zorunlu"]:
            satirlar.append("- Zorunlu: Evet")
        if re.search(r"[A-Z]{1,4}(?:-[A-Z]{1,3})?-\d{1,4}", b["hedef"]):
            satirlar.append(f"- Bağlı ID: {b['hedef']}")
        satirlar += [f"- Soru: {b['soru']}", f"- Mevcut Durum: {b['bosluk']}",
                     "- Etki: Cevaplanmazsa akışın bu noktası geliştirme/testte açık kalır."]
        bloklar.append("\n".join(satirlar))
    return "\n\n".join(bloklar) + "\n"


_DENETIM_AYRAC = re.compile(r"\n---\n\n## (?:🔎|🔗|🔍)")


def sorulari_analize_ekle(md: str, bloklar: str) -> str:
    """Soru bloklarını analizin Açık Sorular bölümünün SONUNA ekler (otomatik denetim bölümlerinden önce).
    Açık Sorular bölümü yoksa gövdenin sonuna başlıkla ekler."""
    if not bloklar:
        return md
    m = _DENETIM_AYRAC.search(md)
    govde, kuyruk = (md[:m.start()], md[m.start():]) if m else (md, "")
    if not re.search(r"^#{1,4}\s+[^\n]*(?:Açık Sorular|Karar Bekleyen)", govde, re.MULTILINE):
        bloklar = "### Açık Sorular / Karar Bekleyen Konular\n\n" + bloklar
    return govde.rstrip("\n") + "\n\n" + bloklar + kuyruk


# ── 4) Dosya tabanlı akış (süreç / teknik) ───────────────────────────────────
def _rapor_kaydet(dosya: str, rapor: dict) -> None:
    try:
        veri = json.loads(RAPOR_DOSYA.read_text(encoding="utf-8")) if RAPOR_DOSYA.exists() else {}
    except Exception:
        veri = {}
    veri[dosya] = rapor
    RAPOR_DOSYA.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")


def rapor_oku(dosya: str, taze_esik: float | None = None) -> dict | None:
    """Dosyanın son akış kapatma özeti (taze_esik verilirse yalnız bu oturuma ait olan)."""
    try:
        r = json.loads(RAPOR_DOSYA.read_text(encoding="utf-8")).get(dosya)
    except Exception:
        return None
    if not r or (taze_esik is not None and r.get("ts", 0) < taze_esik):
        return None
    return r


def _revizyon_kaydet(dosya: str, once: str, sonra: str, rapor: dict) -> None:
    """Akış kapatmayı TEK revizyon olarak kaydet → Revizyon ekranından Geri Al."""
    from . import revizyon
    revizyon.yeniden_bazla(dosya, once, not_="Üretim (akış kapatma öncesi)")
    rev = revizyon.revizyon_oner(
        dosya, sonra, tip="bolum", istek="Otomatik akış kapatma",
        ozet=f"Akış kapatma: {rapor['kapatilan']} boşluk kapatıldı · {rapor['soru']} soru açıldı",
        degisen_bolumler=[{"section": d["hedef"], "changeType": "updated", "reason": d["bosluk"][:160]}
                          for d in rapor["detay"] if d["sonuc"] == "kapatıldı"])
    revizyon.onayla(dosya, rev["id"])


def dosya_akis_kapat(dosya: str, kaynak: str = "", tip: str = "surec",
                     soru_dosya: str | None = None, ek_bulgular: str = "") -> dict | None:
    """output/<dosya> üzerinde akış kapatma. Sorular: `soru_dosya` verilirse ona (teknik → acik-sorular.md,
    Q-T öneki) eklenir, yoksa analizin kendi Açık Sorular bölümüne (süreç → Q öneki).
    Kapalıysa/hata → None (analiz etkilenmez)."""
    if not etkin():
        print("  ⏭ Akış kapatma kapalı (AKIS_KAPATMA=false / HIZLI_MOD).")
        return None
    yol = OUTPUT_DIR / dosya
    try:
        once = yol.read_text(encoding="utf-8")
        print("  🔗 Akış kapatma: analiz uçtan uca yürütülüyor (boşluk tespiti)...")
        s = akis_kapat(once, kaynak, tip, ek_bulgular)
        sonra = s["markdown"]
        if soru_dosya:
            syol = OUTPUT_DIR / soru_dosya
            mevcut = syol.read_text(encoding="utf-8") if syol.exists() else "# Açık Sorular\n"
            bloklar = soru_bloklari(s["sorular"], "Q-T", mevcut)
            if bloklar:
                mevcut = re.sub(r"(?im)^\s*Açık soru tespit edilmedi\.?\s*$", "", mevcut)
                syol.write_text(mevcut.rstrip("\n") + "\n\n" + bloklar, encoding="utf-8")
        else:
            sonra = sorulari_analize_ekle(sonra, soru_bloklari(s["sorular"], "Q", once))
        if sonra != once:
            yol.write_text(sonra, encoding="utf-8")
            try:
                _revizyon_kaydet(dosya, once, sonra, s["rapor"])
            except Exception as e:
                print(f"  ⚠ Akış kapatma revizyon kaydı atlandı (analiz güncellendi): {e}")
        _rapor_kaydet(dosya, s["rapor"])
        r = s["rapor"]
        print(f"  🔗 Akış kapatma: {r['bosluk']} boşluk · {r['kapatilan']} kapatıldı · {r['soru']} soru"
              + (f" ({r['zorunlu']} zorunlu)" if r["zorunlu"] else ""))
        return r
    except Exception as e:
        print(f"  ⚠ Akış kapatma atlandı (analiz etkilenmedi): {e}")
        return None


# ── 5) Task analizi (bellek içi) ─────────────────────────────────────────────
def gorev_akis_kapat(markdown: str, acik_sorular: str, gorev: dict) -> dict:
    """Task analizi için: {markdown, acik_sorular, akis_rapor}. Sorular görevin açık sorularına (Q-T) eklenir."""
    kaynak = f"Görev {gorev.get('key', '')}: {gorev.get('summary', '')}\n\n{gorev.get('description', '') or ''}"
    s = akis_kapat(markdown, kaynak, "gorev")
    bloklar = soru_bloklari(s["sorular"], "Q-T", acik_sorular)
    yeni_sorular = acik_sorular
    if bloklar:
        temel = re.sub(r"(?im)^\s*Açık soru tespit edilmedi\.?\s*$", "", acik_sorular or "").strip()
        yeni_sorular = (temel + "\n\n" if temel else "") + bloklar
    return {"markdown": s["markdown"], "acik_sorular": yeni_sorular, "akis_rapor": s["rapor"]}
