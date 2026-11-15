// Captures real Stellaris screens for the brag video with the isolated Playwright WebKit under /tmp.
// Read-only: navigates, toggles panels and scrolls. Never submits messages, so no model calls are made.
// Run from the repo root:  node brag-output/work/capture.cjs
process.env.PLAYWRIGHT_BROWSERS_PATH ||= '/tmp/stellaris-webtest/browsers';
const { webkit } = require('/tmp/stellaris-webtest/node_modules/playwright');
const fs = require('fs');
const path = require('path');

const ORIGIN = 'http://127.0.0.1:3000';
const P = 'prj_220c07d8abd44eba867d4f15d5bb94a4';
const EXP = 'exp_5920fd34b4b448f8b029a82d3ab4d0a6';
const RUN_MEASURE = 'run_3a7c5660bec647ba88f24912a2ca51df';
const RUN_CHART = 'run_a41f877b427a45a5ad2e5601b4e83d05';
const RUN_REPORT = 'run_a528f8f0739a4af1a9570f13abaac05c';
const REPORT = 'art_7637bfb34fb842acb195e8bccf07b92e';
const OUT = path.join(__dirname, 'shots');
const t0 = Date.now();
const log = (m) => console.log(`${((Date.now() - t0) / 1000).toFixed(1)}s ${m}`);

// [name, url, { assistant: open the Assistant rail, scroll: capture scroll positions }]
const pages = [
  ['projects', '/projects', {}],
  ['home', `/projects/${P}`, { scroll: true }],
  ['research', `/projects/${P}/research`, { assistant: true }],
  ['sources', `/projects/${P}/research?tab=sources`, {}],
  ['studio', `/projects/${P}/studio?experiment=${EXP}`, { scroll: true }],
  ['runs', `/projects/${P}/runs`, {}],
  ['run-measure', `/projects/${P}/runs/${RUN_MEASURE}`, { scroll: true }],
  ['run-chart', `/projects/${P}/runs/${RUN_CHART}`, { scroll: true }],
  ['run-report', `/projects/${P}/runs/${RUN_REPORT}`, { scroll: true }],
  ['report', `/projects/${P}/reports/${REPORT}`, { scroll: true }],
  ['reports', `/projects/${P}/reports`, {}],
  ['materials', `/projects/${P}/materials`, {}],
  ['graph', `/projects/${P}/graph`, {}],
];

async function settle(page) {
  await page.waitForLoadState('load', { timeout: 90000 }).catch(() => {});
  // Wait for skeleton placeholders to clear, then let charts/graph layouts finish animating.
  await page.waitForFunction(() => !document.querySelector('[aria-busy="true"]'), null, { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(3500);
}

async function scrollShots(page, dir, name) {
  // Screenshot successive positions of the largest scrollable region (report/chat bodies scroll internally).
  const handle = await page.evaluateHandle(() => {
    const all = [...document.querySelectorAll('*')].filter((el) => {
      const s = getComputedStyle(el);
      return /(auto|scroll)/.test(s.overflowY) && el.scrollHeight > el.clientHeight + 40 && el.clientHeight > 300;
    });
    all.sort((a, b) => b.clientHeight * b.clientWidth - a.clientHeight * a.clientWidth);
    return all[0] || document.scrollingElement;
  });
  const { sh, ch } = await handle.evaluate((el) => ({ sh: el.scrollHeight, ch: el.clientHeight }));
  let i = 0;
  for (let y = 0; y < sh && i < 8; y += Math.round(ch * 0.8), i++) {
    await handle.evaluate((el, top) => el.scrollTo(0, top), y);
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(dir, `${name}-scroll${i}.png`) });
  }
  await handle.evaluate((el) => el.scrollTo(0, 0));
}

const ONLY = process.argv.slice(2); // optional shot names to (re)capture

(async () => {
  const browser = await webkit.launch({ timeout: 60000 });
  log('webkit launched');
  const theme = 'dark';
  const dir = path.join(OUT, theme);
  fs.mkdirSync(dir, { recursive: true });
  for (const [name, url, opt] of pages) {
    if (ONLY.length && !ONLY.includes(name)) continue;
    // A fresh context per page: a late client-side redirect on one page can't cancel the next navigation.
    const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2, colorScheme: theme });
    await ctx.addInitScript(({ t, rail }) => {
      try { localStorage.setItem('stellaris-theme', t); localStorage.setItem('stellaris.chatRailOpen', rail ? '1' : '0'); } catch {}
      // Hide the Next.js dev-mode badge so it never appears in the video.
      const hide = () => { const st = document.createElement('style'); st.textContent = 'nextjs-portal{display:none!important}'; document.documentElement.appendChild(st); };
      if (document.documentElement) hide(); else document.addEventListener('DOMContentLoaded', hide);
    }, { t: theme, rail: !!opt.assistant });
    const page = await ctx.newPage();
    try {
      await page.goto(ORIGIN + url, { waitUntil: 'domcontentloaded', timeout: 90000 });
      await settle(page);
      await page.screenshot({ path: path.join(dir, `${name}.png`) });
      log(name);
      if (opt.assistant) {
        const chat = page.locator('section[aria-label="Assistant"]').first();
        if (await chat.count()) await chat.screenshot({ path: path.join(dir, 'assistant-panel.png') }).catch(() => {});
        const box = page.getByPlaceholder('Ask a question or plan an experiment…');
        if (await box.count()) {
          await box.first().fill('Is there a correlation between height and weight, and can we generalize an equation for it?');
          await page.waitForTimeout(500);
          await page.screenshot({ path: path.join(dir, 'research-typed.png') });
          await box.first().fill(''); // cleared, never sent
        }
        log('assistant');
      }
      if (opt.scroll) { await scrollShots(page, dir, name); log(`${name} scrolled`); }
    } catch (e) {
      log(`FAILED ${name}: ${e.message.split('\n')[0]}`);
    }
    await ctx.close();
  }
  await browser.close();
  log(`done -> ${dir}`);
})().catch((e) => { console.error(e); process.exit(1); });
