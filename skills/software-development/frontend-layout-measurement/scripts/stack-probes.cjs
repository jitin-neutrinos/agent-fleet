// Stack/slide-deck probe kit — parameterized, playwright from PLAYWRIGHT_PATH.
// Usage:
//   node stack-probes.cjs veil [baseURL]     → veil fade timeline samples
//   node stack-probes.cjs ghost [baseURL]    → visible-card lifecycle (wheel 1→2→1)
//   node stack-probes.cjs scrollfeel [baseURL] → gesture-scoped accumulator probes
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const BASE = process.argv[3] || 'http://localhost:3105';
const CHROME = process.env.HOME + '/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome';
const mode = process.argv[2] || 'ghost';

(async () => {
  const b = await chromium.launch({ executablePath: CHROME, args: ['--headless=new'] });
  const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  await p.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(2600); // veil + settle
  const cur = () => p.evaluate(() => Array.from(document.querySelectorAll('button[aria-label*="Go to"]')).findIndex(x => x.getAttribute('aria-current') === 'true'));
  const wheel = (dy) => p.evaluate((dy) => window.dispatchEvent(new WheelEvent('wheel', { deltaY: dy, cancelable: true })), dy);

  if (mode === 'veil') {
    const out = await p.evaluate(() => new Promise((res) => {
      const s = [];
      const tick = () => {
        const veil = document.querySelector('.intro-veil');
        if (s.length < 40) {
          s.push({ t: Math.round(performance.now()), op: veil ? getComputedStyle(veil).opacity : 'gone' });
          requestAnimationFrame(tick);
        } else res(s);
      };
      requestAnimationFrame(tick);
    }));
    console.log(JSON.stringify(out.filter((x, i) => i % 4 === 0)));
  } else if (mode === 'ghost') {
    const vis = () => p.evaluate(() => Array.from(document.querySelectorAll('.stack-card')).map((c, i) => ({ i, v: getComputedStyle(c).visibility })));
    console.log('rest:', JSON.stringify(await vis()));
    await wheel(120); await p.waitForTimeout(400);
    console.log('mid 1→2:', JSON.stringify(await vis()), '(non-involved must be hidden)');
    await p.waitForTimeout(1400);
    console.log('rest 2: visible =', (await vis()).filter(x => x.v === 'visible').length, 'dot:', await cur());
    await wheel(-120); await p.waitForTimeout(400);
    console.log('mid 2→1:', JSON.stringify(await vis()));
    await p.waitForTimeout(1400);
    console.log('rest 1: dot:', await cur());
  } else if (mode === 'scrollfeel') {
    const burst = async (n, dy, gap) => { for (let i = 0; i < n; i++) { await wheel(dy); await p.waitForTimeout(gap); } };
    await burst(6, 8, 300); await p.waitForTimeout(1600);
    console.log('slow rub →', await cur(), '(want 0: no credit banking)');
    await burst(3, 20, 80); await p.waitForTimeout(2000);
    console.log('one burst →', await cur(), '(want 1)');
    await burst(1, -120, 0); await p.waitForTimeout(1600);
    console.log('up →', await cur(), '(want 0)');
  }
  await b.close();
})().catch((e) => { console.error('probe failed', e); process.exit(1); });
