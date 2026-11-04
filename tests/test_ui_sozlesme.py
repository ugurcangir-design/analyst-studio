"""UI DAVRANIŞ SÖZLEŞMESİ (offline, 0 token) — görsel yeniden tasarım (UI v4, 2026-11-04) işlevselliği bozmasın.

Kural: JS'in referans verdiği her `getElementById('x')` id'si ve `querySelector('#x' / '.y')` seçicisi şablonlarda (index.html +
screens/*.html) ya da JS'in ürettiği HTML'de bulunmalı; HTML'deki her `onclick="fn("` fonksiyonu JS'te tanımlı olmalı.
Tasarım değişikliği bir id/sınıf/onclick'i kaldırır ya da yeniden adlandırırsa bu test söyler. Şablon içindeki JS string'lerinde
üretilen id'ler (`id="pano-model"` gibi) de şablon metninde geçtiğinden sayılır. Bilinçli istisnalar `_ISTISNA`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
HATA = 0


def chk(ad, kosul, ek=""):
    global HATA
    print(("  ✓ " if kosul else "  ✗ ") + ad + (f"  [{ek}]" if (ek and not kosul) else ""))
    if not kosul:
        HATA += 1


idx = (KOK / "templates" / "index.html").read_text(encoding="utf-8")
ekranlar = {p.name: p.read_text(encoding="utf-8") for p in sorted((KOK / "templates" / "screens").glob("*.html"))}
hepsi = idx + "\n" + "\n".join(ekranlar.values())

# ── 1 getElementById → id="…" (şablonda ya da JS'in ürettiği string'de) ──
_ISTISNA = {"jg-ai-btn"}   # kaldırılmış 'AI ile Sınıflandır' düğmesine ölü referans (triyaj 2026-10-27) — JS null-guard'lı
js_idler = sorted(set(re.findall(r"getElementById\(\s*'([A-Za-z0-9_-]+)'\s*\)", hepsi)))
html_idler = set(re.findall(r"""\bid\s*=\s*["']([A-Za-z0-9_-]+)["']""", hepsi))
# JS içinde şablon-literal ile üretilen id'ler: id="x-${...}" → ön-ek eşleşmesi
dinamik_onek = {m for m in re.findall(r"""id="([A-Za-z0-9_-]+)\$\{""", hepsi)}
eksik = [i for i in js_idler if i not in html_idler and i not in _ISTISNA and not any(i.startswith(p) for p in dinamik_onek)]
chk(f"JS'in referans verdiği {len(js_idler)} id şablonda var", not eksik, ", ".join(eksik[:12]))

# ── 2 querySelector('#x') / ('.y') seçicileri ──
secici = sorted(set(re.findall(r"querySelector(?:All)?\(\s*'([^']+)'\s*\)", hepsi)))
css_siniflar = set(re.findall(r"""class\s*=\s*["']([^"']+)["']""", hepsi))
sinif_kumesi = {c for grup in css_siniflar for c in grup.split()}
sinif_kumesi |= set(re.findall(r"classList\.(?:add|toggle)\(\s*'([A-Za-z0-9_-]+)'", hepsi))   # JS'in eklediği sınıflar
_SECICI_ISTISNA = {".epic", ".mermaid", ".prompt-nav-item", "#theme-toggle"}   # JS/marked tarafından dinamik üretilen sınıf/id'ler
eksik_sec = []
for s in secici:
    # her basit parça: #id → id var mı; .cls → sınıf var mı (karmaşık seçicilerde yalnız id/sınıf token'ları bakılır)
    for tok in re.findall(r"#([A-Za-z0-9_-]+)", s):
        if tok not in html_idler and f"#{tok}" not in _SECICI_ISTISNA and not any(tok.startswith(p) for p in dinamik_onek):
            eksik_sec.append(f"{s} → #{tok}")
    for tok in re.findall(r"\.([A-Za-z0-9_-]+)", s):
        if tok not in sinif_kumesi and f".{tok}" not in _SECICI_ISTISNA:
            eksik_sec.append(f"{s} → .{tok}")
chk(f"{len(secici)} querySelector seçicisinin id/sınıf token'ları mevcut", not eksik_sec, "; ".join(eksik_sec[:8]))

# ── 3 onclick="fn(" → function fn / const fn = ──
# işleyici attribute'undaki ÇAĞRILAR: önünde '.' olmayan tanımlayıcılar (metot adları — this.closest() gibi — hariç)
_ATTR = re.compile(r'on(?:click|change|input|keydown|submit)\s*=\s*"([^"]*)"')
onclicks = sorted({f for attr in _ATTR.findall(hepsi)
                   for f in re.findall(r"(?<![\w.$])([A-Za-z_][A-Za-z0-9_]*)\s*\(", attr)})
tanimli = set(re.findall(r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", hepsi))
tanimli |= set(re.findall(r"\b(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?(?:\(|function)", hepsi))
tanimli |= set(re.findall(r"\bwindow\.([A-Za-z_][A-Za-z0-9_]*)\s*=", hepsi))
yerlesik = {"if", "event", "this", "document", "window", "confirm", "alert", "fetch", "setTimeout", "encodeURIComponent",
            "String", "Number", "parseInt", "open", "JSON", "Object", "Array", "Math", "requestAnimationFrame", "escHtml",
            "location", "navigator", "localStorage", "history", "prompt", "toast"}
eksik_fn = [f for f in onclicks if f not in tanimli and f not in yerlesik]
chk(f"HTML'deki {len(onclicks)} olay işleyicisi JS'te tanımlı", not eksik_fn, ", ".join(eksik_fn[:12]))

# ── 4 ekran partial'ları index.html'e include ediliyor + her ekranın page id'si var ──
inc = set(re.findall(r"""\{%\s*include\s+['"]screens/([^'"]+)['"]""", idx))
chk("tüm screens/*.html partial'ları index.html'de include edilmiş",
    all(n in inc for n in ekranlar if not n.startswith("_") and n != "README.md"), ", ".join(n for n in ekranlar if n not in inc and not n.startswith("_")))
page_idler = {i for i in html_idler if i.startswith("page-")}
switch_hedef = set(re.findall(r"switchTab\(\s*'([A-Za-z0-9_-]+)'", hepsi))
eksik_page = [t for t in sorted(switch_hedef) if f"page-{t}" not in page_idler]
chk(f"switchTab hedeflerinin ({len(switch_hedef)}) page-<id> kapsayıcısı var", not eksik_page, ", ".join(eksik_page))

# ── 5 tema token sözleşmesi: tasarım değişse de bu token adları kalmalı (tüm ekranlar bunlara bağlı) ──
TOKENLER = ["--bg", "--surface", "--surface2", "--border", "--border-strong", "--text", "--text2", "--text3", "--accent",
            "--accent-soft", "--green", "--yellow", "--red", "--blue", "--run", "--radius", "--radius-sm", "--font-display"]
root = idx[idx.index(":root"):idx.index("}", idx.index(":root"))]
eksik_tok = [t for t in TOKENLER if f"{t}:" not in root]
chk("çekirdek tema token'ları :root'ta tanımlı", not eksik_tok, ", ".join(eksik_tok))
chk("açık tema bloğu ([data-theme=\"light\"]) var", '[data-theme="light"]' in idx)

print(f"\nid: {len(js_idler)} · seçici: {len(secici)} · işleyici: {len(onclicks)} · ekran: {len(ekranlar)}")
print(f"{'UI SÖZLEŞME TESTLERİ GEÇTİ' if HATA == 0 else str(HATA) + ' HATA'}")
sys.exit(1 if HATA else 0)
