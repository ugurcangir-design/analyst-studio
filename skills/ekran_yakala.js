// Analyst Studio — canlı ekran YAKALAYICI (0 token).
// Kullanım: node ekran_yakala.js '<json>'   (json: {profile, url, out, bekle?, genislik?, yukseklik?, zamanAsimiMs?})
// Oturumlu Chrome profili (slot) ile sayfayı açar, hedef selector'ü bekler, sayfa İÇİNDE document.styleSheets
// kurallarını serileştirir (MUI/emotion prod'da kurallar CSSOM'da — dump-dom'da <style> boş kalır), outerHTML +
// ekran görüntüsünü alır ve KENDİ KENDİNE YETERLİ baseline.html üretir (script yok, CSS gömülü, varlık yolları mutlak).
// Çıktılar: <out>/baseline.html · live.png · meta.json. stdout: tek satır JSON özet. Hata → stderr 'ERR …' + exit 1.
const path = require('path');
const fs = require('fs');
const { chromium } = require('playwright-core');

(async () => {
  const arg = JSON.parse(process.argv[2] || '{}');
  const { profile, url, out } = arg;
  if (!profile || !url || !out) throw new Error('profile/url/out zorunlu');
  const bekle = arg.bekle || 'table tbody tr, [role=grid] [role=row], form, input[type=password], :text("Access Denied"), :text("do not have permission")';
  const genislik = arg.genislik || 1560, yukseklik = arg.yukseklik || 1100;
  const zamanAsimi = arg.zamanAsimiMs || 45000;
  fs.mkdirSync(out, { recursive: true });
  const t0 = Date.now();
  const ctx = await chromium.launchPersistentContext(profile, {
    channel: 'chrome', headless: true, viewport: { width: genislik, height: yukseklik },
    args: ['--disable-extensions', '--no-first-run', '--no-default-browser-check'],
  });
  try {
    const page = ctx.pages()[0] || await ctx.newPage();
    // networkidle KULLANMA: SPA bildirim polling'i yüzünden hiç gelmiyor (spike 2026-11-04).
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: zamanAsimi });
    let beklendi = true;
    try { await page.waitForSelector(bekle, { timeout: Math.min(30000, zamanAsimi) }); } catch (e) { beklendi = false; }
    await page.waitForTimeout(1500);
    const data = await page.evaluate(() => {
      const css = [];
      for (const sh of document.styleSheets) {
        try { css.push({ href: sh.href || '(inline)', rules: [...sh.cssRules].map(r => r.cssText).join('\n') }); }
        catch (e) { css.push({ href: sh.href || '(inline)', rules: '', error: String(e) }); }
      }
      return {
        url: location.href, title: document.title, html: document.documentElement.outerHTML, css,
        login: !!document.querySelector('input[type=password]') || /\/login(\b|\/|\?)/.test(location.pathname),
        // yetki reddi sayfası (SPA 403 görünümü) — baseline olarak İŞE YARAMAZ
        erisim_yok: /access denied|do not have permission|yetkiniz yok|erişim engellendi|\b403\b/i.test((document.body && document.body.innerText || '').slice(0, 4000)),
      };
    });
    await page.screenshot({ path: path.join(out, 'live.png'), fullPage: false });
    const origin = new URL(data.url).origin;
    const abs = p => (p.startsWith('/') && !p.startsWith('//') ? origin + p : p);
    let html = data.html
      .replace(/<script\b[\s\S]*?<\/script>/g, '')
      .replace(/<noscript\b[\s\S]*?<\/noscript>/g, '')
      .replace(/<link[^>]+rel="stylesheet"[^>]*>/g, '')
      .replace(/<style\b[\s\S]*?<\/style>/g, '')
      .replace(/<base\b[^>]*>/g, '')
      .replace(/\s(src|href|srcset)="(\/[^"]*)"/g, (m, a, p) => ` ${a}="${abs(p)}"`);
    const allCss = data.css.map(c => c.rules || '').join('\n')
      .replace(/url\((["']?)(\/[^)"']+)\1\)/g, (m, q, p) => `url(${abs(p)})`);
    const style = `<style id="baseline-css">${allCss}</style>`;
    html = /<\/head>/.test(html) ? html.replace('</head>', style + '</head>') : style + html;
    html = `<!-- baseline: ${data.url} · ${new Date().toISOString()} · Analyst Studio ekran_yakala -->\n` + html;
    fs.writeFileSync(path.join(out, 'baseline.html'), html);
    const ozet = {
      url: data.url, title: data.title, login: data.login, erisim_yok: data.erisim_yok, beklendi, ms: Date.now() - t0,
      html_kc: data.html.length, css_kc: allCss.length, sheet: data.css.length,
      css_hata: data.css.filter(c => c.error).length,
    };
    fs.writeFileSync(path.join(out, 'meta.json'), JSON.stringify(ozet, null, 1));
    console.log(JSON.stringify(ozet));
  } finally {
    await ctx.close().catch(() => {});
  }
})().catch(e => { console.error('ERR ' + (e && e.message ? e.message : e)); process.exit(1); });
