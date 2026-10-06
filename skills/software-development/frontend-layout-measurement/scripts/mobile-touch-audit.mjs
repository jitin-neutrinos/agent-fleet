// Mobile touch-target / overflow / legibility audit — parameterized probe.
// Usage: node mobile-touch-audit.mjs <baseUrl> [route1 route2 ...]
// Default routes: / (edit for your app). Requires playwright:
//   const { chromium } = require('<any repo with playwright>/node_modules/playwright');
// Checks per viewport x route: real horizontal overflow (scrollWidth-
// clientWidth), tap targets < 24px min-side, console errors. Prints a
// per-viewport report; exit 1 if any REAL defect found.
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');

const VIEWPORTS = [
  { name: 'm-360', width: 360, height: 740 },
  { name: 'm-390', width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 3 },
  { name: 'm-412', width: 412, height: 915, isMobile: true, hasTouch: true, deviceScaleFactor: 2.6 },
  { name: 't-768', width: 768, height: 1024, isMobile: true, hasTouch: true },
];
const BASE = process.argv[2] || 'http://localhost:3105';
const ROUTES = process.argv.slice(3).length ? process.argv.slice(3) : ['/'];

(async () => {
  const browser = await chromium.launch({ args: ['--headless=new'] });
  let defects = 0;
  for (const vp of VIEWPORTS) {
    const ctx = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      isMobile: !!vp.isMobile, hasTouch: !!vp.hasTouch,
      deviceScaleFactor: vp.deviceScaleFactor || 1,
    });
    const page = await ctx.newPage();
    const errs = [];
    page.on('console', m => m.type() === 'error' && errs.push(m.text().slice(0, 120)));
    page.on('pageerror', e => errs.push('PAGEERROR ' + e.message.slice(0, 120)));
    for (const route of ROUTES) {
      await page.goto(BASE + route, { waitUntil: 'domcontentloaded', timeout: 20000 });
      await page.waitForTimeout(2600); // hydration + staged animations
      const r = await page.evaluate(() => {
        const doc = document.documentElement;
        const out = { hOverflow: doc.scrollWidth - doc.clientWidth, tiny: [] };
        for (const el of document.querySelectorAll('a,button,[role="button"],input,select,summary')) {
          const b = el.getBoundingClientRect();
          if (b.width === 0 || b.height === 0) continue;
          if (Math.min(b.width, b.height) < 24) {
            out.tiny.push(`${el.tagName.toLowerCase()} ${Math.round(b.width)}x${Math.round(b.height)} ${(el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 30)}`);
          }
        }
        return out;
      });
      const key = `${vp.name}${route}`;
      const bad = r.hOverflow > 1 || r.tiny.length;
      if (bad) defects++;
      console.log(`${bad ? 'FAIL' : 'PASS'} ${key}${r.hOverflow > 1 ? ` hOverflow=${r.hOverflow}px` : ''}${r.tiny.length ? ` tinyTargets=${r.tiny.length}` : ''}`);
      r.tiny.forEach(t => console.log('  tiny:', t));
    }
    if (errs.length) { console.log(`console ${vp.name}:`, errs.slice(0, 5)); defects++; }
    await ctx.close();
  }
  await browser.close();
  process.exit(defects ? 1 : 0);
})().catch(e => { console.error('AUDIT FAILED', e); process.exit(2); });
