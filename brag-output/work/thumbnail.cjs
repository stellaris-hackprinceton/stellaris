// Renders the 3:2 Devpost thumbnail (3000x2000) with the isolated Playwright WebKit under /tmp.
process.env.PLAYWRIGHT_BROWSERS_PATH ||= '/tmp/stellaris-webtest/browsers';
const { webkit } = require('/tmp/stellaris-webtest/node_modules/playwright');
const path = require('path');
(async () => {
  const browser = await webkit.launch({ timeout: 60000 });
  const page = await (await browser.newContext({ viewport: { width: 1500, height: 1000 }, deviceScaleFactor: 2 })).newPage();
  await page.goto('file://' + path.resolve(__dirname, '../composition2/thumbnail.html'), { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(500);
  const out = path.resolve(__dirname, '../devpost-thumbnail.png');
  await page.screenshot({ path: out });
  await browser.close();
  console.log('saved ' + out);
})().catch((e) => { console.error(e); process.exit(1); });
