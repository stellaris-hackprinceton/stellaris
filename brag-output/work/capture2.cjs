// Feature-based capture pass for the brag video (isolated Playwright WebKit under /tmp).
// Never submits a message: prompts are recreated by scrolling the real conversation, so no model calls are made.
// Opening the Terminal starts a temporary terminal session container for the project (no commands are typed).
//   node brag-output/work/capture2.cjs [shot names...]
process.env.PLAYWRIGHT_BROWSERS_PATH ||= '/tmp/stellaris-webtest/browsers';
const { webkit } = require('/tmp/stellaris-webtest/node_modules/playwright');
const fs = require('fs');
const path = require('path');

const ORIGIN = 'http://127.0.0.1:3000';
const P = 'prj_220c07d8abd44eba867d4f15d5bb94a4';
const P_PAPER = 'prj_9cc7c62efc024dba853f24b79b953385';
const EXP = 'exp_5920fd34b4b448f8b029a82d3ab4d0a6';
const CSV = 'art_420269292fe542109ca7bdc7d3ef2b3b';
const P_VIDEO = 'prj_5bc1b4cb38e741b7942c4a2dcea4e2c9'; // test1: webcam recordings + motion tracking
const EXP_VIDEO = 'exp_5e0ab901e55440b5a269fcad1e348afb';
const OUT = path.join(__dirname, 'shots', 'v2');
const ONLY = process.argv.slice(2);
const t0 = Date.now();
const log = (m) => console.log(`${((Date.now() - t0) / 1000).toFixed(1)}s ${m}`);
fs.mkdirSync(OUT, { recursive: true });

async function open(browser, url, { rail = false, railWidth = 700 } = {}) {
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2, colorScheme: 'dark' });
  await ctx.addInitScript(({ rail, railWidth }) => {
    try {
      localStorage.setItem('stellaris-theme', 'dark');
      localStorage.setItem('stellaris.chatRailOpen', rail ? '1' : '0');
      localStorage.setItem('stellaris.chatRailWidth', String(railWidth));
    } catch {}
    const hide = () => { const st = document.createElement('style'); st.textContent = 'nextjs-portal{display:none!important}'; document.documentElement.appendChild(st); };
    if (document.documentElement) hide(); else document.addEventListener('DOMContentLoaded', hide);
  }, { rail, railWidth });
  const page = await ctx.newPage();
  await page.goto(ORIGIN + url, { waitUntil: 'domcontentloaded', timeout: 90000 });
  await page.waitForLoadState('load', { timeout: 90000 }).catch(() => {});
  await page.waitForFunction(() => !document.querySelector('[aria-busy="true"]'), null, { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(3500);
  return { ctx, page };
}
const shot = (page, name) => page.screenshot({ path: path.join(OUT, `${name}.png`) });
const want = (n) => !ONLY.length || ONLY.includes(n);

(async () => {
  const browser = await webkit.launch({ timeout: 60000 });
  log('webkit launched');

  // 1. Real prompts and replies from the Assistant conversation.
  if (want('chat')) {
    const { ctx, page } = await open(browser, `/projects/${P}/research`, { rail: true });
    const list = page.locator('[aria-label="Conversation history"]').first();
    const box = page.getByPlaceholder('Ask a question or plan an experiment…').first();
    const geo = {
      composer: await box.boundingBox(),
      send: await page.getByRole('button', { name: /^Send/ }).first().boundingBox().catch(() => null),
      list: await list.boundingBox(),
    };
    fs.writeFileSync(path.join(OUT, 'chat-geometry.json'), JSON.stringify(geo, null, 1));
    const count = await page.locator('article[data-role="user"]').count();
    log(`${count} user prompts in the conversation`);
    for (let k = 0; k < count; k++) {
      // "before": the conversation up to (not including) prompt k, composer empty.
      await list.evaluate((el, k) => {
        const a = el.querySelectorAll('article[data-role="user"]')[k];
        el.scrollTop = Math.max(0, a.offsetTop - el.offsetTop - el.clientHeight + 4);
      }, k);
      await page.waitForTimeout(500);
      await shot(page, `chat-${k}-before`);
      // "after": prompt k at the top with the agent's reply beneath it.
      await list.evaluate((el, k) => {
        const a = el.querySelectorAll('article[data-role="user"]')[k];
        el.scrollTop = a.offsetTop - el.offsetTop - 12;
      }, k);
      await page.waitForTimeout(500);
      await shot(page, `chat-${k}-after`);
      log(`chat ${k}`);
    }
    await ctx.close();
  }

  // 2. Simple pages.
  const pages = [
    ['studio-inputs', `/projects/${P}/studio?experiment=${EXP}&view=inputs`],
    ['studio-analysis', `/projects/${P}/studio?experiment=${EXP}&view=analysis`],
    ['studio-results', `/projects/${P}/studio?experiment=${EXP}&view=results`],
    ['library-csv', `/projects/${P}/materials?artifact=${CSV}`],
    ['library-literature', `/projects/${P}/materials?view=literature`],
    ['library-measurements', `/projects/${P}/materials?view=measurements`],
    ['library-findings', `/projects/${P}/materials?view=findings`],
    ['paper-home', `/projects/${P_PAPER}`],
    ['reports-library', `/projects/${P}/reports`],
    ['video-inputs', `/projects/${P_VIDEO}/studio?experiment=${EXP_VIDEO}&view=inputs`],
    ['video-plan', `/projects/${P_VIDEO}/studio?experiment=${EXP_VIDEO}&view=plan`],
    ['video-analysis', `/projects/${P_VIDEO}/studio?experiment=${EXP_VIDEO}&view=analysis`],
  ];
  for (const [name, url] of pages) {
    if (!want(name)) continue;
    try {
      const { ctx, page } = await open(browser, url);
      await page.evaluate(() => Promise.all([...document.querySelectorAll('video')].map((v) => new Promise((r) => {
        if (v.readyState >= 2) return r(); v.addEventListener('loadeddata', r, { once: true }); setTimeout(r, 6000);
      })))).catch(() => {});
      await shot(page, name);
      if (name === 'studio-inputs' || name === 'video-inputs') {
        const rec = page.getByRole('tab', { name: 'Record video' }).first();
        if (await rec.count()) { await rec.click(); await page.waitForTimeout(2000); await shot(page, name === 'video-inputs' ? 'video-record' : 'studio-record'); }
      }
      log(name);
      await ctx.close();
    } catch (e) { log(`FAILED ${name}: ${e.message.split('\n')[0]}`); }
  }

  // 3. Terminal panel (opens a temporary terminal session; nothing is typed).
  if (want('terminal')) {
    try {
      const { ctx, page } = await open(browser, `/projects/${P}`);
      await page.getByRole('button', { name: 'Show terminal' }).first().click();
      await page.waitForTimeout(6000);
      await shot(page, 'terminal');
      log('terminal');
      await ctx.close();
    } catch (e) { log(`FAILED terminal: ${e.message.split('\n')[0]}`); }
  }

  await browser.close();
  log(`done -> ${OUT}`);
})().catch((e) => { console.error(e); process.exit(1); });
