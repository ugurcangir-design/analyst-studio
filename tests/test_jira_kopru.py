"""Jira Köprüsü — offline durum-makinesi testi (0 token, ağ YOK).

Tüm Jira/AI çağrıları monkeypatch'lenir; yalnız komut→taslak→onay akışının
mantığı doğrulanır. Çalıştır:  venv/bin/python tests/test_jira_kopru.py
"""

import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
os.environ.setdefault("AUTH_ENABLED", "false")

import skills.jira_kopru as jk  # noqa: E402

basari = 0


def kontrol(ad: str, kosul: bool) -> None:
    global basari
    if not kosul:
        raise SystemExit(f"FAIL {ad}")
    basari += 1
    print(f"  ✓ {ad}")


# ── Sahte Jira/AI dünyası ────────────────────────────────────────────────────
yazilan_aciklama: dict = {}      # key → güncellenen açıklama md
acilan_tasklar: list = []        # oluşturulan issue'lar
kurulan_linkler: list = []       # (inward, outward, tip)

analiz_cagrilari: list = []      # gorev_analiz_et'e geçen ekran_baglami'yı yakala
analiz_girdi: list = []          # (cevaplar, onceki_sorular, description) — cevap/özyineleme testi

jk.gorev_getir = lambda key: {"key": key, "summary": f"{key} başlık", "description": "açıklama"}


def _sahte_analiz(gorev, cevaplar="", onceki_sorular="", **kw):
    analiz_cagrilari.append(kw.get("ekran_baglami", "YOK"))
    analiz_girdi.append({"cevaplar": cevaplar, "onceki": onceki_sorular, "desc": gorev.get("description", "")})
    acik = "Açık soru tespit edilmedi." if cevaplar else "Q-T-001: belirsizlik var?"
    return {"markdown": f"# Analiz {gorev['key']}\n\n(cevap: {cevaplar or 'yok'})", "acik_sorular": acik}


jk.gorev_analiz_et = _sahte_analiz
jk.gorev_analiz_duzelt = lambda gorev, mevcut, talimat: f"{mevcut}\n\n[DÜZELTİLDİ: {talimat}]"
cevap_girdi: list = []   # Kota Faz 2: hedefli cevap uygulama MOCK (gerçek motor çağrılmaz)


def _sahte_cevap_uygula(gorev, mevcut, cevaplar, onceki_sorular=""):
    cevap_girdi.append({"key": gorev.get("key"), "mevcut": mevcut, "cevaplar": cevaplar, "onceki": onceki_sorular})
    return {"markdown": f"{mevcut}\n\n[CEVAP İŞLENDİ: {cevaplar}]", "acik_sorular": "Açık soru tespit edilmedi.", "hedefli": True}


jk.gorev_cevap_uygula = _sahte_cevap_uygula
jk.gorev_jiraya_yaz = lambda key, md: yazilan_aciklama.__setitem__(key, md) or True
jk._iliskili_task_onerileri = lambda md, gorev: [
    {"summary": "BE endpoint ekle", "description": "market servisi", "katman": "BE"},
    {"summary": "FE filtre kaldır", "description": "gereksiz filtre", "katman": "FE"},
]
jk._proje_bilgi = lambda proje, cloud_id: {"task_id": "10001", "story_id": "10002"}
jk._cloud_id = lambda: "cloud-x"
_ORJ_CGB = jk._canli_gorev_baglam   # sonda gerçek fonksiyon test edilir
jk._canli_gorev_baglam = lambda gorev: (None, None)   # live-app config'e bağlı kalma (offline) — (blok, kapsam)
jk._kopru_config = lambda: {}                 # test: json config yok → .env yedeği (deterministik)


def _sahte_issue_olustur(summary, adf, type_id, proje, cloud_id, parent_key=None):
    key = f"{proje}-{900 + len(acilan_tasklar)}"
    acilan_tasklar.append({"key": key, "summary": summary, "proje": proje})
    return key


jk._issue_olustur = _sahte_issue_olustur
jk.jira_issue_link = lambda inw, outw, tip="Relates": kurulan_linkler.append((inw, outw, tip)) or True

PFX = "/analyst_agent"


# ── analiz → task GÖVDESİNE yazar (yoruma değil), orijinal korunur (#1) ───────
durum: dict = {}
r = jk._komut_uygula("analiz", "", "MBSTRADE-1", PFX, durum)
kontrol("analiz sonucu task GÖVDESİNE yazıldı", "MBSTRADE-1" in yazilan_aciklama)
govde = yazilan_aciklama["MBSTRADE-1"]
kontrol("gövdede orijinal talep + analiz bölümü", "Orijinal Talep" in govde and "Teknik Analiz" in govde)
kontrol("analiz yorumu = gövdeye yazıldı bilgisi", "açıklamasına yazıldı" in r.lower() or "açıklamaya yaz" in r.lower())
kontrol("analiz çıktısı önbelleğe alındı", durum.get("son_analiz", {}).get("MBSTRADE-1", {}).get("md"))
kontrol("bridge analizi KENDİ KENDİNE YETERLİ (ekran_baglami=False)", analiz_cagrilari[-1] is False)

# ── güncelle → SON analizi gövdeye YENİDEN yazar (taslak DEĞİL, 0-token) ──────
yazilan_aciklama.clear()
oncesi = len(analiz_cagrilari)
r = jk._komut_uygula("guncelle", "", "MBSTRADE-1", PFX, durum)
kontrol("güncelle gövdeye yazdı, taslak oluşturmadı",
        "MBSTRADE-1" in yazilan_aciklama and "MBSTRADE-1" not in durum.get("taslaklar", {}))
kontrol("güncelle taze önbelleği kullandı (yeniden analiz yok)", len(analiz_cagrilari) == oncesi)

# ── onayla → bekleyen ilişkili taslak yok ────────────────────────────────────
r = jk._komut_uygula("onayla", "", "MBSTRADE-1", PFX, durum)
kontrol("bekleyen taslak yokken onayla no-op", "bekleyen taslak yok" in r)

# ── ilişkili-aç → taslak (henüz task AÇILMADI) ───────────────────────────────
r = jk._komut_uygula("iliskili-ac", "", "MBSTRADE-2", PFX, durum)
kontrol("ilişkili-aç taslağı 2 öneri", len(durum["taslaklar"]["MBSTRADE-2"]["oneriler"]) == 2)
kontrol("ilişkili-aç taslakken task AÇILMADI", not acilan_tasklar)

# ── onayla → task'lar açılır + Relates bağlanır ──────────────────────────────
r = jk._komut_uygula("onayla", "", "MBSTRADE-2", PFX, durum)
kontrol("2 ilişkili task açıldı", len(acilan_tasklar) == 2)
kontrol("açılan task'lar doğru projede", all(t["proje"] == "MBSTRADE" for t in acilan_tasklar))
kontrol("her yeni task kaynağa Relates bağlandı",
        len(kurulan_linkler) == 2 and all(o == "MBSTRADE-2" and t == "Relates" for _, o, t in kurulan_linkler))
kontrol("ilişkili-aç onayından sonra taslak temizlendi", "MBSTRADE-2" not in durum.get("taslaklar", {}))

# ── iptal → ilişkili taslağı düşürür ─────────────────────────────────────────
jk._komut_uygula("iliskili-ac", "", "MBSTRADE-3", PFX, durum)
r = jk._komut_uygula("iptal", "", "MBSTRADE-3", PFX, durum)
kontrol("iptal bekleyen taslağı düşürdü", "MBSTRADE-3" not in durum.get("taslaklar", {}) and "iptal edildi" in r.lower())

# ── #3: task'tan RAG anahtar kelimeleri çıkar ────────────────────────────────
kws = jk._task_keywords({"summary": "Rapor ekranı arama filtresi alanı",
                         "description": "kullanıcı rapor ekranında arama yapabilmeli için modül"})
kontrol("task keyword'leri çıkarıldı (durak kelimeler elenmiş)",
        "arama" in kws and "rapor" in kws and "için" not in kws)

# ── #1: orijinal talep ayıklama (tekrar analizde korunur) ────────────────────
onceki = "## 📌 Orijinal Talep\n\nyeni bir alan isteniyor\n\n---\n\n## 🤖 Teknik Analiz (Analyst Agent)\n\neski analiz"
kontrol("orijinal talep tekrar analizde korunur", jk._orijinal_talep_ayikla(onceki) == "yeni bir alan isteniyor")

# ── özyineleme önlemi: analiz GİRDİSİ orijinal talep (gövde değil) ────────────
og = jk._orijinal_gorev({"key": "MBSTRADE-9", "summary": "s",
                         "description": "## 📌 Orijinal Talep\n\nORJ metin\n\n---\n\n## 🤖 Teknik Analiz (Analyst Agent)\n\nESKİ ANALİZ"})
kontrol("gövdeye analiz yazılmışsa girdi = orijinal talep", og["description"] == "ORJ metin")
kontrol("gövdeden analiz bölümü ayıklanır (düzelt için)",
        jk._analiz_bolumu_ayikla("## 📌 Orijinal Talep\n\nX\n\n---\n\n## 🤖 Teknik Analiz (Analyst Agent)\n\nANALİZ GÖVDESİ") == "ANALİZ GÖVDESİ")
# Jira ADF geri-okuma: '##' başlıkları DÜŞER → marker '#'siz de eşleşmeli (gerçek hata)
_adf = "📌 Orijinal Talep\n\nyeni alan isteniyor\n\n🤖 Teknik Analiz (Analyst Agent)\n\neski analiz"
kontrol("ADF-okuma (#'siz) orijinal ayıklama", jk._orijinal_talep_ayikla(_adf) == "yeni alan isteniyor")
kontrol("ADF-okuma (#'siz) analiz bölümü ayıklama", jk._analiz_bolumu_ayikla(_adf) == "eski analiz")
# çift '📌 Orijinal Talep' kaz-boynu → tek orijinale iner (self-heal)
kontrol("çift orijinal başlık self-heal",
        jk._orijinal_talep_ayikla("📌 Orijinal Talep\n\n📌 Orijinal Talep\n\nORJ\n\n🤖 Teknik Analiz\n\nA") == "ORJ")

# ── cevap → analizi cevaplarla YENİDEN üretir, soruları yakınsar, gövdeye yazar ──
durum2: dict = {}
jk._komut_uygula("analiz", "", "MBSTRADE-5", PFX, durum2)
kontrol("analiz açık soruyu önbelleğe aldı", "Q-T-001" in durum2["son_analiz"]["MBSTRADE-5"].get("acik", ""))
kontrol("analiz girdisi orijinal (gövde değil)", analiz_girdi[-1]["desc"] == "açıklama")
yazilan_aciklama.clear()
_analiz_sayisi = len(analiz_girdi)
r = jk._komut_uygula("cevap", "Q-T-001: mevcut alan korunur", "MBSTRADE-5", PFX, durum2)
kontrol("cevap gövdeyi güncelledi", "MBSTRADE-5" in yazilan_aciklama and "CEVAP İŞLENDİ" in yazilan_aciklama["MBSTRADE-5"])
kontrol("cevap HEDEFLİ işlendi (mevcut analiz + cevaplar; tam üretim YOK — Kota Faz 2)",
        cevap_girdi and cevap_girdi[-1]["cevaplar"].startswith("Q-T-001") and len(analiz_girdi) == _analiz_sayisi)
kontrol("cevap önceki soruları yakınsamaya geçirdi", "Q-T-001" in cevap_girdi[-1]["onceki"])
kontrol("cevap → açık soru kalmadı bilgisi", "açık soru kalmadı" in r.lower())
# Hedefli kapalı (CEVAP_HEDEFLI=false) → eski yol: cevaplarla TAM yeniden üretim
jk.cevap_hedefli_acik = lambda: False
jk._komut_uygula("cevap", "Q-T-001: ikinci cevap", "MBSTRADE-5", PFX, durum2)
kontrol("hedefli kapalıyken cevap tam üretime düşer (önceki sorular yakınsamaya geçer)",
        len(analiz_girdi) == _analiz_sayisi + 1 and "Q-T-001" in (analiz_girdi[-1]["onceki"] or "") or "ikinci" in analiz_girdi[-1].get("cevaplar", ""))
jk.cevap_hedefli_acik = lambda: True

# ── düzelt → yalnız ilgili kısmı düzeltir, gövdeye yazar ──────────────────────
yazilan_aciklama.clear()
r = jk._komut_uygula("duzelt", "§7'ye debounce süresi ekle", "MBSTRADE-5", PFX, durum2)
kontrol("düzelt ilgili kısmı düzeltip gövdeye yazdı",
        "MBSTRADE-5" in yazilan_aciklama and "DÜZELTİLDİ" in yazilan_aciklama["MBSTRADE-5"])

# ── döngü koruması: kendi 🤖 yanıtımız komut sayılmaz ────────────────────────
kontrol("kendi yanıtı komut değil", jk._komut_coz(jk.ROBOT_IMZA + " ✅ güncellendi", PFX) is None)

# ── GÜVENLİK: yazar allowlist fail-closed + accountId-only ────────────────────
kontrol("allowlist boş → fail-closed (yetki yok)", jk._yazar_izinli({"hesap": "a", "yazar": "Ali"}, []) is False)
kontrol("allowlist accountId ile eşleşir", jk._yazar_izinli({"hesap": "a"}, ["a"]) is True)
kontrol("displayName yetkiye SOKULMAZ (spoof koruması)", jk._yazar_izinli({"yazar": "Ali", "hesap": "x"}, ["Ali"]) is False)

# ── İSTEK 1: yetkisiz/entegrasyonsuz yazara TAM SESSİZLİK (_tek_tur_ic akışı) ──
_yorum_cagrilari: list = []
jk.jira_yorum_ekle = lambda key, md: _yorum_cagrilari.append((key, md)) or True
jk.atlassian_post = lambda path, body=None, cloud_id=None: {"issues": [{"key": "MBS-1"}]}
jk._issue_yorumlari = lambda key, cloud_id: [
    {"id": "c1", "metin": f"{PFX} analiz", "yazar": "Yabancı", "hesap": "intruder"},
    {"id": "c2", "metin": f"{PFX} analiz", "yazar": "Ben", "hesap": "me"},
]
_durum_bellek: dict = {}
jk._durum_yukle = lambda: dict(_durum_bellek)
jk._durum_yaz = lambda d: (_durum_bellek.clear() or _durum_bellek.update(d))
os.environ["JIRA_KOPRU_PROJELER"] = "MBS"
os.environ["JIRA_KOPRU_YAZAR_ALLOWLIST"] = "me"

_ozet = jk._tek_tur_ic()
kontrol("yetkisiz yazara ⛔/red yanıtı YAZILMAZ (tam sessizlik)",
        all("⛔" not in md and "yetkisinde değil" not in md for _, md in _yorum_cagrilari))
kontrol("yalnız yetkili yazar için Jira yorumu (1 yanıt)", len(_yorum_cagrilari) == 1)
kontrol("yetkili yazarın komutu işlendi", len(_ozet["islenen"]) == 1 and _ozet["islenen"][0]["komut"] == "analiz")
kontrol("yetkisiz komut 'atlanan'a sayıldı", _ozet["atlanan"] >= 1)
kontrol("yetkisiz yorum işlenen-id'ye eklenmedi", "c1" not in _durum_bellek.get("islenen", {}))

# ── Self-scope (madde 2): elle allowlist yoksa agent kendi myself.accountId'ine kilitlenir ──
jk._owner_id_cache["id"] = None
jk.atlassian_get = lambda path, cloud_id=None: {"accountId": "owner-123"} if "myself" in path else {}
kontrol("elle allowlist varsa o kullanılır (override)", jk._etkin_allowlist({"yazar_allowlist": ["a", "b"]}, "cx") == ["a", "b"])
jk._owner_id_cache["id"] = None
kontrol("allowlist boş → self-scope (owner accountId)", jk._etkin_allowlist({"yazar_allowlist": []}, "cx") == ["owner-123"])
kontrol("owner accountId önbelleğe alındı", jk._owner_id_cache["id"] == "owner-123")


def _myself_patlar(path, cloud_id=None):
    raise RuntimeError("401 yetki")


jk._owner_id_cache["id"] = None
jk.atlassian_get = _myself_patlar
kontrol("myself alınamazsa fail-closed ([])", jk._etkin_allowlist({"yazar_allowlist": []}, "cx") == [])

# ── Durum göstergesi (madde 6): saglik_guncelle → son_durum.saglik ────────────
jk.saglik_guncelle(True)
kontrol("başarılı tur → bagli True, son_hata None", jk.saglik()["bagli"] is True and jk.saglik()["son_hata"] is None)
jk.saglik_guncelle(False, "401 Unauthorized")
kontrol("hata → bagli False + son_hata dolu", jk.saglik()["bagli"] is False and "401" in (jk.saglik()["son_hata"] or ""))
kontrol("son_durum 'saglik' alanı içerir", "saglik" in jk.son_durum())

# ── #1: config json-birincil (analist .env yazmadan güncelleme ile) ───────────
jk._kopru_config = lambda: {"aktif": True, "projeler": ["mbs", "abc"], "yazar_allowlist": []}
for k in ("JIRA_KOPRU", "JIRA_KOPRU_PROJELER", "JIRA_KOPRU_YAZAR_ALLOWLIST"):
    os.environ.pop(k, None)
a = jk.ayarlar()
kontrol("json config → aktif True (.env olmadan)", a["aktif"] is True)
kontrol("json projeler → upper + liste", a["projeler"] == ["MBS", "ABC"])
kontrol("json boş allowlist → [] (self-scope)", a["yazar_allowlist"] == [])
jk._kopru_config = lambda: {"aktif": False}
os.environ["JIRA_KOPRU"] = "true"
kontrol("json aktif:false → .env'e DÜŞMEZ (False korunur)", jk.ayarlar()["aktif"] is False)
jk._kopru_config = lambda: {}     # json yok → .env yedeği
os.environ["JIRA_KOPRU"] = "true"
os.environ["JIRA_KOPRU_PROJELER"] = "xyz"
a = jk.ayarlar()
kontrol(".env yedek (json yok) → aktif True + projeler", a["aktif"] is True and a["projeler"] == ["XYZ"])

# ── Kanıt etiketi (`[K: …]`) temizliği — Jira'ya sadece gerçek task analizi gider ──
from skills.base import kanit_etiketlerini_temizle as _kt  # noqa: E402

kontrol("kanıt: inline [K:] silinir",
        _kt("Ekrana gider [K: Canlı UI:/route].") == "Ekrana gider.")
kontrol("kanıt: network path etiketi silinir",
        _kt("Endpoint [K: Network:GET /bff/x/y-z] çağrılır.") == "Endpoint çağrılır.")
kontrol("kanıt: çoklu etiket + çift boşluk temizlenir",
        _kt("A [K: a] B [K: b] C.") == "A B C.")
kontrol("kanıt: markdown linki KORUNUR (K: ile başlamaz)",
        _kt("Bak [rapor](http://x) burada.") == "Bak [rapor](http://x) burada.")
kontrol("kanıt: etiketsiz metin değişmez",
        _kt("Normal cümle, dokunma.") == "Normal cümle, dokunma.")
kontrol("kanıt: boş/None güvenli", _kt("") == "" and _kt(None) is None)
# Wiring: her iki Jira-yazım sınırı da temizleyiciyi çağırır (kaynak-düzey güvence)
import inspect  # noqa: E402
import skills.jira_gorevleri as _jg  # noqa: E402
kontrol("kanıt: gorev_jiraya_yaz (gövde) temizleyiciyi çağırır",
        "jira_icin_temizle" in inspect.getsource(_jg.gorev_jiraya_yaz))   # tek kapı: etiket+özet+gözlem+alıntı+numaralama
# (jk.jira_yorum_ekle testte mock'landı → gerçek kaynağı modül dosyasından oku)
_jk_kaynak = inspect.getsource(jk)
kontrol("kanıt: jira_yorum_ekle (yorum) temizleyiciyi çağırır",
        "def jira_yorum_ekle" in _jk_kaynak
        and "kanit_etiketlerini_temizle(markdown)" in _jk_kaynak)

# ── Ek regresyonlar: Türkçe İ/I, ADF okuma, yetki hatası, köprü kapsamı ──
kws = jk._task_keywords({"summary": "İNDİRİM KUPONLARI IŞIKLAR", "description": "indirim kuponu filtresi"})
kontrol("_task_keywords: 'İNDİRİM'→'indirim' (İ→i), 'IŞIKLAR'→'ışıklar' (I→ı) — dotless/dotted karışmaz",
        "indirim" in kws and "ışıklar" in kws and not any("i̇" in k for k in kws))
adf = {"type": "doc", "content": [
    {"type": "heading", "attrs": {"level": 3}, "content": [{"type": "text", "text": "Başlık"}]},
    {"type": "table", "content": [
        {"type": "tableRow", "content": [{"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "A"}]}]},
                                         {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "B"}]}]}]},
        {"type": "tableRow", "content": [{"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "1"}]}]},
                                         {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "2"}]}]}]}]}]}
txt = _jg._adf_to_text(adf)
kontrol("_adf_to_text: başlık '### ' ile, tablo hücreleri '|' ile (köprü düzelt/cevap biçimi bozmaz)",
        "### Başlık" in txt and "| A | B |" in txt and "| 1 | 2 |" in txt)
kontrol("orijinal_talep_ayikla '### 🤖 Teknik Analiz' işaretini (ADF geri okuma) tanır",
        _jg.orijinal_talep_ayikla("## 📌 Orijinal Talep\nisteri\n\n---\n\n### 🤖 Teknik Analiz (Analyst Agent)\nanaliz") == "isteri")


class _Yanit:
    def __init__(self, kod):
        self.status_code = kod


def _hata_ver(kod):
    e = Exception(f"HTTP {kod}")
    e.response = _Yanit(kod)
    return e


_eski_post, _eski_tek = _jg.atlassian_post, _jg._tek_issue_ham
_jg.atlassian_post = lambda *a, **k: (_ for _ in ()).throw(_hata_ver(403))
try:
    _jg._tek_issue_ham("MBS-1", "cid")
    kontrol("_tek_issue_ham 403 yükseltir", False)
except RuntimeError as e:
    kontrol("_tek_issue_ham: 401/403 'bulunamadı' diye YUTULMAZ → RuntimeError (yetki/ağ)", "yetki" in str(e))
_jg.atlassian_post = lambda *a, **k: (_ for _ in ()).throw(_hata_ver(404))
kontrol("_tek_issue_ham: 404 → None (gerçek bulunamadı)", _jg._tek_issue_ham("MBS-1", "cid") is None)
_jg.atlassian_post = lambda *a, **k: (_ for _ in ()).throw(_hata_ver(403))
try:
    _jg.alt_gorevleri_cek("MBS-1")
    kontrol("alt_gorevleri_cek hata", False)
except RuntimeError as e:
    kontrol("alt_gorevleri_cek: tüm sorgular 403'le düşerse '0 alt görev' değil RuntimeError", "okunamadı" in str(e))
_jg.atlassian_post = lambda *a, **k: (_ for _ in ()).throw(_hata_ver(400))
_jg._tek_issue_ham = lambda key, cid: None
kontrol("alt_gorevleri_cek: 400 (JQL alanı yok) sessizce geçilir → boş liste", _jg.alt_gorevleri_cek("MBS-1") == [])
_jg.atlassian_post, _jg._tek_issue_ham = _eski_post, _eski_tek
# köprü: canlı bağlam hangi URL alanından geldiyse o kapsam gorev_analiz_et'e geçer
_eski_cgb, _eski_lcf, _eski_cub = jk._canli_gorev_baglam, jk.load_context_filter, jk.canli_uygulama_baglami_hazirla
_gercek_cgb = _ORJ_CGB
jk.canli_uygulama_baglami_hazirla = lambda **kw: "CANLI " + kw.get("base_url_override", "")
jk.load_context_filter = lambda: {"live_app_gorev": {"target_url": "https://g.local/app/x"}, "live_app": {"target_url": "https://s.local/app"}}
a = _gercek_cgb({"summary": "s", "description": "d"})
jk.load_context_filter = lambda: {"live_app": {"target_url": "https://s.local/app"}}
b = _gercek_cgb({"summary": "s", "description": "d"})
jk.load_context_filter = lambda: {}
c = _gercek_cgb({"summary": "s", "description": "d"})
kontrol("_canli_gorev_baglam: live_app_gorev → ('…','gorev'); yalnız live_app → ('…','surec'); yok → (None, None)",
        a == ("CANLI https://g.local", "gorev") and b == ("CANLI https://s.local", "surec") and c == (None, None))
jk._canli_gorev_baglam, jk.load_context_filter, jk.canli_uygulama_baglami_hazirla = _eski_cgb, _eski_lcf, _eski_cub
kap: list = []
_eski_ae = jk.gorev_analiz_et
jk.gorev_analiz_et = lambda gorev, **kw: (kap.append(kw.get("canli_kapsam")) or {"markdown": "m", "acik_sorular": ""})
jk._canli_gorev_baglam = lambda gorev: ("CANLI", "gorev")
jk._bridge_uret({"key": "MBS-9", "summary": "s", "description": "d"}, "")
jk._canli_gorev_baglam, jk.gorev_analiz_et = _eski_cgb, _eski_ae
kontrol("köprü canli_kapsam'ı URL kaynağına göre geçirir", kap == ["gorev"])

print(f"\nJIRA KÖPRÜSÜ TESTLERİ GEÇTİ ({basari} kontrol)")
