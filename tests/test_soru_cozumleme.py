"""Açık Soru Öz-Çözümleme (offline, 0 token — AI/retrieval/tüketici/kod MOCK).

Kapsam:
  1. _bloklar/_adaylar: Q-T blokları, alanlar, endpoint yolu + kimlik adayları (my-permissions, `|` ayrımı)
  2. cozumle: kanıt → sınıflandırma → md'ye Agent satırları; cevaplandı/kısmen/karar; UI parser uyumlu
  3. canlı gözlem: yalnız gozlem_gerekli + cevaplanmamış sorular için TEK tur; gözlem 'cevaplandi' → durum yükselir;
     canli=False → gözlem çağrılmaz; gözlem hatası yutulur
  4. idempotent: ikinci geçişte eski Agent satırları yenilenir (çoğalmaz); zaten çözümlü bloklar atlanır
  5. güvenlik: 'Açık soru tespit edilmedi' / boş → aynen; AI bozuk → orijinal; acik_mi bayrakları; ozet()
  6. entegrasyon: gorev_analiz_et açık sorulardan sonra cozumle'yi çağırır; UI parser Agent alanlarını okur
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("BILDIRIM", "false")

from skills import soru_cozumleme as SC  # noqa: E402

_hata = 0


def chk(ad, kosul, ek=""):
    global _hata
    if not kosul:
        _hata += 1
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if ek and not kosul else ""))


SC._api_cagri = lambda *a, **k: (_ for _ in ()).throw(AssertionError("Gerçek AI çağrısı!"))
SC._corpus = lambda: [{"tip": "confluence", "rel": "confluence/RBAC.md", "metin": "my-permissions ucu yalnız menü kurulumunda ve dashboard guard'ında kullanılır. Dashboard ve profil ekranı izin gerektirmez (whitelist)."}]
import skills.degisiklik_etkisi as DE  # noqa: E402
DE.tuketici_tara = lambda adaylar, ref_dir=None: [{"aday": "my-permissions", "kaynak": "Swagger:identity.json", "nerede": "GET /user/my-permissions"},
                                                   {"aday": "my-permissions", "kaynak": "Confluence:Menu-Kurulumu", "nerede": "menü guard"}]
GOREV = {"key": "MBS-1", "summary": "Rol grubu yetkisi login"}
MD = """### Q-T-001: Dashboard/profil koşulsuz mu?
- Önem: Kritik
- Zorunlu: Evet
- Bağlı bölüm: §Çözüm (FE/BE)
- Soru: `my-permissions` boş dönünce dashboard ve profil ekranı koşulsuz mu açılacak, yoksa baseline izin seti mi dönecek?
- Beklenen yanıt: Karar — (a) whitelist (b) baseline

### Q-T-002: my-permissions tüketicileri
- Önem: Yüksek
- Bağlı bölüm: §Çözüm (BE)
- Soru: `GET /bff/spectron|fiora/identity-service/user/my-permissions` ucunu başka tüketen ekran/servis var mı?
- Beklenen yanıt: Uç tüketici listesi
"""

print("1) bloklar + adaylar")
b = SC._bloklar(MD)
chk("2 blok, alanlar", [x["id"] for x in b] == ["Q-T-001", "Q-T-002"] and b[0]["beklenen"].startswith("Karar") and b[1]["bagli"] == "§Çözüm (BE)")
ad = SC._adaylar(b[1])
chk("adaylar: my-permissions + yol parçaları (| ayrımı) + kimlik", "my-permissions" in ad and any("identity-service" in a for a in ad), ad)

print("2) cozumle — sınıflandırma + md")
yak: dict = {}


def ai_sinif(s, m):
    yak["sistem"] = s
    yak["metin"] = "\n".join(p["text"] for p in m[0]["content"])
    return ('<soru_cozum>[{"id":"Q-T-001","durum":"karar_gerekli","cevap":"Confluence dashboard+profil whitelist diyor; baseline seçeneği dokümanda yok","kanit":"[K: Confluence:RBAC]","gozlem_gerekli":true,"gozlem_adimi":"Düşük yetkili hesapla giriş yap, dashboard ve profil açılıyor mu bak"},'
            '{"id":"Q-T-002","durum":"cevaplandi","cevap":"Yalnız menü kurulumu ve dashboard guard tüketiyor; başka tüketici yok","kanit":"[K: Swagger:identity.json] [K: Confluence:Menu-Kurulumu]","gozlem_gerekli":false}]</soru_cozum>')


out = SC.cozumle(MD, GOREV, canli=False, _ai=ai_sinif)
chk("kanıtlar prompta girdi (referans parçası + tüketici taraması)", "whitelist" in yak["metin"] and "Tüketici taraması" in yak["metin"] and "Swagger:identity.json" in yak["metin"])
chk("Q-T-002 cevaplandı satırları", "- Agent durumu: cevaplandı" in out and "- Agent cevabı: Yalnız menü kurulumu" in out and "- Agent kanıtı: [K: Swagger:identity.json]" in out)
chk("Q-T-001 karar gerekli (canli=False → gözlem yok, durum değişmedi)", "- Agent durumu: karar gerekli" in out and "Agent gözlemi" not in out)
chk("orijinal alanlar korunur (Zorunlu, Önem)", "- Zorunlu: Evet" in out and out.count("### Q-T-") == 2)
chk("ozet()", SC.ozet(out) == {"toplam": 2, "cevaplandi": 1, "kismi": 0, "karar": 1}, SC.ozet(out))

print("3) canlı gözlem")
yg: dict = {}
SC.gorev_live_app_urls = lambda: ["https://uat-ornek.local/app"]
SC.canli_uygulama_baglami_hazirla = lambda **kw: (yg.update(kw) or "CANLI")


def ai_gozlem(s, m):
    yg["metin"] = "\n".join(p["text"] for p in m[0]["content"])
    return '<gozlem_cozum>[{"id":"Q-T-001","sonuc":"cevaplandi","bulgu":"Yetkisiz hesapla dashboard ve profil açıldı, menü boş","kanit":"[K: Canlı UI:/dashboard]"}]</gozlem_cozum>'


out = SC.cozumle(MD, GOREV, canli=True, _ai=ai_sinif, _ai_canli=ai_gozlem)
chk("gözlem hedefi yalnız gözlem gereken soruyu içerir (Q-T-001; Q-T-002 cevaplandı → yok)", "Q-T-001" in yg.get("hedef_tarif", "")
    and "Q-T-002" not in yg.get("hedef_tarif", "") and "gozlem_cozum" in yg.get("hedef_tarif", "") and yg.get("gorev") is True)
chk("gözlem cevaplandı → durum yükseldi + gözlem satırı + kanıt birleşti", "### Q-T-001" in out
    and out.split("### Q-T-002")[0].count("- Agent durumu: cevaplandı") == 1 and "- Agent gözlemi: Yetkisiz hesapla" in out
    and "[K: Canlı UI:/dashboard]" in out, out)
SC.gorev_live_app_urls = lambda: []
SC.live_app_urls = lambda: ["https://dev-ornek.local/app/x"]
yg.clear()
SC.cozumle(MD, GOREV, canli=True, _ai=ai_sinif, _ai_canli=ai_gozlem)
chk("task hedefi yoksa süreç ANA adresi (base) ile gözlem", yg.get("base_url_override") == "https://dev-ornek.local")
out = SC.cozumle(MD, GOREV, canli=True, _ai=ai_sinif, _ai_canli=lambda s, m: (_ for _ in ()).throw(RuntimeError("MCP yok")))
chk("gözlem hatası yutulur → referans sonucu korunur", "- Agent durumu: karar gerekli" in out and "- Agent durumu: cevaplandı" in out)

print("4) idempotent")
out2 = SC.cozumle(out, GOREV, canli=False, _ai=lambda s, m: (_ for _ in ()).throw(AssertionError("zaten çözümlü — AI çağrılmamalı")))
chk("zaten çözümlü bloklar atlanır, AI çağrılmaz, md aynı", out2 == out)
yeni_md = out.replace("- Agent durumu: karar gerekli\n", "").replace("- Agent durumu: cevaplandı\n", "")
out3 = SC.cozumle(yeni_md, GOREV, canli=False, _ai=ai_sinif)
chk("eski Agent satırları yenilenir, çoğalmaz", out3.count("- Agent cevabı:") == 2 and out3.count("- Agent kanıtı:") == 2)

print("5) güvenlik")
chk("tespit edilmedi / boş → aynen", SC.cozumle("Açık soru tespit edilmedi.", GOREV) == "Açık soru tespit edilmedi." and SC.cozumle("", GOREV) == "")
chk("AI bozuk → orijinal md", SC.cozumle(MD, GOREV, canli=False, _ai=lambda s, m: "bozuk") == MD)
chk("AI hata → orijinal md (fırlatmaz)", SC.cozumle(MD, GOREV, canli=False, _ai=lambda s, m: (_ for _ in ()).throw(RuntimeError("x"))) == MD)
os.environ["SORU_COZUMLEME"] = "false"
chk("SORU_COZUMLEME=false → kapalı", SC.acik_mi() is False)
os.environ.pop("SORU_COZUMLEME", None)
SC.hizli_mod_acik = lambda: True
chk("HIZLI_MOD → kapalı", SC.acik_mi() is False)
SC.hizli_mod_acik = lambda: False
chk("varsayılan açık", SC.acik_mi() is True)

print("6) entegrasyon")
from skills import jira_gorevleri as JG  # noqa: E402
src = Path(JG.__file__).read_text(encoding="utf-8")
chk("gorev_analiz_et: açık sorulardan sonra öz-çözümleme (canlı bayrağıyla)", "_sc_cozumle(acik, gorev, canli=bool(canli_baglam))" in src)
ui = Path(JG.__file__).parent.parent.joinpath("templates/index.html").read_text(encoding="utf-8")
chk("UI: Agent alanları parse + ön-doldurma + rozet", "al('Agent durumu')" in ui and "agentOn" in ui and "jg-sk-agent-ozet" in ui)

print()
if _hata:
    print(f"SORU ÇÖZÜMLEME TESTLERİ BAŞARISIZ ({_hata} hata)")
    sys.exit(1)
print("SORU ÇÖZÜMLEME TESTLERİ GEÇTİ")
