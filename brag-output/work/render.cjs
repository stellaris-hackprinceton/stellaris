// Renders the Stellaris brag composition frame by frame with the isolated Playwright WebKit under /tmp.
//   node brag-output/work/render.cjs stills   -> brag-output/work/stills/*.jpg + overflow report (fast check)
//   node brag-output/work/render.cjs full     -> brag-output/work/frames/%05d.jpg (30fps, 4 parallel pages)
process.env.PLAYWRIGHT_BROWSERS_PATH ||= '/tmp/stellaris-webtest/browsers';
const { webkit } = require('/tmp/stellaris-webtest/node_modules/playwright');
const fs = require('fs');
const path = require('path');

const mode = process.argv[2] || 'stills';
const FPS = 30;
const page_url = 'file://' + path.resolve(__dirname, '..', process.env.COMP || 'composition2', 'index.html');
const STILLS = [5.5, 12.0, 14.0, 15.4, 17.5, 19.6, 24.0, 27.5, 31.5, 34.8, 38.5, 41.5, 44.6, 48.5, 51.5, 55.5, 59.5, 62.5, 65.5, 69.2, 71.0, 75.5, 79.5, 82.0, 85.2, 88.5, 93.5, 98.5, 102.8, 106.5, 113.5];
const t0 = Date.now();
const log = (m) => console.log(`${((Date.now() - t0) / 1000).toFixed(1)}s ${m}`);

async function open(browser) {
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => console.log('PAGE ERROR:', e.message));
  page.on('console', (m) => { if (m.type() === 'error') console.log('CONSOLE ERROR:', m.text()); });
  await page.goto(page_url, { waitUntil: 'load' });
  await page.evaluate(() => window.ready);
  await page.evaluate(() => window.warmup());
  await page.waitForTimeout(800);
  return page;
}

(async () => {
  const browser = await webkit.launch({ timeout: 60000 });
  if (mode === 'stills') {
    const dir = path.join(__dirname, 'stills'); fs.mkdirSync(dir, { recursive: true });
    const page = await open(browser);
    const problems = [];
    for (const t of STILLS) {
      await page.evaluate((x) => { window.renderFrame(x); return new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))); }, t);
      await page.screenshot({ path: path.join(dir, `t${t.toFixed(1).padStart(5, '0')}.jpg`), type: 'jpeg', quality: 85 });
      const over = await page.evaluate(() => window.checkOverflow());
      if (over.length) problems.push({ t, over });
    }
    fs.writeFileSync(path.join(dir, 'overflow.json'), JSON.stringify(problems, null, 1));
    log(`${STILLS.length} stills, ${problems.length} frames with overflow -> ${dir}`);
  } else {
    const dir = path.join(__dirname, 'frames'); fs.mkdirSync(dir, { recursive: true });
    const duration = await (await open(browser)).evaluate(() => window.DURATION);
    const total = Math.round(duration * FPS);
    // Optional FROM/TO (seconds) re-render only part of the video, overwriting those frames.
    const first = process.env.FROM ? Math.floor(Number(process.env.FROM) * FPS) : 0;
    const last = process.env.TO ? Math.min(total, Math.ceil(Number(process.env.TO) * FPS) + 1) : total;
    const workers = 4;
    let done = 0;
    await Promise.all([...Array(workers)].map(async (_, w) => {
      const page = await open(browser);
      for (let f = first + w; f < last; f += workers) {
        await page.evaluate((x) => { window.renderFrame(x); return new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))); }, f / FPS);
        await page.screenshot({ path: path.join(dir, `${String(f).padStart(5, '0')}.jpg`), type: 'jpeg', quality: 92 });
        if (++done % 300 === 0) log(`${done}/${total} frames`);
      }
    }));
    log(`done: frames ${first}-${last - 1} of ${total} -> ${dir}`);
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
