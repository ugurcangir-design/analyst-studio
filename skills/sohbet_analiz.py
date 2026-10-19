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

from urllib.parse import urlparse

from .base import (
    _api_cagri, _xml_ayir, _metin_sikistir, OUTPUT_DIR,
    referans_dosyalari_hazirla, _ref_bloklari_olustur,
    _domain_kurallari_oku, canli_uygulama_baglami_hazirla, live_app_urls,
    MAX_TOKENS_COMBINED, MAX_TOKENS_KISA,
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
    "- Türkçe yaz; teknik terimler İngilizce kalabilir.\n\n"
    "ÇALIŞMA BİÇİMİ (analist adım adım ilerler — bunlara UY):\n"
    "- SIRAYLA SOR: aynı anda EN FAZLA BİR (zorunluysa iki) netleştirici soru sor; analist cevaplayınca "
    "bir sonrakine geç. Soru listesi dökme.\n"
    "- BRD YÜKLENMEZ, REFERANSTA HAZIRDIR: 'BRD'deki X isteri' dendiğinde REFERANS BAĞLAM'daki BRD "
    "parçalarını kullan ve atıf ver; bulamıyorsan 'BRD'de bu ekran/ister için metin bulamadım' de, uydurma.\n"
    "- CANLI GÖZLEM: analist mesajı '🌐 Gözlemle' ile gönderdiyse sana CANLI UYGULAMA GÖREVİ verilir — "
    "uygulamayı GERÇEKTEN gez, gördüğünü (ekran, kolon, buton var/yok, servis) sohbet tonunda yaz. Normal "
    "turda uygulamayı açma. Giriş reddedilirse tekrar deneme; 'Girişi Test Et' ile hesabın düzeltilmesini iste.\n"
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
    return canli_uygulama_baglami_hazirla(base_url_override=f"{p.scheme}://{p.netloc}",
                                          hedef_tarif=(hedef_tarif or "").strip() or "Ana ekran")


def _cevaplanan_sorular_metni() -> str:
    """Analistin Sorular defterinde (bu oturumda) cevapladığı/varsayım girdiği sorular → sohbet ve üretim
    bağlamına KESİN bilgi olarak girer (tekrar sorulmaz). Best-effort; hata → ''."""
    try:
        from .sorular import sorular_yukle
        o = oturum_oku()
        mesajlar = o.get("mesajlar") or []
        esik = min((m.get("ts") or 0) for m in mesajlar) if mesajlar else (o.get("created") or 0)
        satirlar = []
        for q in (sorular_yukle().get("sorular") or []):
            if q.get("durum") not in ("cevaplandi", "varsayim"):
                continue
            ts = q.get("guncellendi_at") or q.get("olusturuldu_at") or ""
            try:
                from datetime import datetime
                if datetime.fromisoformat(ts).timestamp() < float(esik or 0) - 1:
                    continue   # önceki oturumun cevabı
            except Exception:
                pass
            cevap = q.get("cevap") or q.get("varsayim") or ""
            if cevap:
                satirlar.append(f"- {q.get('id')} ({q.get('kaynak_dosya', '')}): {q.get('soru') or q.get('baslik', '')} → "
                                f"{'VARSAYIM: ' if q.get('durum') == 'varsayim' else ''}{cevap}")
        return "\n".join(satirlar)
    except Exception:
        return ""


# ─── Sohbet turu ─────────────────────────────────────────────────────────────

def sohbet_mesaj(metin: str, gozlem: bool = False) -> dict:
    """Analistin mesajını ekler, RAG'li yanıt üretir, ekler ve oturumu döndürür.
    gozlem=False: canlı gözlem YAPILMAZ (hızlı sohbet). gozlem=True ('🌐 Gözlemle'): miras canlı
    uygulamada mesaja göre GERÇEK gözlem yapılır (dakikalar sürer — arka plan iş)."""
    metin = (metin or "").strip()
    if not metin:
        raise ValueError("Boş mesaj gönderilemez.")
    oturum = oturum_oku()
    oturum["mesajlar"].append({"rol": "analist", "metin": metin, "ts": time.time(), **({"gozlem": True} if gozlem else {})})
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
    for m in oturum["mesajlar"]:
        rol = "user" if m.get("rol") == "analist" else "assistant"
        mesajlar.append({"role": rol, "content": [{"type": "text", "text": m.get("metin", "")}]})

    canli = _canli_tabanli_baglam(metin) if gozlem else None
    if gozlem and canli:
        mesajlar.append({"role": "user", "content": [{"type": "text", "text": canli},
            {"type": "text", "text": (
                "### 🌐 CANLI GÖZLEM TURU\nAnalistin SON mesajı için yukarıdaki canlı uygulama görevini GERÇEKTEN uygula "
                "(gir, ilgili ekrana git, gör), sonra gözlemi KISA sohbet yanıtına çevir: ekran/kolon/buton/servis ne "
                "gördüysen onu yaz; göremediğini yazma. Rapor biçimi değil, sohbet tonu; sonunda bir sonraki adımı öner.")}]})
    elif gozlem:
        mesajlar.append({"role": "user", "content": [{"type": "text", "text":
            "(Analist canlı gözlem istedi ama canlı uygulama URL'i tanımlı değil — bunu belirt, Bağlam Filtresi'ne yönlendir.)"}]})

    sistem = _SOHBET_SISTEM + _domain_kurallari_oku()
    yanit = _api_cagri(sistem, mesajlar, max_tokens=MAX_TOKENS_COMBINED, thinking=False,
                       onbellek=not (gozlem and canli), canli_uygulama_kapsami=("surec" if (gozlem and canli) else None))
    yanit = (yanit or "").strip()
    oturum = oturum_oku()   # gözlem sürerken oturum değişmiş olabilir → taze oku
    oturum["mesajlar"].append({"rol": "agent", "metin": yanit, "ts": time.time(), **({"gozlem": True} if gozlem else {})})
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
    return {"anahtar": anahtar, "md": md_yol.read_text(encoding="utf-8"), "ts": ts,
            "yas_gun": round((time.time() - ts) / 86400, 1), "hedef_url": meta.get("hedef_url", ""),
            "ekran": meta.get("ekran", ""), "yol": str(md_yol), "ok": bool(meta.get("ok", True))}


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
    icerik = list(ref_bloklari) + [
        {"type": "text", "text": "### SOHBET\n\n" + konusma[-12000:]},
        {"type": "text", "text": _cevaplanan_sorular_metni() and ("### CEVAPLANAN SORULAR\n" + _cevaplanan_sorular_metni()) or "(cevaplanmış soru yok)"},
        {"type": "text", "text": "Ekran envanterini çıkar."},
    ]
    yanit = _api_cagri(_EKRAN_SISTEM + _domain_kurallari_oku(), [{"role": "user", "content": icerik}],
                       max_tokens=MAX_TOKENS_KISA, thinking=False, katman="yardimci")
    ham = _xml_ayir(_metin_sikistir(yanit or ""), "ekranlar")
    try:
        liste = json.loads(ham)
    except Exception:
        a, b = ham.find("["), ham.rfind("]")
        liste = json.loads(ham[a:b + 1]) if a != -1 and b > a else []
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
        adimlar.append({"key": key, "mode": "fe-be-ayir",
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
