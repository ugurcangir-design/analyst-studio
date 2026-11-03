"""Kayıtlı Swagger'dan servis sözleşmesi enjeksiyonu (offline, 0 token; sentetik OpenAPI).

Owner 2026-10-21: BE task'ında agent mimari kararı analiste bırakmamalı — Swagger'da mevcut endpoint'i bulup
kullanmalı. servis_sozlesme.endpoint_baglami: task/gözlem metniyle alakalı MEVCUT endpoint'leri (method+path+şema)
çıkarır. Ayrıca prompt kuralları (SERVİS KARARI + açık-soru teknik-tasarım dışlaması) yerinde mi.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skills import servis_sozlesme as SS  # noqa: E402
from skills import base as B  # noqa: E402
from skills import jira_gorevleri as JG  # noqa: E402

HATA = 0


def chk(ad, kosul, ek=""):
    global HATA
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if (ek and not kosul) else ""))
    if not kosul:
        HATA += 1


# Sentetik OpenAPI (gerçek reference/services gitignore — teste bağlama)
tmp = Path(tempfile.mkdtemp())
spec = {
    "paths": {
        "/bff/nebula/id-mapping-service/external/markets/{id}": {
            "get": {"operationId": "getExternalMarketById",
                    "responses": {"200": {"content": {"*/*": {"schema": {"type": "object", "additionalProperties": {}}}}}}},
        },
        "/bff/tradoria/definition-service/markets": {
            "get": {"operationId": "getMarkets",
                    "parameters": [
                        {"name": "sportId", "in": "query", "schema": {"type": "integer"}},
                        {"name": "name", "in": "query", "schema": {"type": "string"}},
                        {"name": "marketId", "in": "query", "required": True, "schema": {"type": "integer"}},
                    ],
                    "responses": {"200": {"content": {"application/json": {"schema": {
                        "type": "array", "items": {"$ref": "#/components/schemas/Market"}}}}}}},
        },
        "/bff/odeme/payment-service/charge": {   # ALAKASIZ endpoint — task'a girmemeli
            "post": {"operationId": "charge", "responses": {"200": {}}},
        },
    },
    "components": {"schemas": {"Market": {"type": "object", "properties": {
        "id": {"type": "integer"}, "name": {"type": "string"}, "outcomes": {"type": "array"}}}}},
}
(tmp / "sky-panel-bff.json").write_text(json.dumps(spec), encoding="utf-8")
SS.SERVICES_DIR = tmp

blok = SS.endpoint_baglami("Market Definitions outcome eşleme provider gösterimi",
                           ek_metin="GET /bff/nebula/id-mapping-service/external/markets  definition-service/markets")
chk("alakalı nebula id-mapping endpoint'i yüzeye çıkar", "id-mapping-service/external/markets" in blok)
chk("alakalı definition-service/markets endpoint'i yüzeye çıkar", "definition-service/markets" in blok)
chk("ALAKASIZ ödeme servisi GİRMEZ (ister dışı)", "payment-service" not in blok, blok[:200])
chk("method+path yazılır", "GET /bff/" in blok)
chk("çözülen response şeması (Market alanları) görünür", "outcomes" in blok or "name" in blok)
chk("blok başlığı + 'KULLAN' yönergesi", "KAYITLI SERVİS SÖZLEŞMELERİ" in blok and "KULLAN" in blok)
# 1254 koşusu: blok name/marketId listelerken model 'doğrulanamadı' yazdı → başlık parametre listesini KESİN ilan eder + ad eşleme
chk("blok başlığı: Parametreler satırı KESİN + 'id'→marketId ad eşleme + proxy/api aynı uç",
    "KESİN sözleşmedir" in blok and "marketId" in blok and "AYNI uçtur" in blok)
# owner 2026-11-02: query/path parametreleri indekslenir + çıktıda gösterilir (GET-filtre sözleşmesi)
chk("parametre satırı çıktıda görünür (sportId/name/marketId)",
    "Parametreler" in blok and all(x in blok for x in ("sportId", "name", "marketId")), blok)
chk("zorunlu parametre * ile işaretli", "marketId:integer*" in blok, blok)
blok_p = SS.endpoint_baglami("sportId ve name ile market filtreleme araması")
chk("parametre ADIYLA sorgu → GET-filtre ucunu yüzeye çıkarır (param_boost)",
    "definition-service/markets" in blok_p, blok_p[:300])
# denetim 2026-11-02 A#5/A#6: aynı uç iki serviste → TEK satır (servisler '|' ile); kısa 'id'/'q' parametreleri eşleşir
spec2 = {"paths": {"/bff/tradoria/definition-service/markets": {"get": {"operationId": "getMarkets",
         "parameters": [{"name": "q", "in": "query", "schema": {"type": "string"}}, {"name": "id", "in": "query", "schema": {"type": "integer"}}],
         "responses": {"200": {}}}}}}
(tmp / "sky-operation-bff.json").write_text(json.dumps(spec2), encoding="utf-8")
blok_d = SS.endpoint_baglami("market listesi id ile ara q")
_sat = [ln for ln in blok_d.splitlines() if "GET /bff/tradoria/definition-service/markets" in ln]
chk("DEDUP: aynı (method,path) iki Swagger'da → TEK satır, etiket iki servisi '|' ile taşır",
    len(_sat) == 1 and "sky-panel-bff" in _sat[0] and "sky-operation-bff" in _sat[0] and "|" in _sat[0], _sat)
chk("DEDUP: parametreler BİRLEŞİR (marketId + q/id birlikte) ve kısa ad ('id'/'q') eşleşir",
    "marketId" in blok_d and "q:" in blok_d and "id:" in blok_d, blok_d[-500:])
(tmp / "sky-operation-bff.json").unlink()

# Hiç alaka yoksa boş (blok eklenmez)
chk("alakasız sorgu → boş", SS.endpoint_baglami("tamamen alakasız xyzzy foobar") == "")
# Servis yoksa boş, patlamaz
SS.SERVICES_DIR = tmp / "yok"
chk("servis dizini yoksa boş + patlamaz", SS.endpoint_baglami("market") == "")
SS.SERVICES_DIR = tmp

# ── Prompt kuralları ──
gtp = B.VARSAYILAN_PROMPTLAR["gorev_teknik_analiz"]["icerik"]
chk("prompt: SERVİS/ENDPOINT KARARI bölümü var", "SERVİS / ENDPOINT KARARI" in gtp and "PUNT ETME" in gtp)
# denetim 2026-11-02 D#3: analiz çağrısı ARAÇSIZ — prompt tarayıcı aracı değil GÖZLEM/BFF RAPORU'nu kaynak gösterir
chk("prompt: Swagger→gözlem/BFF raporu→tasarla sırası (tarayıcı aracı talimatı YOK)",
    "GÖZLEM / BFF RAPORUNDAN doğrula" in gtp and "YENİ endpoint TASARLA" in gtp and "browser_network_request" not in gtp)
chk("prompt: 'Türetilmiş' etiketi punt şablonu taşımaz ('BE teyidi' yok)", "BE teyidi]" not in gtp)
chk("prompt: keşfedilen ekran provenans cümlesi dikte etmez (yalnız etiket)", "adı YOK, kapsama dahil mi" not in gtp)
# D#5: task dili tek sabit → düzelt/cevap/öz-çözümleme turlarına da girer
chk("TASK DİLİ sabiti düzelt sistemine girer", "# TASK DİLİ" in JG._GOREV_DUZELT_SISTEM)
chk("TASK DİLİ sabiti cevap talimatına girer", "# TASK DİLİ" in JG._CEVAP_TALIMAT)
import skills.soru_cozumleme as _SC2  # noqa: E402
chk("TASK DİLİ sabiti öz-çözümleme işleme talimatına girer", "# TASK DİLİ" in _SC2.uygulama_talimati([{"id": "Q-T-001", "bagli": "", "soru": "s", "cevap": "c", "kanit": "", "gozlem": ""}]))
# D#4: ORTAK + domain kuralları görev analizine de akar (CLAUDE.md iddiası artık kodda)
_tam = B.prompt_yukle("gorev_teknik_analiz")
chk("gorev promptu ORTAK ek kuralları + TASK DİLİ içerir (prompt_yukle)", "# TASK DİLİ" in _tam and len(_tam) > len(gtp) + 3000
    and "ayrı açık-sorular bölümü YAZMA" in _tam, len(_tam))
chk("prompt: analiste teknik tasarım sorusu YASAK", "ANALİSTE SORMA" in gtp)
# açık soru üretimi: teknik tasarım sorusu dışlanır
import inspect  # noqa: E402
sq = inspect.getsource(JG._gorev_acik_sorular_uret)
chk("açık soru promptu: teknik tasarım/endpoint seçimi SORU DEĞİL", "TEKNİK TASARIM/ENDPOINT SEÇİMİ SORU DEĞİLDİR" in sq)
# owner 2026-10-26: hata kodu / özel kural yoksa → karar+not, soru değil (Fault Catalog'dan çöz)
chk("prompt: HATA KODU → Fault Catalog + mevcut kodu kullan, soru açma", "HATA KODU / errorCode" in gtp and "B-Hata-Kodu-Referansı" in gtp)
chk("prompt: ÖZEL KURAL YOKSA → NOT, soru değil", "ÖZEL KURAL YOKSA → NOT" in gtp)
# owner 2026-10-26: çok ekranlı görevde her ekran ayrı analiz edilmeli, 'diğerleri aynı' yetersiz
chk("prompt: ÇOK EKRANLI KAPSAM — her ekran ayrı ele alınır", "ÇOK EKRANLI KAPSAM" in gtp)
# owner 2026-11-01: keşfedilen ekran Amaç'ta yüzeye çıkmalı + her ekran alt-başlık + kabul kriteri ekran×alan
chk("prompt: KEŞFEDİLEN EKRAN yüzeye çıkar (Amaç'ta belirt)", "KEŞFEDİLEN EKRAN" in gtp)
chk("prompt: HER EKRAN KENDİ ALT-BAŞLIĞIYLA", "HER EKRAN KENDİ ALT-BAŞLIĞIYLA" in gtp)
chk("prompt: KABUL KRİTERLERİ = HER EKRAN × HER İLGİLİ ALAN", "KABUL KRİTERLERİ = HER EKRAN" in gtp)
# owner 2026-11-01: meta-kural ekosu + generic FE reçetesi + 'BE teyit' punt yasağı
chk("prompt: META-KURAL EKOSU YAZMA ('icat edilmez' vb.)", "META-KURAL EKOSU" in gtp)
chk("prompt: GENERİC FE/İMPLEMENTASYON REÇETESİ UYDURMA (debounce/race)", "GENERİC FE/İMPLEMENTASYON REÇETESİ" in gtp)
chk("prompt: 'BE TEYİT EDİLMELİ' bir sonuç değil — Swagger/canlı yakala", "BİR SONUÇ DEĞİL" in gtp)
# owner 2026-11-02: notta/isterde adlandırılan ekran kesin kapsam (künye yazma) + 'analist bildirdi' geçersiz kaynak
chk("prompt: NOTTA/İSTERDE ADLANDIRILAN EKRAN = KESİN KAPSAM (künye yazma)", "NOTTA/İSTERDE ADLANDIRILAN EKRAN" in gtp)
chk("prompt: 'ANALİST BİLDİRDİ' geçersiz kaynak — Swagger/gözlem raporuyla doğrula", "ANALİST BİLDİRDİ" in gtp and "DOĞRULAYIP" in gtp)
# owner 2026-11-01: Swagger servis sözleşmesi enjeksiyonu artık task-only DEĞİL — süreç + teknik de kullanır
import pathlib as _pl  # noqa: E402
_surec_src = _pl.Path("skills/surec_analizi.py").read_text(encoding="utf-8")
_teknik_src = _pl.Path("skills/teknik_analiz.py").read_text(encoding="utf-8")
chk("süreç analizi servis_sozlesme enjekte eder", "servis_sozlesme" in _surec_src and "endpoint_baglami" in _surec_src)
chk("teknik analiz servis_sozlesme enjekte eder", "servis_sozlesme" in _teknik_src and "endpoint_baglami" in _teknik_src)
import skills.gozlem as GZ  # noqa: E402
chk("gözlem: ÇOK EKRAN — her adlandırılan ekrana git", "ÇOK EKRAN" in GZ._RAPOR_FORMAT)
chk("gözlem: PARAMETRE/YETENEK DOĞRULAMA — pasif gözlem yetmez, fiilen dene", "PARAMETRE/YETENEK DOĞRULAMA" in GZ._RAPOR_FORMAT)
chk("açık soru promptu: kaynaktan türetilebilir soru üretme", "KAYNAKTAN TÜRETİLEBİLİR SORU ÜRETME" in sq)
import skills.soru_cozumleme as SC  # noqa: E402
chk("öz-çözümleme: kaynaktan türetilebilir → cevaplandi", "KAYNAKTAN TÜRETİLEBİLİR SORULAR `cevaplandi`" in SC._SISTEM if hasattr(SC, "_SISTEM") else "KAYNAKTAN TÜRETİLEBİLİR" in inspect.getsource(SC))

# --- owner 2026-11-02 (1254 3. koşu): Swagger bloğu `name`/`marketId` listelerken ana analiz 'bulunamadı / analist bildirdi'
# yazdı → 0-token çelişki dedektörü + hedefli düzelt; düzelt/cevap turuna Swagger bloğu girer; Durum hücresi kaynak adı olmaz.
import skills.servis_sozlesme as SS  # noqa: E402
_blok = (
    "### KAYITLI SERVİS SÖZLEŞMELERİ\n"
    "- **GET /bff/tradoria/definition-service/markets** — getMarkets  `[K: Swagger:sky-panel-bff|sky-operation-bff]`\n"
    "  - Parametreler (query/path): `page:integer, size:integer, sportId:integer, name:string, marketId:string`\n"
    "- **GET /bff/tradoria/event-management-service/fixture** — getFixtures  `[K: Swagger:sky-panel-bff]`\n"
    "  - Parametreler (query/path): `id:integer, name:string, externalId:string`\n"
    "- **PUT /bff/tradoria/definition-service/sports/{id}** — updateSport  `[K: Swagger:sky-panel-bff]`\n"
)
_bp = SS.blok_parametreleri(_blok)
chk("blok_parametreleri: parametreli uçlar geri ayrışır (parametresiz uç yok)",
    set(_bp) == {"/bff/tradoria/definition-service/markets", "/bff/tradoria/event-management-service/fixture"}
    and _bp["/bff/tradoria/definition-service/markets"]["parametreler"] == {"page", "size", "sportId", "name", "marketId"}
    and _bp["/bff/tradoria/definition-service/markets"]["servis"] == "sky-panel-bff|sky-operation-bff")
_md_kotu = (
    "## 3. Teknik Gereksinimler\n### 3.1. Kullanılacak servis\n"
    "Market listesi `GET /bff/tradoria/definition-service/markets` ucundan okunur.\n\n"
    "| Yetenek | Parametre | Kanıt |\n|---|---|---|\n"
    "| Ad ile arama | `name` | ⚠ Kayıtlı Swagger bloğunda doğrulanamadı `[K: ❓ Belirsiz]` |\n"
    "| ID ile arama | — | ⚠ Swagger bloğunda ID arama parametresi bulunamadı `[K: ❓ Belirsiz]` |\n"
    "| Sport filtresi | `sportId` | `[K: Swagger:sky-panel-bff]` |\n\n"
    "- `sportId`'siz çağrının tüm marketleri döndürdüğü doğrulanamadı `[K: ❓ Belirsiz]`.\n"
    "- Eşleşmeyen terim \"Market ID bulunamadı\" hatası verir.\n"
    "## 10. Teknik Borç\n- Analist, serviste id parametresinin bulunduğunu bildirdi; tam adı canlı doğrulanamadı.\n"
)
_c = SS.sozlesme_celiskileri(_md_kotu, _blok)
chk("çelişki: Swagger'da TANIMLI `name` + 'ID arama parametresi bulunamadı' + 'analist bildirdi' yakalanır (markets'a bağlı)",
    {x["parametre"] for x in _c} == {"name", "marketId"} and all(x["path"].endswith("/markets") for x in _c) and len(_c) == 3)
chk("çelişki DEĞİL: davranış belirsizliği ('sportId'siz çağrı … doğrulanamadı') ve tırnak içi UI mesajı ('Market ID bulunamadı')",
    not any("sportId'siz" in x["satir"] or "Eşleşmeyen terim" in x["satir"] for x in _c))
_md_iyi = _md_kotu.replace("⚠ Kayıtlı Swagger bloğunda doğrulanamadı `[K: ❓ Belirsiz]`", "`[K: Swagger:sky-panel-bff]`") \
    .replace("| ID ile arama | — | ⚠ Swagger bloğunda ID arama parametresi bulunamadı `[K: ❓ Belirsiz]` |",
             "| ID ile arama | `marketId` | `[K: Swagger:sky-panel-bff]` |") \
    .replace("- Analist, serviste id parametresinin bulunduğunu bildirdi; tam adı canlı doğrulanamadı.\n", "")
chk("çelişki yok: doğru analizde 0 bulgu (yanlış pozitif → gereksiz düzelt turu olmaz)", SS.sozlesme_celiskileri(_md_iyi, _blok) == [])
chk("çelişki yok: analizde anılmayan uç (fixture) için yargı yapılmaz",
    SS.sozlesme_celiskileri("`externalId` parametresi Swagger'da bulunamadı `[K: ❓ Belirsiz]`", _blok) == [])
_t = SS.celiski_talimati(_c)
chk("celiski_talimati: KESİN parametre listesi + gerçek ad (marketId) + Durum hücresi + §10/Açık Soru temizliği",
    "`marketId`" in _t and "`name`" in _t and "Swagger:sky-panel-bff" in _t and "Durum/Kanıt" in _t and "§10" in _t)
chk("celiski_talimati: boş listede boş", SS.celiski_talimati([]) == "")
import skills.jira_gorevleri as JG  # noqa: E402
_jg_src = inspect.getsource(JG)
chk("gorev_analiz_et: Swagger bloğu FE katmanında da enjekte edilir (owner 2026-11-03 — FE 'Swagger kayıtlı değil' sorusu açıyordu)",
    'if katman != "fe":\n        try:\n            from . import servis_sozlesme' not in _jg_src
    and '**({"butce": 5000, "azami": 10} if katman == "fe" else {})' in _jg_src)
chk("gorev_analiz_et: ana çıktı _sozlesme_celiski_duzelt'ten geçer (tespit → hedefli düzelt, SOZLESME_DENETIM ile kapanır)",
    "teknik = _sozlesme_celiski_duzelt(gorev, teknik, _sozlesme_blok)" in _jg_src and "SOZLESME_DENETIM" in _jg_src)
# düzelt turu: Swagger bloğu çağrıya girer (verilen ya da 0-token türetilen) — yakalanan içerikle doğrula
_yakalanan = {}
def _sahte_api(sistem, mesajlar, **kw):
    _yakalanan["icerik"] = mesajlar[0]["content"]
    return "<teknik_analiz>" + "## 1\n## 2\n## 3\n" + ("x" * 400) + "</teknik_analiz>"
_eski_api = JG._api_cagri
JG._api_cagri = _sahte_api
try:
    _mev = "## 1\n## 2\n## 3\n" + ("y" * 500)
    JG.gorev_analiz_duzelt({"key": "X-1", "summary": "s"}, _mev, "düzelt", sozlesme_blok=_blok)
    _metinler = [b.get("text", "") for b in _yakalanan["icerik"]]
    chk("gorev_analiz_duzelt: verilen Swagger bloğu 'KAYITLI SERVİS SÖZLEŞMESİ — KESİN' etiketiyle talimattan ÖNCE girer",
        any("KAYITLI SERVİS SÖZLEŞMESİ — KESİN" in m and "definition-service/markets" in m for m in _metinler)
        and _metinler[-1].startswith("[DÜZELTME TALİMATI"))
    JG.gorev_analiz_duzelt({"key": "X-1", "summary": "s"}, _mev, "düzelt", sozlesme_blok="")
    chk("gorev_analiz_duzelt: boş blok verilirse sözleşme bloğu eklenmez (türetme de yapılmaz)",
        not any("KAYITLI SERVİS SÖZLEŞMESİ — KESİN" in b.get("text", "") for b in _yakalanan["icerik"]))
finally:
    JG._api_cagri = _eski_api
chk("_CEVAP_TALIMAT: cevaptaki parametre Swagger'daki gerçek ada çözülür, 'analist bildirdi' kurulmaz, Durum hücresi 'Analist cevabı' olmaz",
    "KAYITLI SERVİS SÖZLEŞMESİ" in JG._CEVAP_TALIMAT and "'Analist cevabı' YAZMA" in JG._CEVAP_TALIMAT)
from skills.base import _TASK_DILI_KURALLARI as _TD  # noqa: E402
chk("TASK DİLİ #7: Durum/Kanıt hücresi olgusal; Swagger'da listelenen parametre için punt yazılmaz",
    "7. Tablo 'Durum'/'Kanıt' hücresi OLGUSAL" in _TD and "LİSTELENEN bir parametre" in _TD)

print()
if HATA:
    print(f"FAIL — {HATA} kontrol başarısız")
    sys.exit(1)
print("SERVİS SÖZLEŞME TESTLERİ GEÇTİ")
