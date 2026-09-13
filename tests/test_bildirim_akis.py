"""Analiz yaşam döngüsü bildirimi — geçiş + dedup testi (0 token, gerçek bildirim ATEŞLENMEZ).

app._analiz_bildirim_kontrol'ü workflow.ozet mock'uyla sürer; bildirim.gonder yakalanır.
Çalıştır:  venv/bin/python tests/test_bildirim_akis.py
"""

import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("JIRA_KOPRU", "false")

import workflow as wf  # noqa: E402
from skills import bildirim  # noqa: E402
import app  # noqa: E402  (import-time: thread BAŞLATMAZ — threadler yalnız __main__'de)

basari = 0


def kontrol(ad: str, kosul: bool) -> None:
    global basari
    if not kosul:
        raise SystemExit(f"FAIL {ad}")
    basari += 1
    print(f"  ✓ {ad}")


_cagrilar: list = []
bildirim.gonder = lambda baslik, metin, alt_metin="": _cagrilar.append((baslik, metin)) or True
app._aktif_dokuman_adi = lambda: "TestDoc.md"
app._acik_soru_sayisi = lambda: 5


def durum(**k):
    wf.ozet = lambda: k


app._son_bildirilen_analiz["anahtar"] = None

durum(calisiyor=True)
app._analiz_bildirim_kontrol()
kontrol("çalışırken bildirim yok", len(_cagrilar) == 0)

durum(calisiyor=False, onay_bekleniyor=True)
app._analiz_bildirim_kontrol()
kontrol("süreç onayı → 1 bildirim", len(_cagrilar) == 1)
kontrol("başlık 'Süreç analizi tamamlandı'", _cagrilar[0][0] == "Süreç analizi tamamlandı")
kontrol("metinde doküman + açık soru sayısı", "TestDoc.md" in _cagrilar[0][1] and "5 açık soru" in _cagrilar[0][1])

app._analiz_bildirim_kontrol()
kontrol("aynı durumda tekrar bildirim YOK (dedup)", len(_cagrilar) == 1)

durum(calisiyor=True)   # teknik çalışıyor
app._analiz_bildirim_kontrol()
kontrol("teknik çalışırken bildirim yok + dedup korunur", len(_cagrilar) == 1)

durum(calisiyor=False, teknik_onay_bekleniyor=True)
app._analiz_bildirim_kontrol()
kontrol("teknik onayı → 2. bildirim", len(_cagrilar) == 2 and _cagrilar[1][0] == "Teknik analiz tamamlandı")

durum(calisiyor=False)   # idle → dedup sıfırlanır
app._analiz_bildirim_kontrol()
durum(calisiyor=False, onay_bekleniyor=True)   # yeni koşu
app._analiz_bildirim_kontrol()
kontrol("idle sonrası yeni koşu → tekrar bildirim (3)", len(_cagrilar) == 3)

app._son_bildirilen_analiz["anahtar"] = None
durum(calisiyor=False, hata="alt süreç çöktü", durum="surec_analizi_hata")
app._analiz_bildirim_kontrol()
kontrol("hata → bildirim (4)", len(_cagrilar) == 4 and _cagrilar[3][0] == "Analiz tamamlanamadı")

# ── #2: Jira köprü komut bildirimi (yorum + UI kanalı ortak helper) ───────────
_cagrilar.clear()
app._kopru_komut_bildir("MBS-1", "analiz")
kontrol("köprü analiz → yerel bildirim", len(_cagrilar) == 1 and "MBS-1" in _cagrilar[0][1] and "analiz" in _cagrilar[0][1].lower())
app._kopru_komut_bildir("MBS-2", "guncelle")
kontrol("köprü güncelle → bildirim", "güncellendi" in _cagrilar[1][1])
app._kopru_komut_bildir("MBS-3", "duzelt", ok=False, hata="401 yetki")
kontrol("köprü hata → hata bildirimi", _cagrilar[2][0] == "Jira köprüsü — hata" and "401" in _cagrilar[2][1])

print(f"\nBİLDİRİM AKIŞ TESTLERİ GEÇTİ ({basari} kontrol)")
