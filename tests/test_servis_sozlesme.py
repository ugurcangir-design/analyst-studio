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

# Hiç alaka yoksa boş (blok eklenmez)
chk("alakasız sorgu → boş", SS.endpoint_baglami("tamamen alakasız xyzzy foobar") == "")
# Servis yoksa boş, patlamaz
SS.SERVICES_DIR = tmp / "yok"
chk("servis dizini yoksa boş + patlamaz", SS.endpoint_baglami("market") == "")
SS.SERVICES_DIR = tmp

# ── Prompt kuralları ──
gtp = B.VARSAYILAN_PROMPTLAR["gorev_teknik_analiz"]["icerik"]
chk("prompt: SERVİS/ENDPOINT KARARI bölümü var", "SERVİS / ENDPOINT KARARI" in gtp and "PUNT ETME" in gtp)
chk("prompt: Swagger→canlı gözlem→tasarla sırası", "browser_network_request" in gtp and "YENİ endpoint TASARLA" in gtp)
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
import skills.gozlem as GZ  # noqa: E402
chk("gözlem: ÇOK EKRAN — her adlandırılan ekrana git", "ÇOK EKRAN" in GZ._RAPOR_FORMAT)
chk("açık soru promptu: kaynaktan türetilebilir soru üretme", "KAYNAKTAN TÜRETİLEBİLİR SORU ÜRETME" in sq)
import skills.soru_cozumleme as SC  # noqa: E402
chk("öz-çözümleme: kaynaktan türetilebilir → cevaplandi", "KAYNAKTAN TÜRETİLEBİLİR SORULAR `cevaplandi`" in SC._SISTEM if hasattr(SC, "_SISTEM") else "KAYNAKTAN TÜRETİLEBİLİR" in inspect.getsource(SC))

print()
if HATA:
    print(f"FAIL — {HATA} kontrol başarısız")
    sys.exit(1)
print("SERVİS SÖZLEŞME TESTLERİ GEÇTİ")
