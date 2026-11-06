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
import os
import re
import secrets
import time
from pathlib import Path

from urllib.parse import urlparse

from .base import (
    _api_cagri, _xml_ayir, _metin_sikistir, OUTPUT_DIR,
    referans_dosyalari_hazirla, _ref_bloklari_olustur,
    _domain_kurallari_oku, canli_uygulama_baglami_hazirla, live_app_urls,
    MAX_TOKENS_COMBINED, MAX_TOKENS_KISA,
)
from . import base as _base

_SOHBET_DIR = OUTPUT_DIR / "sohbet"
_OTURUM_DOSYA = _SOHBET_DIR / "oturum.json"
_EK_DIR = _SOHBET_DIR / "ekler"          # analistin sohbete eklediği ekran görüntüleri (gitignore: output/)
_EK_UZANTILAR = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_EK_AZAMI_BAYT = 8 * 1024 * 1024
_EK_AD = re.compile(r"^ek-\d+-[0-9a-f]{6}\.(png|jpg|jpeg|webp|gif)$")


# ─── Ekran görüntüsü ekleri (owner 2026-11-05: 'sohbete ekran görüntüsü ekleyebilmek istiyorum') ───

def ek_kaydet(dosya_adi: str, veri: bytes) -> dict:
    """Görseli `output/sohbet/ekler/` altına güvenli adla yazar → {ad, yol, boyut}. PNG/JPG/WEBP/GIF, ≤8 MB."""
    uz = Path(dosya_adi or "").suffix.lower()
    if uz not in _EK_UZANTILAR:
        raise ValueError("Yalnız görsel eklenebilir (PNG/JPG/WEBP/GIF).")
    if not veri:
        raise ValueError("Boş dosya.")
    if len(veri) > _EK_AZAMI_BAYT:
        raise ValueError("Görsel 8 MB'tan büyük olamaz.")
    _EK_DIR.mkdir(parents=True, exist_ok=True)
    ad = f"ek-{int(time.time() * 1000)}-{secrets.token_hex(3)}{uz}"
    yol = _EK_DIR / ad
    yol.write_bytes(veri)
    return {"ad": ad, "yol": str(yol), "boyut": len(veri)}


def ek_yolu(ad: str) -> Path | None:
    """Kayıtlı ek adı → dosya yolu (ad deseni dışı / olmayan → None; yol gezinmesi imkânsız)."""
    if not ad or not _EK_AD.match(ad):
        return None
    y = _EK_DIR / ad
    return y if y.is_file() else None


def _ekleri_dogrula(ekler) -> list[str]:
    return [a for a in (ekler or []) if isinstance(a, str) and ek_yolu(a)]


def _ek_icerik(ekler: list[str], gorsel_olarak: bool) -> tuple[list[dict], list[str]]:
    """Mesajın eklerini model içeriğine çevirir. gorsel_olarak=True (API modu) → image bloğu; False (CLI) → mutlak yol
    notu (model `Read` ile açar). Dönen: (içerik blokları, Read'e açılacak yollar)."""
    bloklar: list[dict] = []
    yollar: list[str] = []
    for ad in ekler:
        y = ek_yolu(ad)
        if not y:
            continue
        if gorsel_olarak:
            try:
                bloklar.append(_base.gorsel_hazirla(y))
                bloklar.append({"type": "text", "text": f"(Yukarıdaki görsel: analistin eklediği ekran görüntüsü `{ad}`)"})
                continue
            except Exception:
                pass
        yollar.append(str(y.resolve()))
        bloklar.append({"type": "text", "text": f"[EKRAN GÖRÜNTÜSÜ EKİ — `Read` aracıyla AÇ ve gördüğünü yanıtında kullan: {y.resolve()}]"})
    return bloklar, yollar


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
    "- Türkçe yaz; teknik terimler İngilizce kalabilir.\n\n"
    "ÇALIŞMA BİÇİMİ (analist adım adım ilerler — bunlara UY):\n"
    "- İSTENEN ÇIKTIYI ÜRET: analist somut bir çıktı istediyse (örnek analiz, tespit listesi, karşılaştırma tablosu, kabul "
    "kriterleri, ekran listesi) 'kısa yanıt' kuralı o tur için GEÇERSİZDİR — istenen çıktıyı eldeki kanıtla (gözlem raporu, "
    "referans, BFF raporu) EKSİKSİZ üret; 'bir sonraki turda yapalım' deme, bilinmeyeni `[K: ❓ Belirsiz]` işaretle.\n"
    "- KARAR VER: analist 'karar ver / karar vererek ilerleyelim' dediyse soru sormak yerine kararı ver (ne, neden, kanıt); "
    "yalnız kararı GERÇEKTEN değiştirecek tek belirsizlik varsa onu sor.\n"
    "- SIRAYLA SOR: aynı anda EN FAZLA BİR (zorunluysa iki) netleştirici soru sor; analist cevaplayınca "
    "bir sonrakine geç. Soru listesi dökme.\n"
    "- BRD YÜKLENMEZ, REFERANSTA HAZIRDIR: 'BRD'deki X isteri' dendiğinde REFERANS BAĞLAM'daki BRD "
    "parçalarını kullan ve atıf ver; bulamıyorsan 'BRD'de bu ekran/ister için metin bulamadım' de, uydurma.\n"
    "- CANLI GÖZLEM: analist mesajı '🌐 Gözlemle' ile gönderdiyse sana CANLI UYGULAMA GÖREVİ verilir — "
    "uygulamayı GERÇEKTEN gez, gördüğünü (ekran, kolon, buton var/yok, servis) sohbet tonunda yaz. Normal "
    "turda uygulamayı açma. Giriş reddedilirse tekrar deneme; 'Girişi Test Et' ile hesabın düzeltilmesini iste.\n"
    "- EKRAN GÖRÜNTÜSÜ EKİ: analist mesajına ekran görüntüsü eklediyse (görsel ya da 'EKRAN GÖRÜNTÜSÜ EKİ … Read' notu) "
    "önce onu AÇ/incele; gördüğün ekran/alan/hata mesajını yanıtında somut olarak kullan (hangi ekran, hangi alan, ne "
    "yazıyor). Görseli açamadıysan bunu söyle, tahmin etme.\n"
    "- ANALİSTİN CEVAPLADIĞI AÇIK SORULAR sana 'CEVAPLANAN SORULAR' bloğunda gelir — bunları KESİN kabul et, "
    "tekrar sorma.\n"
    "- HEDEF ÇIKTI: iş EKRAN BAZLIDIR. Kapsam netleşince (hangi ekranlar, her ekranda ne) analiste "
    "'Ekran Task'ları Üret' adımını öner: her ekran için ayrı FE+BE analiz üretilir ve Jira'ya ekran başına "
    "FE/BE task açılır. 'Süreç/Teknik Analizi Üret' TEK doküman içindir — ekran bazlı işte onu değil bunu öner.\n"
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


# ─── Canlı uygulama (miras live_app ana adresi + sohbetten hedef) ─────────────

def _canli_tabanli_baglam(hedef_tarif: str) -> str | None:
    """Süreç/Teknik ekranından MİRAS alınan canlı uygulama URL'inin ANA adresi (base) + verilen hedef
    tarifiyle canlı gözlem görevi. URL yoksa None (gözlem yapılamaz, sessizce atlanır)."""
    urls = live_app_urls()
    if not urls:
        return None
    p = urlparse(urls[0])
    if not (p.scheme and p.netloc):
        return None
    # kapsam_birlestir=False: sohbet mesajı kapsamın KENDİSİ — Süreç ekranının Bağlam Filtresi'ndeki (başka doküman için
    # girilmiş) 'gözlem kapsamı' EKLENMEZ. Aksi hâlde gözlemci analistin istediği ekran yerine o eski kapsamı arıyordu
    # (bulgu 2026-11-05: 'Sport Basic Data ekranlarını tara' dendi, rapor 'Match Status filtresi / Match Info kolonu' aradı).
    return canli_uygulama_baglami_hazirla(base_url_override=f"{p.scheme}://{p.netloc}",
                                          hedef_tarif=(hedef_tarif or "").strip() or "Ana ekran",
                                          kapsam_birlestir=False)


def _cevaplanan_sorular_metni() -> str:
    """Analistin Sorular defterinde (bu oturumda) cevapladığı/varsayım girdiği sorular → sohbet ve üretim
    bağlamına KESİN bilgi olarak girer (tekrar sorulmaz). Best-effort; hata → ''."""
    try:
        from .sorular import cevaplanan_sorular_metni
        o = oturum_oku()
        mesajlar = o.get("mesajlar") or []
        esik = min((m.get("ts") or 0) for m in mesajlar) if mesajlar else (o.get("created") or 0)
        return cevaplanan_sorular_metni(esik or None)
    except Exception:
        return ""


# ─── Sohbet gözlem raporları (Task Analizi formatında üretime taşınır — owner 2026-11-06) ───────────────────────

def _gozlem_kaydet(rapor: dict, hedef: str) -> None:
    """Başarılı 🌐 gözlem raporunu oturuma bağlar (`oturum.gozlemler[]`: anahtar/ts/hedef) → ekran envanteri ve ekran
    task'ları aynı raporu YENİDEN GÖZLEMEDEN kullanır."""
    try:
        o = oturum_oku()
        liste = [g for g in (o.get("gozlemler") or []) if g.get("anahtar") != rapor.get("anahtar")]
        liste.append({"anahtar": rapor.get("anahtar"), "ts": time.time(), "hedef": (hedef or "")[:200]})
        o["gozlemler"] = liste[-10:]
        _oturum_yaz(o)
    except Exception as e:
        print(f"  ⚠ Gözlem raporu oturuma yazılamadı: {e}")


def son_gozlem_raporu(oturum: dict | None = None) -> dict | None:
    """Bu oturumun EN TAZE (geçerlilik süresi içinde, ok) 🌐 gözlem raporu; yoksa None."""
    try:
        from . import gozlem as _gz
        o = oturum or oturum_oku()
        for g in reversed(o.get("gozlemler") or []):
            r = _gz.rapor_oku(g.get("anahtar") or "")
            if _gz.taze_mi(r):
                return r
    except Exception:
        pass
    return None


def ekran_sonucu_bildir(key: str, baslik: str, be_is, fe_is, hata: str = "") -> None:
    """Ekran task'ı (EKRAN-n) Task Analizi'nde bitince sohbete sistem mesajı: katman kararı + yönlendirme (best-effort)."""
    try:
        def _k(v):
            return "iş VAR" if v is True else ("iş YOK" if v is False else "belirsiz")
        if hata:
            metin = f"⚠ **{baslik}** ({key}) ekran analizi üretilemedi: {hata[:200]}"
        else:
            metin = (f"🧩 **{baslik}** ({key}) — Task Analizi formatında FE+BE analiz hazır: **BE {_k(be_is)} · FE {_k(fe_is)}**. "
                     "Task Analizi ekranında inceleyin; Jira'ya **'Yeni Task Aç'** (BE+FE, Blocks) ile açın.")
        o = oturum_oku()
        o["mesajlar"].append({"rol": "agent", "sistem": True, "ts": time.time(), "metin": metin, "task_analizi": True})
        _oturum_yaz(o)
    except Exception as e:
        print(f"  ⚠ Ekran sonucu sohbete yazılamadı: {e}")


# ─── Sohbet gözlem hedefi ────────────────────────────────────────────────────

# Gözlem turu yanıt talimatı (owner 2026-11-05: 'isteklerimi yapmıyor — tespit ve örnek analiz istedim'): eski talimat
# 'raporu KISA sohbet yanıtına çevir, sonunda bir sonraki adımı öner' diyordu → model analistin asıl isteğini (tespit +
# örnek analiz + karar) bırakıp özet + yeni tur önerisiyle yetiniyordu. Rapor KANIT'tır, çıktı analistin İSTEĞİ'dir.
_GOZLEM_TURU_TALIMAT = (
    "### 🌐 CANLI GÖZLEM TURU\nYukarıdaki gözlem raporu analistin SON mesajı için az önce yapıldı. Rapor senin KANIT kaynağındır; "
    "yanıtın ise analistin SON MESAJINDA İSTEDİĞİ ÇIKTIDIR — raporu özetlemekle yetinme.\n"
    "- Analist ne istediyse onu TAM üret: 'tespit' dediyse gözlenen ekran/alan/davranışların tespit listesi; 'örnek analiz' "
    "dediyse bulunan HER ekran için örnek analiz (aşağıdaki şablon); 'tablo' dediyse tablo; 'kabul kriteri' dediyse kriterler. "
    "İstek birden çok parçaysa hepsini yaz, hiçbirini sonraki tura erteleme.\n"
    "- 'Karar vererek ilerleyelim' dediyse KARARI SEN VER (değişiklik gerekli/gerekmez + gerekçe + kanıt); soruyla geri atma.\n"
    "- Raporda olmayanı uydurma; gözlenemeyen noktayı o maddede `[K: ❓ Belirsiz]` ile işaretle, 'gözlenemedi' de ve geç — "
    "yanıtı 'hâlâ eksik' bölümüne çevirme.\n"
    "- Yeni gözlem turu önerisi EN SONDA en fazla 1-2 satır (hangi ekran, ne denenecek); yanıtın ana gövdesi istenen çıktıdır.\n"
    "- ÖRNEK ANALİZ = TASK ANALİZİ ŞABLONU (ekran başına `### <Ekran — rota>` altında, Task Analizi'ndeki bölüm adlarıyla; "
    "o ekran için içeriksiz bölüm ATLANIR, kısa ama kanıtlı): `## 1. Amaç ve Hedefler` · `## 2. İş Gereksinimleri` "
    "(BR-n, ister) · `## 3. Teknik Gereksinimler` (gözlenen mevcut durum + değişiklik, `[K:]`) · `## 5. API Tasarımı` "
    "(uç/alan/validasyon — Swagger/Network kanıtı) · `## 6. İş Mantığı` · `## 7. Frontend İş Kırılımı` · `## 9. Hata Yönetimi` "
    "· `## 11. Kabul Kriterleri` (ekran × alan, 2-4 madde) · açık soru varsa `### Q-T-00n:` bloğu · sonda "
    "`**Katman kararı:** BE iş VAR/YOK · FE iş VAR/YOK — gerekçe`. Bu sohbet içi ön izlemedir; resmi FE+BE analiz "
    "'Ekran Task'ları Üret' ile Task Analizi'nde üretilir — analiste bunu hatırlat (tek satır)."
)

_PLAN_KC = 1_800   # önceki agent yanıtından taşınan plan (SON kısmı — öneri genelde sonda)


def _gozlem_hedefi(oturum: dict, metin: str) -> str:
    """🌐 turunun gözlem hedefi = analistin mesajı + agent'ın BİR ÖNCEKİ turda önerdiği somut plan.
    Bulgu 2026-11-05: agent 'Edit Sport aç → Odds Multiplier'a 1,111111 yaz' diye plan önerdi, analist bunu 🌐 ile
    onayladı ('tara ve karar vererek ilerleyelim') ama gözlemciye YALNIZ analist mesajı gidiyordu → plan hiç
    uygulanmadı, 40 tur menü listelemeye gitti, hiçbir modal açılmadı. Önceki agent yanıtı yoksa yalnız mesaj."""
    m = (metin or "").strip()
    mesajlar = oturum.get("mesajlar") or []
    onceki = ""
    for x in reversed(mesajlar[:-1] if mesajlar and mesajlar[-1].get("metin") == m and mesajlar[-1].get("rol") == "analist"
                      else mesajlar):
        if x.get("rol") == "agent":
            onceki = (x.get("metin") or "").strip()
            break
    if not onceki:
        return m
    if len(onceki) > _PLAN_KC:
        onceki = "…" + onceki[-_PLAN_KC:]
    return (m + "\n\n### Önceki turda agent'ın önerdiği gözlem planı (analist bu mesajla 🌐 gözlem istedi → plandaki "
            "somut adımları — ekran/rota, açılacak modal, yazılacak değer — ÖNCE uygula)\n" + onceki)


def _sohbet_gozlem_tur() -> int:
    """Sohbet gözlem turu tavanı: menü taraması + modal açma tek turda sığsın diye genel LIVE_APP_MAX_TUR'dan (40) yüksek."""
    try:
        return max(10, int(os.getenv("SOHBET_GOZLEM_MAX_TUR", "70")))
    except (TypeError, ValueError):
        return 70


def _sohbet_gozlem_devam() -> int:
    try:
        return max(0, int(os.getenv("SOHBET_GOZLEM_TUR_DEVAM", "1")))
    except (TypeError, ValueError):
        return 1


# ─── Sohbet turu ─────────────────────────────────────────────────────────────

def sohbet_mesaj(metin: str, gozlem: bool = False, ekler: list[str] | None = None) -> dict:
    """Analistin mesajını ekler, RAG'li yanıt üretir, ekler ve oturumu döndürür.
    gozlem=False: canlı gözlem YAPILMAZ (hızlı sohbet). gozlem=True ('🌐 Gözlemle'): miras canlı
    uygulamada mesaja göre GERÇEK gözlem yapılır (dakikalar sürer — arka plan iş).
    ekler: `ek_kaydet` ile kaydedilmiş ekran görüntüsü adları — yalnız SON analist mesajının ekleri modele görsel
    olarak gider (API: image bloğu · CLI: `Read` ile açılan mutlak yol); eski mesajların ekleri ad olarak kalır
    (agent'ın o turdaki yanıtı görüntüyü zaten metne çevirmiştir)."""
    metin = (metin or "").strip()
    ekler = _ekleri_dogrula(ekler)
    if not metin and not ekler:
        raise ValueError("Boş mesaj gönderilemez.")
    if not metin:
        metin = "(ekran görüntüsü eklendi — incele ve yorumla)"
    oturum = oturum_oku()
    oturum["mesajlar"].append({"rol": "analist", "metin": metin, "ts": time.time(), **({"gozlem": True} if gozlem else {}),
                               **({"ekler": ekler} if ekler else {})})
    if not oturum.get("baslik"):
        oturum["baslik"] = metin[:60] + ("…" if len(metin) > 60 else "")
    _oturum_yaz(oturum)   # gözlem turu uzun sürer → analist mesajı hemen görünsün (yeniden bağlanma)

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
    bff_blok = _bff_raporlari_blogu()
    if bff_blok:
        mesajlar.append({"role": "user", "content": [{"type": "text", "text": bff_blok}]})
        mesajlar.append({"role": "assistant", "content": [{"type": "text", "text": "BFF sözleşme raporlarını gerçek veri olarak aldım."}]})
    cevaplanan = _cevaplanan_sorular_metni()
    if cevaplanan:
        mesajlar.append({"role": "user", "content": [{"type": "text", "text":
            "### CEVAPLANAN SORULAR (analistin Sorular defterindeki kesin cevapları — tekrar sorma)\n" + cevaplanan}]})
        mesajlar.append({"role": "assistant", "content": [{"type": "text", "text": "Cevapları kesin bilgi olarak aldım."}]})
    okunur_dosyalar: list[str] = []
    son_idx = len(oturum["mesajlar"]) - 1
    for i, m in enumerate(oturum["mesajlar"]):
        rol = "user" if m.get("rol") == "analist" else "assistant"
        icerik: list[dict] = [{"type": "text", "text": m.get("metin", "")}]
        m_ekler = m.get("ekler") or []
        if m_ekler and i == son_idx:
            bloklar, yollar = _ek_icerik(m_ekler, gorsel_olarak=not _base.USE_CLAUDE_CLI)
            icerik += bloklar
            okunur_dosyalar += yollar
        elif m_ekler:
            icerik.append({"type": "text", "text": "(bu mesaja ekran görüntüsü eklenmişti: " + ", ".join(m_ekler) + ")"})
        mesajlar.append({"role": rol, "content": icerik})

    hedef = _gozlem_hedefi(oturum, metin) if gozlem else metin
    canli = _canli_tabanli_baglam(hedef) if gozlem else None
    gozlem_raporu = None
    if gozlem and canli:
        # Kota: gözlem, tam bağlamlı sohbet çağrısının İÇİNDE değil, küçük promptlu AYRI fazda (skills/gozlem.py) yapılır;
        # sohbet yanıtı TARAYICISIZ üretilir ve rapora dayanır (eskiden her araç turu RAG+BFF+konuşma bağlamını yeniden okuyordu).
        from . import gozlem as _gz
        gozlem_raporu = _gz.rapor_al(canli, "surec", gorev_ozet=hedef, yeniden=True,
                                     max_turns=_sohbet_gozlem_tur(), tur_devam=_sohbet_gozlem_devam())
        if gozlem_raporu.get("ok") and gozlem_raporu.get("md"):
            _gozlem_kaydet(gozlem_raporu, metin)
            mesajlar.append({"role": "user", "content": [{"type": "text", "text": _gz.rapor_blogu(gozlem_raporu)},
                {"type": "text", "text": _GOZLEM_TURU_TALIMAT}]})
        else:
            mesajlar.append({"role": "user", "content": [{"type": "text", "text": _gz.gozlem_yok_blogu(gozlem_raporu.get("neden", ""))},
                {"type": "text", "text": "(Analist canlı gözlem istedi ama gözlem yapılamadı — nedenini kısaca belirt, referanslara dayanarak yanıtla.)"}]})
    elif gozlem:
        mesajlar.append({"role": "user", "content": [{"type": "text", "text":
            "(Analist canlı gözlem istedi ama canlı uygulama URL'i tanımlı değil — bunu belirt, Bağlam Filtresi'ne yönlendir.)"}]})

    sistem = _SOHBET_SISTEM + _domain_kurallari_oku()
    # Gözlem ayrı fazda yapıldı → bu çağrı tarayıcı aracı kullanmaz (taze rapor metni zaten prompt'u/önbellek anahtarını değiştirir).
    yanit = _api_cagri(sistem, mesajlar, max_tokens=MAX_TOKENS_COMBINED, thinking=False, onbellek=not (gozlem and canli),
                       **({"okunur_dosyalar": okunur_dosyalar} if okunur_dosyalar else {}))
    yanit = (yanit or "").strip()
    oturum = oturum_oku()   # gözlem sürerken oturum değişmiş olabilir → taze oku
    _ga = (gozlem_raporu or {}).get("anahtar") if (gozlem_raporu or {}).get("ok") else None
    oturum["mesajlar"].append({"rol": "agent", "metin": yanit, "ts": time.time(), **({"gozlem": True} if gozlem else {}),
                               **({"gozlem_anahtar": _ga} if _ga else {})})
    _oturum_yaz(oturum)
    return oturum


# ─── Giriş testi (canlı uygulama erişimi EN BAŞTA doğrulanır) ────────────────

def giris_testi() -> dict:
    """Miras canlı uygulamaya kayıtlı test hesabıyla giriş dener; sonucu oturuma yazar + sohbete mesaj ekler.
    Çekirdek `canli_giris.test_et('surec')` (Task Analizi'nin analiz-öncesi giriş kapısıyla ORTAK; sonuç imzalı
    önbelleğe yazılır → Süreç/Teknik analizleri de aynı doğrulamayı kullanır). Dönen: {ok, neden, ekran, menu}."""
    from .canli_giris import test_et as _giris_test_et
    sonuc = _giris_test_et("surec")
    if not sonuc.get("url") and not sonuc.get("ok"):
        sonuc["neden"] = "Canlı uygulama URL'i tanımlı değil (Süreç/Teknik ekranı → Bağlam Filtresi)."
    sonuc["ts"] = time.time()
    oturum = oturum_oku()
    oturum["giris"] = sonuc
    if sonuc["ok"]:
        metin = (f"🔐 **Giriş testi başarılı.** Açılan ekran: `{sonuc['ekran'] or '—'}`."
                 + (f" Üst menü: {', '.join(sonuc['menu'][:12])}." if sonuc["menu"] else "")
                 + " Canlı gözlem ve ekran bazlı analiz için erişim hazır.")
    else:
        metin = (f"🔐 **Giriş testi BAŞARISIZ** — {sonuc['neden'] or 'neden belirlenemedi'}. Canlı gözlem bu hesapla "
                 "yapılamaz: Süreç/Teknik Analiz → Bağlam Filtresi'nde uygulama giriş bilgilerini düzeltip tekrar test edin.")
    oturum["mesajlar"].append({"rol": "agent", "metin": metin, "ts": time.time(), "sistem": True})
    _oturum_yaz(oturum)
    return sonuc


# ─── BFF Keşfi (sohbetten) — agent miras canlı uygulamada ekranda kendisi CRUD yapar ────────

def bff_kesfet(ekran_tarif: str) -> dict:
    """Miras `live_app` ANA adresi + verilen ekran tarifiyle `bff_kesif.kesfet(ekran_bazli=True)`; sonuç
    oturum['bff'] listesine + sohbete sistem mesajı. Anahtar Task Analizi ile ORTAKTIR (aynı ekran = aynı rapor)."""
    from .bff_kesif import kesfet
    ekran_tarif = (ekran_tarif or "").strip()
    if not ekran_tarif:
        raise ValueError("Hangi ekranda keşif yapılacağını yazın (ör. 'Sport Basic Data › Sports').")
    urls = live_app_urls()
    r = kesfet(urls[0] if urls else "", ekran_tarif, ekran_bazli=True)
    oturum = oturum_oku()
    liste = [x for x in (oturum.get("bff") or []) if x.get("anahtar") != r.get("anahtar")]
    liste.append({"anahtar": r.get("anahtar"), "ekran": ekran_tarif, "ts": r.get("ts") or time.time(), "ok": bool(r.get("ok"))})
    oturum["bff"] = liste[-20:]
    if r.get("ok"):
        md = r.get("md") or ""
        bulunan = [m for m in ("POST", "PUT", "PATCH", "DELETE") if f"`{m} " in md or f"{m} /" in md]
        metin = (f"🔌 **BFF keşfi tamamlandı — {ekran_tarif}.** Agent ekranda kendisi oluştur/güncelle/sil yaptı; "
                 f"yakalanan yazma servisleri: {', '.join(bulunan) or '—'}. Rapor bu sohbete ve üretime otomatik girer "
                 f"(7 gün). AI-TEST kayıtları ekranda bırakıldı — raporda listeli.")
    else:
        metin = f"🔌 **BFF keşfi tamamlanamadı — {ekran_tarif}:** {r.get('neden') or 'neden belirlenemedi'}."
    oturum["mesajlar"].append({"rol": "agent", "metin": metin, "ts": time.time(), "sistem": True, "bff_anahtar": r.get("anahtar")})
    _oturum_yaz(oturum)
    return r


def _bff_raporlari_blogu() -> str:
    """Bu oturumda çıkarılmış, hâlâ TAZE (7 gün) BFF raporları → sohbet turu + üretim girdisi bloğu. Yoksa ''."""
    try:
        from .bff_kesif import rapor_oku, taze_mi, rapor_blogu
        parcalar = []
        for x in (oturum_oku().get("bff") or []):
            r = rapor_oku_anahtar(x.get("anahtar"), rapor_oku)
            if taze_mi(r):
                parcalar.append(rapor_blogu(r))
        return "\n\n".join(parcalar)[:60_000]
    except Exception:
        return ""


def rapor_oku_anahtar(anahtar: str | None, _rapor_oku=None) -> dict | None:
    """Anahtarla rapor (bff_kesif depo düzeni: <anahtar>.md + .json)."""
    from .bff_kesif import BFF_DIR
    import json as _json
    if not anahtar:
        return None
    md_yol, meta_yol = BFF_DIR / f"{anahtar}.md", BFF_DIR / f"{anahtar}.json"
    if not md_yol.exists():
        return None
    try:
        meta = _json.loads(meta_yol.read_text(encoding="utf-8")) if meta_yol.exists() else {}
    except Exception:
        meta = {}
    ts = float(meta.get("ts") or md_yol.stat().st_mtime)
    md = md_yol.read_text(encoding="utf-8")
    # `ok` OKUMA ANINDA yeniden değerlendirilir — bff_kesif.rapor_oku ile AYNI kapı (denetim 2026-11-02 B#7: sohbet yolu
    # meta'daki bayat ok=True'yu alıp giriş duvarında kalmış/kanıtsız raporu 'GERÇEK gözlem' diye üretime veriyordu).
    from .bff_kesif import rapor_tam_mi, _giris_hatasi_var
    ok = bool(meta.get("ok", True)) and rapor_tam_mi(md) and not _giris_hatasi_var(md)
    return {"anahtar": anahtar, "md": md, "ts": ts,
            "yas_gun": round((time.time() - ts) / 86400, 1), "hedef_url": meta.get("hedef_url", ""),
            "ekran": meta.get("ekran", ""), "yol": str(md_yol), "ok": ok}


# ─── Ekran bazlı iş: ekran envanteri + ekran başına FE/BE görev girdisi ──────

_EKRAN_SISTEM = (
    "Kıdemli iş analistisin. Verilen sohbetten (analist ↔ agent) ve REFERANS BAĞLAM'daki BRD/Confluence "
    "parçalarından, yapılacak işin EKRAN ENVANTERİNİ çıkar. Yalnız sohbette KAPSAMA ALINAN ekranlar (analistin "
    "son kararları esas: ör. 'önce Sport Basic Data altındaki ekranlar'). Her ekran için o ekranda yapılacak "
    "değişikliği 1-3 cümleyle, BRD atfıyla yaz. Uydurma ekran ekleme; BRD/sohbette geçmeyen ekranı alma.\n\n"
    "Çıktı YALNIZ şu blok:\n<ekranlar>[{\"ad\": \"Ekran adı\", \"menu\": \"Ana menü › alt menü\", "
    "\"ister\": \"bu ekranda yapılacak değişiklik\", \"brd_ref\": \"BRD §/sayfa veya Confluence sayfası\", "
    "\"not\": \"sekme/özel durum (varsa)\"}]</ekranlar>"
)


def ekran_listesi_cikar() -> list[dict]:
    """Sohbet + BRD referanslarından ekran envanteri (1 AI çağrısı). oturum['ekranlar']'a yazar."""
    oturum = oturum_oku()
    konusma = _konusma_metni(oturum)
    if not konusma.strip():
        raise ValueError("Önce sohbette kapsamı netleştirin.")
    ref_bloklari: list = []
    try:
        ref_dosyalar = referans_dosyalari_hazirla()
        if ref_dosyalar:
            ref_bloklari, _ = _ref_bloklari_olustur(ref_dosyalar, sorgu_metni=_konusma_metni(oturum, son_n=8))
    except Exception as e:
        print(f"  ⚠ Ekran envanteri RAG atlandı: {e}")
    icerik = list(ref_bloklari)
    _sg = son_gozlem_raporu(oturum)
    if _sg:
        icerik.append({"type": "text", "text": "### CANLI GÖZLEM RAPORU (bu oturumda agent'ın gerçekten gezdiği ekranlar — "
                                                "rotaları/menüsü buradan; burada bulunan ve kapsamla ilgili ekranlar da ADAYDIR)\n"
                                                + (_sg.get("md") or "")[:9000]})
    icerik += [
        {"type": "text", "text": "### SOHBET\n\n" + konusma[-12000:]},
        {"type": "text", "text": _cevaplanan_sorular_metni() and ("### CEVAPLANAN SORULAR\n" + _cevaplanan_sorular_metni()) or "(cevaplanmış soru yok)"},
        {"type": "text", "text": "Ekran envanterini çıkar."},
    ]
    sistem = _EKRAN_SISTEM + _domain_kurallari_oku()
    mesajlar = [{"role": "user", "content": icerik}]

    def _coz(yanit):
        ham = _xml_ayir(_metin_sikistir(yanit or ""), "ekranlar")
        try:
            return json.loads(ham)
        except Exception:
            a, b = ham.find("["), ham.rfind("]")
            try:
                return json.loads(ham[a:b + 1]) if a != -1 and b > a else []
            except Exception:
                return []

    liste = _coz(_api_cagri(sistem, mesajlar, max_tokens=MAX_TOKENS_KISA, thinking=False, katman="yardimci"))
    if not liste:
        # Bozuk/boş yanıt 7 gün önbellekte kalmasın → BİR KEZ önbelleksiz tekrar
        liste = _coz(_api_cagri(sistem, mesajlar, max_tokens=MAX_TOKENS_KISA, thinking=False, katman="yardimci", onbellek=False))
    ekranlar = []
    for e in liste if isinstance(liste, list) else []:
        if not isinstance(e, dict) or not str(e.get("ad") or "").strip():
            continue
        ekranlar.append({"ad": str(e.get("ad")).strip(), "menu": str(e.get("menu") or "").strip(),
                         "ister": str(e.get("ister") or "").strip(), "brd_ref": str(e.get("brd_ref") or "").strip(),
                         "not": str(e.get("not") or "").strip()})
        if len(ekranlar) >= 40:
            break
    oturum = oturum_oku()
    oturum["ekranlar"] = ekranlar
    oturum["mesajlar"].append({"rol": "agent", "sistem": True, "ts": time.time(), "metin":
        (f"🧩 **Ekran envanteri çıkarıldı: {len(ekranlar)} ekran.** Aşağıdan seçip her ekran için FE+BE analiz "
         "üretebilirsiniz (Task Analizi ekranında görünür; oradan 'Yeni Task Aç' ile Jira'ya ekran başına FE/BE task açılır).")
        if ekranlar else "🧩 Ekran envanteri çıkarılamadı — sohbette hangi ekranların kapsamda olduğunu netleştirin."})
    _oturum_yaz(oturum)
    return ekranlar


def ekran_gorevleri(secilen: list[int]) -> list[dict]:
    """Seçilen ekranlar için Task Analizi iş adımları (mode fe-be-ayir, sentetik görev EKRAN-n + canlı hedef).
    Jira'da task YOK — analiz üretilir, Jira'ya açma Task Analizi 'Yeni Task Aç' ile yapılır."""
    oturum = oturum_oku()
    ekranlar = oturum.get("ekranlar") or []
    if not ekranlar:
        raise ValueError("Önce ekran envanteri çıkarın.")
    konusma = _konusma_metni(oturum)[-6000:]
    cevaplar = _cevaplanan_sorular_metni()
    _sg = son_gozlem_raporu(oturum)
    gozlem_anahtar = (_sg or {}).get("anahtar") or ""
    adimlar = []
    for i in secilen:
        if not (0 <= int(i) < len(ekranlar)):
            continue
        e = ekranlar[int(i)]
        key = f"EKRAN-{int(i) + 1}"
        menu = (e.get("menu") or "").strip()
        # Model 'menu' alanına ekran adını çoğu zaman zaten ekler ("Sport Basic Data › Sports") → tekrar ekleme
        baslik = menu if (menu and menu.lower().endswith(e["ad"].lower())) else (f"{menu} › {e['ad']}" if menu else e["ad"])
        aciklama = (f"## Ekran: {e['ad']}\nMenü: {e.get('menu') or '—'}\n\n## İster (bu ekranda yapılacak)\n{e.get('ister') or '—'}\n"
                    + (f"\nBRD referansı: {e['brd_ref']}\n" if e.get("brd_ref") else "")
                    + (f"Not: {e['not']}\n" if e.get("not") else "")
                    + (f"\n## Analistin kesin cevapları\n{cevaplar}\n" if cevaplar else "")
                    + f"\n## Sohbetten kararlar (bağlam)\n{konusma}")
        # Sohbetin TAZE 🌐 gözlem raporu adıma taşınır → motor yeniden gözlemez (owner 2026-11-06: sohbetten Task Analizi
        # formatında üretim). Rapor yoksa/eskiyse motor canli_hedef ile kendisi gözler (eski davranış).
        adimlar.append({"key": key, "mode": "fe-be-ayir", "gozlem_anahtar": gozlem_anahtar, "sohbet_kaynak": True,
                        "gorev": {"key": key, "summary": baslik, "description": aciklama, "issuetype": "Görev",
                                  "status": "", "ekran": e["ad"]},
                        "canli_hedef": f"{baslik} ekranı — DataTable kolonları, mevcut butonlar/aksiyonlar, tetiklenen "
                                       f"servis çağrıları; istenen değişiklik: {e.get('ister') or ''}"})
    if not adimlar:
        raise ValueError("Geçerli ekran seçilmedi.")
    return adimlar


# ─── Kilometre taşı üretim — MEVCUT motorları sohbet girdisiyle çalıştır ──────

def _uretim_girdisi(oturum: dict) -> list:
    konusma = _konusma_metni(oturum)
    if not konusma.strip():
        raise ValueError("Önce sohbette isterini yaz (analiz üretilecek içerik yok).")
    cevaplar = _cevaplanan_sorular_metni()
    bff_blok = _bff_raporlari_blogu()
    girdi = [{"type": "text", "text": bff_blok}] if bff_blok else []
    return girdi + [{"type": "text", "text": (
        "### İnteraktif Analiz Oturumu (analist ↔ agent sohbeti)\n\n"
        "Aşağıda bir isteri/süreç üzerine yapılan sohbet var. Bu sohbette OLGUNLAŞAN "
        "gereksinimi analiz konusu kabul et; analistin son kararlarını/cevaplarını esas al, "
        "açık kalan noktaları 'Açık Sorular'a taşı.\n\n" + konusma
        + (("\n\n### Analistin kesin cevapları (Sorular defteri — açık soru olarak TEKRAR SORMA)\n" + cevaplar) if cevaplar else ""))}]


_HEDEF_MESAJ_KC = 400


def _sohbet_hedef_tarifi(oturum: dict) -> str:
    """Üretim gözlemi için hedef tarifi SOHBETTEN: analistin mesajları (son 6, her biri kırpılmış). Süreç ekranının
    Bağlam Filtresi'ndeki gözlem kapsamı (başka doküman için girilmiş olabilir) KULLANILMAZ."""
    mesajlar = [m.get("metin", "").strip() for m in (oturum.get("mesajlar") or []) if m.get("rol") == "analist"]
    mesajlar = [m[:_HEDEF_MESAJ_KC] for m in mesajlar if m][-6:]
    if not mesajlar:
        return ""
    return ("Sohbette analistin tarif ettiği ekranlar/alanlar (hedef bunlardır; menüden bul):\n"
            + "\n".join(f"- {m}" for m in mesajlar))


def _uretim_canli_baglami(oturum: dict) -> str | None:
    """Sohbetten üretimde canlı görev bloğu: miras ANA adres + sohbet hedefi (kapsam_birlestir=False).
    URL yoksa None → motor gözlemsiz üretir (doküman akışındaki davranışla aynı)."""
    return _canli_tabanli_baglam(_sohbet_hedef_tarifi(oturum))


def surec_uret(oturum: dict | None = None) -> Path:
    """Sohbetten süreç analizi üretir (özel prompt YOK, canlı gözlem VAR — miras ANA adres, hedef SOHBETTEN).
    surec-analizi.md yazar → Çıktılar/Revizyon/Teknik devreye girer."""
    oturum = oturum or oturum_oku()
    from .surec_analizi import surec_analizi_yap
    return surec_analizi_yap(icerik_override=_uretim_girdisi(oturum),
                             dosya_adi_override="interaktif-analiz", ozel_atla=True,
                             canli_baglam_override=_uretim_canli_baglami(oturum))


def teknik_uret(oturum: dict | None = None) -> tuple[Path, Path]:
    """surec-analizi.md → teknik-analiz.md (özel prompt YOK, canlı gözlem VAR — hedef SOHBETTEN)."""
    oturum = oturum or oturum_oku()
    from .teknik_analiz import teknik_analiz_yap
    return teknik_analiz_yap(ozel_atla=True, canli_baglam_override=_uretim_canli_baglami(oturum))


def _oturuma_ait_mi(dosya: str, oturum: dict | None = None) -> bool:
    """Çıktı BU sohbet oturumunda mı üretildi? Dosya mtime'ı oturumun İLK mesajından (yoksa oluşturulma
    zamanından) önceyse → önceki doküman/sohbet akışının BAYAT çıktısıdır; sohbetin ürünü gibi gösterilmez.
    (Hata: 12 Eylül'de üretilmiş süreç analizi 15 Ekim'deki yeni sohbetin sonucu sanıldı.)"""
    yol = OUTPUT_DIR / dosya
    if not yol.exists():
        return False
    o = oturum if oturum is not None else oturum_oku()
    mesajlar = o.get("mesajlar") or []
    esik = min((m.get("ts") or 0) for m in mesajlar) if mesajlar else (o.get("created") or 0)
    try:
        return yol.stat().st_mtime >= float(esik or 0)
    except (OSError, TypeError, ValueError):
        return False


def surec_var_mi(oturum: dict | None = None) -> bool:
    return _oturuma_ait_mi("surec-analizi.md", oturum)


def teknik_var_mi(oturum: dict | None = None) -> bool:
    return _oturuma_ait_mi("teknik-analiz.md", oturum)
