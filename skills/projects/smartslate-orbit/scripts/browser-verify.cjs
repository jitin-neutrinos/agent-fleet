#!/usr/bin/env node
/**
 * Browser-verify an Orbit deploy — the gate curl cannot provide.
 *
 * A curl 200 for the page HTML plus a curl 200 for the JSON endpoint, checked
 * separately, both pass while the page is dead in a browser (the JS crash when
 * the two meet — e.g. `.map` on a wrapped {key:[...]} envelope). This script
 * logs in through the real form and walks the routes, failing on ANY pageerror.
 *
 * Usage: node scripts/browser-verify.cjs [baseUrl] [email] [password]
 *   env overrides: ORBIT_BASE_URL, ORBIT_QA_EMAIL, ORBIT_QA_PASSWORD
 */
const { chromium } = require('/home/notjitin/Work/projects/astra-webui/node_modules/playwright');

const args = process.argv.slice(2);
const base = args[0] || process.env.ORBIT_BASE_URL || 'https://orbit.jitinnair.com';
const email = args[1] || process.env.ORBIT_QA_EMAIL || 'qa-admin@orbit.test';
const pass = args[2] || process.env.ORBIT_QA_PASSWORD || 'orbitqa1234';

// route -> content marker that proves the page actually rendered
const ROUTES = [
  ['/app', /dashboard|onboarding|course/i],
  ['/app/courses', /courses/i],
  ['/app/members', /members/i],
  ['/app/approvals', /approval inbox/i],
  ['/app/settings', /settings|ai configuration/i],
  ['/pricing', /pricing|₹/i],
];

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));

  await page.goto(base + '/login', { waitUntil: 'networkidle', timeout: 45000 });
  await page.fill('input[type=email], input[name=email]', email);
  await page.fill('input[type=password]', pass);
  await page.click('button[type=submit]');
  await page.waitForURL('**/app**', { timeout: 20000 }).catch(() => {});

  let failed = 0;
  for (const [route, marker] of ROUTES) {
    errors.length = 0;
    await page.goto(base + route + '?cb=' + Date.now(), { waitUntil: 'networkidle', timeout: 45000 });
    await page.waitForTimeout(1200);
    const body = ((await page.textContent('body').catch(() => '')) || '').replace(/\s+/g, ' ');
    const markerOk = marker.test(body);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    const pageErr = errors[0];
    const ok = markerOk && !pageErr;
    if (!ok) failed++;
    console.log(`${ok ? 'PASS' : 'FAIL'} ${route}` + (pageErr ? ` — pageerror: ${pageErr}` : '') + (!markerOk ? ' — marker missing' : '') + (overflow ? ' — horizontal overflow' : ''));
  }
  await browser.close();
  console.log(failed ? `${failed}/${ROUTES.length} routes FAILED` : `all ${ROUTES.length} routes OK`);
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.error('verify crashed:', e.message); process.exit(1); });
