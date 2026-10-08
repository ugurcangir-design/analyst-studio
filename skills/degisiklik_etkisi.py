"""Değişiklik Etkisi & Veri Yaşam Döngüsü — deterministik (0 token).

Girdide (doküman / süreç analizi / Jira görevi) veri değiştiren bir işlem sinyali
(zorunluluk kaldırma, silme, alan kaldırma, pasife alma, güncelleme, tip/isim değişimi)
varsa analize "DEĞİŞİKLİK ETKİSİ" talimatı + **Olası Tüketiciler** bloğu eklenir:
değişen öğenin adı Swagger / Confluence / Jira referanslarında aranır → o veriyi kullanan
endpoint/sayfa/task'lar kaynaklarıyla listelenir. Amaç analizi büyütmek DEĞİL: etki ayrı bölüm
olarak değil, mevcut Etki Analizi + ilgili akış adımına işlenir (uçtan uca akış kapansın).
Etkilenip etkilenmediği belirlenemeyen nokta → açık soru (riskliyse `Zorunlu: Evet`).

AI çağrısı YOK; base.py IMPORT ETMEZ (ucuz, döngüsel import yok). Hata durumunda boş döner —
analiz akışını ASLA kırmaz.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REF_DIR = Path(__file__).parent.parent / "reference"

# ── Sinyal tespiti ────────────────────────────────────────────────────────────
# Desenler Türkçe-katlanmış küçük harf metne uygulanır (_kucuk): İ→i, I→ı.
_SINYAL_TANIM: list[tuple[str, str, list[str]]] = [
    ("zorunluluk", "Zorunluluk kaldırma", [
        r"zorunlu(?:lu[gğ]u|luk|lu[gğ]unun)?\s+(?:\S+\s+){0,2}?(?:kald[ıi]r|kalk|olmaktan\s+[çc][ıi]k)",
        r"zorunlu\s+(?:olmayacak|olmamal[ıi]|de[gğ]il)",
        r"opsiyonel\w*\s+(?:\S+\s+){0,1}?(?:ol|yap|[çc]ek|hale|getir|d[öo]n)",
        r"iste[gğ]e\s+ba[gğ]l[ıi]\s+(?:ol|hale|yap)",
        r"\boptional\b",
    ]),
    ("silme", "Silme", [
        r"\bsil(?:in|me|ece|ebil|insin|inir|indi|inmes|inece|inebil|mek)\w*",
        r"\b(?:hard|soft)[- ]?delete\b", r"\bdelete\b",
    ]),
    ("kaldirma", "Alan/öğe kaldırma", [
        r"(?:alan|kolon|s[üu]tun|buton|ekran|men[üu]|sekme|se[çc]enek|filtre)\w*\s+(?:\S+\s+){0,2}?kald[ıi]r[ıi]l\w*",
        r"kald[ıi]r[ıi]lacak", r"kald[ıi]r[ıi]ls[ıi]n",
    ]),
    ("pasif", "Pasife alma", [
        r"pasif(?:e)?\s+(?:al|[çc]ek|hale|yap)\w*", r"\bdeaktif\w*", r"devre\s*d[ıi][şs][ıi]\s+b[ıi]rak\w*",
    ]),
    ("guncelleme", "Güncelleme", [
        r"\bg[üu]ncelle(?:n|me|yece|nece|nebil|ns)\w*", r"\bupdate\b",
        r"de[gğ]i[şs]tiril\w*", r"\bd[üu]zenlen\w*",
    ]),
    ("tip_isim", "Tip/isim/format değişikliği", [
        r"(?:tipi|t[üu]r[üu]|format[ıi]|uzunlu[gğ]u|ad[ıi]|ismi)\s+(?:\S+\s+){0,2}?de[gğ]i[şs]\w*",
        r"\brename\b",
    ]),
]
_SINYAL_DERLENMIS = [(tip, ad, [re.compile(d) for d in desenler]) for tip, ad, desenler in _SINYAL_TANIM]

# Her tip için analizde mutlaka cevaplanacak kontrol soruları (prompt'a girer)
_KONTROL: dict[str, str] = {
    "zorunluluk": ("Boş değeri kullanan yerler (rapor, export, entegrasyon, hesaplama, liste/filtre) nasıl "
                   "davranacak · boş değer ekranda nasıl gösterilecek · DB NOT NULL kısıtı/default · "
                   "mevcut dolu kayıtlar ne olur · validasyon FE+BE'de birlikte mi kalkıyor · eski istemci sürümleri"),
    "silme": ("Fiziksel mi mantıksal (soft delete) mı · bağlı kayıtlar ne olur (cascade/engelle/yetim) · "
              "geçmiş işlem ve raporlarda nasıl görünür · işlemdeki (yarım) akışlar · cache/event (Kafka) etkisi · "
              "geri alınabilir mi · silme yetkisi ve audit/log"),
    "kaldirma": ("Kaldırılan alan/öğenin verisi ne olur (saklanır mı, silinir mi) · onu okuyan diğer ekran/rapor/"
                 "entegrasyon · API sözleşmesinden de kalkıyor mu (geri uyumluluk) · mevcut kayıtlardaki değer"),
    "pasif": ("Pasif kayıt hangi ekranlarda görünmeye devam eder (liste/filtre/seçim kutusu) · pasif kayda bağlı "
              "aktif işlemler · tekrar aktifleştirme · raporlarda durumu"),
    "guncelleme": ("Değişiklik geçmiş kayıtlara mı yalnız yenilere mi uygulanır · kopyalanmış/önbellekteki değerler "
                   "güncellenir mi · eşzamanlı güncelleme (iki kullanıcı) · audit/değişiklik geçmişi · "
                   "güncellenen değeri gösteren diğer ekranlar"),
    "tip_isim": ("Mevcut verinin dönüşümü (migration) · API/rapor/export sözleşmesindeki karşılığı · "
                 "eski adla çalışan istemci/entegrasyonlar"),
}

_MAX_ORNEK = 6          # sinyal başına kanıt cümlesi
_MAX_ADAY = 8           # aranacak değişen-öğe adayı
_MAX_TUKETICI = 25      # bloktaki toplam tüketici satırı
_MAX_DOSYA_KRK = 400_000


def _kucuk(metin: str) -> str:
    """Türkçe-duyarlı küçük harf (İ→i, I→ı) — regex IGNORECASE Türkçe i'yi güvenilir eşlemez."""
    return (metin or "").replace("İ", "i").replace("I", "ı").lower()


_ASCII = str.maketrans("çğıöşüâîû", "cgiosuaiu")


def _norm(s: str) -> str:
    """Eşleştirme anahtarı: küçük harf + ASCII katlama + yalnız harf/rakam (taxNumber == 'Tax Number')."""
    return re.sub(r"[^a-z0-9]", "", _kucuk(s).translate(_ASCII))


def _cumleler(metin: str) -> list[str]:
    return [c.strip() for c in re.split(r"(?<=[.!?])\s+|\n+", metin or "") if c.strip()]


def sinyaller(metin: str) -> list[dict]:
    """Girdideki veri-değişikliği sinyalleri: [{tip, ad, ornekler:[cümle…]}]. Yoksa []."""
    sonuc: list[dict] = []
    if not metin:
        return sonuc
    cumleler = _cumleler(metin)
    kucukler = [_kucuk(c) for c in cumleler]
    for tip, ad, desenler in _SINYAL_DERLENMIS:
        ornekler: list[str] = []
        for c, k in zip(cumleler, kucukler):
            if any(d.search(k) for d in desenler):
                ornekler.append(c[:200])
                if len(ornekler) >= _MAX_ORNEK:
                    break
        if ornekler:
            sonuc.append({"tip": tip, "ad": ad, "ornekler": ornekler})
    return sonuc


# ── Değişen öğe adayları ─────────────────────────────────────────────────────
_TIRNAK = re.compile(r"[\"“”'‘’«»`]([^\"“”'‘’«»`\n]{2,40})[\"“”'‘’«»`]")
_ALAN_ONCESI = re.compile(
    r"((?:[\wçğıöşüÇĞİÖŞÜ]+\s+){0,2}[\wçğıöşüÇĞİÖŞÜ]+)\s+"
    r"(?:alan[ıi]?\w*|kolon\w*|s[üu]tun\w*|field\b|bilgisi\w*|de[gğ]eri\w*|butonu?\w*|parametre\w*)",
)
_KIMLIK = re.compile(r"\b[a-z]+(?:[A-Z][a-z0-9]+)+\b|\b[a-z]+(?:_[a-z0-9]+)+\b")
_DURAK = {"bu", "şu", "o", "ilgili", "mevcut", "yeni", "ve", "ile", "için", "olan", "tüm", "her", "bir",
          "the", "an", "a", "zorunlu", "opsiyonel", "ekrandaki", "ekranındaki", "formdaki", "listedeki",
          "aşağıdaki", "yukarıdaki", "söz", "konusu", "de", "da", "ki", "ise", "gibi", "kayıt", "kaydın"}


def degisen_adaylari(metin: str, sinyal_listesi: list[dict] | None = None) -> list[str]:
    """Sinyal cümlelerinden değişen alan/varlık adaylarını çıkarır (tırnaklı ad, 'X alanı', camelCase)."""
    sinyal_listesi = sinyal_listesi if sinyal_listesi is not None else sinyaller(metin)
    cumleler = [c for s in sinyal_listesi for c in s["ornekler"]]
    adaylar: list[str] = []
    gorulen: set[str] = set()

    def ekle(a: str):
        a = a.strip(" .,;:-–()[]")
        kelimeler = a.split()
        while kelimeler and _kucuk(kelimeler[0]) in _DURAK:
            kelimeler = kelimeler[1:]
        a = " ".join(kelimeler)
        n = _norm(a)
        if len(n) < 3 or n in gorulen or _kucuk(a) in _DURAK:
            return
        gorulen.add(n)
        adaylar.append(a)

    for c in cumleler:
        for m in _TIRNAK.finditer(c):
            ekle(m.group(1))
        for m in _KIMLIK.finditer(c):
            ekle(m.group(0))
        for m in _ALAN_ONCESI.finditer(c):
            ekle(m.group(1))
        if len(adaylar) >= _MAX_ADAY:
            break
    return adaylar[:_MAX_ADAY]


# ── Tüketici taraması ────────────────────────────────────────────────────────
_swagger_onbellek: dict[str, tuple[float, list[dict]]] = {}


def _swagger_operasyonlar(yol: Path) -> list[dict]:
    """Swagger dosyasını [{op:'GET /x', alanlar:{norm: (ad, yer)}, metin:'özet+açıklama'}] listesine indirger."""
    try:
        mt = yol.stat().st_mtime
        if str(yol) in _swagger_onbellek and _swagger_onbellek[str(yol)][0] == mt:
            return _swagger_onbellek[str(yol)][1]
        spec = json.loads(yol.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []
    semalar = ((spec.get("components") or {}).get("schemas") or {}) or (spec.get("definitions") or {})

    def topla(dugum, yer: str, hedef: dict, derinlik: int = 0, gorulen: frozenset = frozenset()):
        if derinlik > 6 or dugum is None:
            return
        if isinstance(dugum, dict):
            ref = dugum.get("$ref")
            if isinstance(ref, str):
                ad = ref.rsplit("/", 1)[-1]
                if ad not in gorulen and ad in semalar:
                    topla(semalar[ad], yer, hedef, derinlik + 1, gorulen | {ad})
            for pad, pdeger in (dugum.get("properties") or {}).items():
                hedef.setdefault(_norm(pad), (pad, yer))
                topla(pdeger, yer, hedef, derinlik + 1, gorulen)
            for k in ("items", "allOf", "oneOf", "anyOf", "schema", "content", "additionalProperties"):
                if k in dugum:
                    topla(dugum[k], yer, hedef, derinlik + 1, gorulen)
            if "application/json" in dugum:
                topla(dugum["application/json"], yer, hedef, derinlik + 1, gorulen)
        elif isinstance(dugum, list):
            for x in dugum:
                topla(x, yer, hedef, derinlik + 1, gorulen)

    ops: list[dict] = []
    for p, metodlar in (spec.get("paths") or {}).items():
        if not isinstance(metodlar, dict):
            continue
        for metod, op in metodlar.items():
            if metod.lower() not in ("get", "post", "put", "patch", "delete") or not isinstance(op, dict):
                continue
            alanlar: dict = {}
            for prm in op.get("parameters") or []:
                if isinstance(prm, dict) and prm.get("name"):
                    alanlar.setdefault(_norm(prm["name"]), (prm["name"], "parametre"))
            topla(op.get("requestBody"), "istek", alanlar)
            for kod, yanit in (op.get("responses") or {}).items():
                topla(yanit, "yanıt", alanlar)
            ops.append({"op": f"{metod.upper()} {p}", "alanlar": alanlar,
                        "metin": _kucuk(f"{op.get('summary', '')} {op.get('description', '')}")})
    _swagger_onbellek[str(yol)] = (mt, ops)
    return ops


def _swagger_tara(adaylar: list[str], ref_dir: Path) -> list[dict]:
    bulgular: list[dict] = []
    for yol in sorted((ref_dir / "services").glob("*.json")):
        ops = _swagger_operasyonlar(yol)
        for a in adaylar:
            n, k = _norm(a), _kucuk(a)
            for op in ops:
                if n in op["alanlar"]:
                    pad, yer = op["alanlar"][n]
                    bulgular.append({"aday": a, "kaynak": f"Swagger:{yol.name}", "nerede": op["op"],
                                     "eslesme": f"{yer} alanı `{pad}`", "guc": 2})
                elif len(k) >= 5 and k in op["metin"]:
                    bulgular.append({"aday": a, "kaynak": f"Swagger:{yol.name}", "nerede": op["op"],
                                     "eslesme": "özet/açıklamada geçiyor", "guc": 1})
    return bulgular


def _confluence_tara(adaylar: list[str], ref_dir: Path) -> list[dict]:
    dosyalar = sorted((ref_dir / "confluence").rglob("*.md"))
    if not dosyalar:
        return []
    metinler: list[tuple[Path, str]] = []
    for yol in dosyalar:
        try:
            metinler.append((yol, yol.read_text(encoding="utf-8", errors="replace")[:_MAX_DOSYA_KRK]))
        except Exception:
            continue
    bulgular: list[dict] = []
    for a in adaylar:
        k = _kucuk(a)
        if len(k) < 4:
            continue
        isabet: list[tuple[int, Path, str]] = []
        for yol, metin in metinler:
            km = _kucuk(metin)
            sayi = km.count(k)
            if sayi:
                i = km.find(k)
                bas = metin.rfind("\n", 0, i) + 1
                son = metin.find("\n", i)
                satir = metin[bas: son if son != -1 else len(metin)].strip()[:140]
                isabet.append((sayi, yol, satir))
        # Çok genel aday (sayfaların %40'ından fazlası) → gürültü, atla
        if not isabet or len(isabet) > max(5, len(metinler) * 0.4):
            continue
        for sayi, yol, satir in sorted(isabet, key=lambda x: -x[0])[:5]:
            bulgular.append({"aday": a, "kaynak": f"Confluence:{yol.stem}", "nerede": satir or "(sayfa)",
                             "eslesme": f"{sayi} geçiş", "guc": 1})
    return bulgular


def _jira_tara(adaylar: list[str], ref_dir: Path) -> list[dict]:
    issues: list[dict] = []
    for yol in sorted((ref_dir / "jira").glob("*.json")):
        if yol.name.startswith("_"):
            continue
        try:
            d = json.loads(yol.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        liste = d.get("issues") if isinstance(d, dict) else d
        for it in liste or []:
            if isinstance(it, dict) and it.get("key"):
                issues.append(it)
    bulgular: list[dict] = []
    for a in adaylar:
        k = _kucuk(a)
        if len(k) < 4:
            continue
        isabet = [it for it in issues
                  if k in _kucuk(f"{it.get('summary', '')} {it.get('description', '') or ''}")]
        if not isabet or len(isabet) > max(5, len(issues) * 0.2):
            continue
        for it in isabet[:4]:
            bulgular.append({"aday": a, "kaynak": f"Jira:{it['key']}",
                             "nerede": str(it.get("summary", ""))[:120],
                             "eslesme": str(it.get("status", "") or ""), "guc": 1})
    return bulgular


def tuketici_tara(adaylar: list[str], ref_dir: Path | None = None) -> list[dict]:
    """Değişen öğe adaylarını referanslarda arar → olası tüketiciler (güçlü eşleşme önce)."""
    ref_dir = ref_dir or REF_DIR
    if not adaylar:
        return []
    bulgular: list[dict] = []
    for tarayici in (_swagger_tara, _confluence_tara, _jira_tara):
        try:
            bulgular.extend(tarayici(adaylar, ref_dir))
        except Exception:
            continue
    # Tekilleştir + aday başına güçlü (alan adı birebir) eşleşmeler önce
    gorulen: set[tuple] = set()
    gruplar: dict[str, list[dict]] = {a: [] for a in adaylar}
    for b in sorted(bulgular, key=lambda x: -x["guc"]):
        anahtar = (b["aday"], b["kaynak"], b["nerede"])
        if anahtar not in gorulen:
            gorulen.add(anahtar)
            gruplar.setdefault(b["aday"], []).append(b)
    # Adaylar arasında SIRAYLA dağıt → yaygın bir aday (ör. id alanı) bütçeyi tek başına doldurmaz
    sonuc: list[dict] = []
    i = 0
    while len(sonuc) < _MAX_TUKETICI and any(i < len(g) for g in gruplar.values()):
        for g in gruplar.values():
            if i < len(g) and len(sonuc) < _MAX_TUKETICI:
                sonuc.append(g[i])
        i += 1
    return sonuc


# ── Prompt bloğu ─────────────────────────────────────────────────────────────
_HEDEF_YERLESIM = {
    "surec": ("AYRI bölüm AÇMA: mevcut **İlişkili Ekranlar / Süreçler ve Etki Analizi** bölümüne kısa bir "
              "`Veri Değişikliği Etkisi` tablosu ekle ve her etkiyi ilgili süreç adımına / alternatif akışa işle."),
    "teknik": ("Etkiyi §3 akışında ilgili adıma işle; DB karşılığını (NOT NULL kaldırma/migration, FK ON DELETE, "
               "soft-delete, mevcut veri dönüşümü) §4'te, API sözleşme etkisini (alan opsiyonel/kaldırıldı, geri "
               "uyumluluk) §5'te, cache/event etkisini §6'da yaz. Ayrı tablo yalnız birden fazla öğe değişiyorsa, kısa."),
    "gorev": ("Etkiyi `## 3. Teknik Gereksinimler` akışında ilgili adıma işle; birden fazla öğe değişiyorsa kısa bir "
              "`Veri Değişikliği Etkisi` tablosu ekle (yalnız bu görevin değiştirdiği veriler)."),
    "gorev_hata": ("HATA/BASİT İŞ modu: tablo AÇMA — `## Çözüm` altına tek madde `Etki:` ile değişen verinin "
                   "kullanıldığı yerleri ve mevcut kayıtlara etkisini KISA yaz; belirsizse açık soru."),
}
# Yalnız 'güncelleme' sinyali (BRD'lerde çok yaygın) → tablo yok, tek kısa talimat (analiz büyümesin).
_KOMPAKT_HEDEF = {"surec", "teknik", "gorev"}


def degisiklik_blogu(metin: str, hedef: str = "surec", ref_dir: Path | None = None) -> str:
    """Sinyal varsa analize eklenecek talimat + Olası Tüketiciler bloğu; yoksa ''. Hata → ''."""
    try:
        sl = sinyaller(metin)
        if not sl:
            return ""
        adaylar = degisen_adaylari(metin, sl)
        tuketiciler = tuketici_tara(adaylar, ref_dir)
    except Exception:
        return ""
    yalniz_guncelleme = all(s["tip"] == "guncelleme" for s in sl)
    tablo = hedef in _KOMPAKT_HEDEF and not yalniz_guncelleme

    satirlar = [
        "### DEĞİŞİKLİK ETKİSİ (otomatik tespit)",
        "Girdide veri değiştiren işlemler var. Bu işlemler kaynak ekranla sınırlı kalmaz; o veriyi gösteren/"
        "kullanan ekran, rapor, servis ve entegrasyonlarda da davranışı değiştirir. Uçtan uca akış bu etkiyle "
        "birlikte kapanmalı: 'X silinince/boş kalınca Y ekranında ne olur?' sorusu analizde cevapsız kalmasın. "
        "Analizi BÜYÜTME — yalnız gerçekten veri değiştiren öğeleri ele al.",
        "",
        "**Tespit edilen sinyaller:**",
    ]
    for s in sl:
        satirlar.append(f"- **{s['ad']}** — ör. «{s['ornekler'][0][:140]}»")
    if yalniz_guncelleme and hedef != "gorev_hata":
        satirlar += ["", "**Yerleşim:** tablo AÇMA. Güncellenen verinin onu gösteren diğer ekranlarda/kayıtlarda "
                     "nasıl yansıdığını ilgili süreç adımında kısaca belirt."]
    else:
        satirlar += ["", "**Yerleşim:** " + _HEDEF_YERLESIM.get(hedef, _HEDEF_YERLESIM["surec"])]
    if tablo:
        satirlar += [
            "",
            "| Değişen Öğe | Değişiklik | Kullanan Yerler (kaynaklı) | Mevcut Kayıtlar | Yeni Davranış / Bağlı Adım |",
            "|---|---|---|---|---|",
        ]
    satirlar += ["", "**Netleştirilecek noktalar (yalnız ilgili olanlar):**"]
    for s in sl:
        satirlar.append(f"- *{s['ad']}:* {_KONTROL[s['tip']]}")
    satirlar += [
        "",
        "**KURALLAR:** Kullanan yerleri yalnız kaynaklardan (Swagger/Confluence/Jira/canlı gözlem) yaz, uydurma. "
        "Etkisi kaynaktan belirlenemeyen nokta `[K: ❓ Belirsiz]` + açık soru olur ve cevapsız kalması veri kaybı/"
        "kırılma riski taşıyorsa `- Zorunlu: Evet` işaretlenir. Kabul kriteri yalnız akışın kritik dalı için.",
    ]
    if tuketiciler:
        satirlar += [
            "",
            "#### Olası Tüketiciler (deterministik kaynak taraması — değişen öğe adları referanslarda arandı)",
            "Her satırı değerlendir: etkileniyorsa akışta/tabloda ele al, etkilenmiyorsa atla (gerekçe yazmana "
            "gerek yok). Etkilenip etkilenmediği belirlenemiyorsa açık soru.",
            "| Aday Öğe | Kaynak | Nerede | Eşleşme |",
            "|---|---|---|---|",
        ]
        for t in tuketiciler:
            nerede = str(t["nerede"]).replace("|", "/")
            satirlar.append(f"| {t['aday']} | {t['kaynak']} | {nerede} | {t['eslesme']} |")
    elif adaylar:
        satirlar += ["", f"_Aday öğeler ({', '.join(adaylar)}) referanslarda bulunamadı — kullanan yerleri "
                         "canlı gözlem/kaynaklardan doğrula; belirlenemiyorsa açık soru aç._"]
    return "\n".join(satirlar)
