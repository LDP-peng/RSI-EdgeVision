
import { createRequire } from 'node:module';
const require = createRequire('C:/Users/LDP/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/');
const { chromium } = require('playwright');
const dir = 'C:/Users/LDP/.codex/visualizations/2026/09/06/01a0758b-ebc1-77d1-a732-d983745cd83f';
const browser = await chromium.launch({
  executablePath: 'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  headless: true,
  args: ['--no-sandbox','--disable-gpu','--force-device-scale-factor=2']
});
const page = await browser.newPage({ viewport: { width: 842, height: 1200 }, deviceScaleFactor: 2 });
await page.goto('file:///' + dir + '/cover.html');
await page.waitForTimeout(2000);
for (const id of ['a','b']) {
  const el = await page.$('#' + id);
  await el.screenshot({ path: dir + '/cover_' + id + '.png' });
  console.log('shot ' + id);
}
await browser.close();
