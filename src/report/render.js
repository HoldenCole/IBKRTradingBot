// Render an HTML file to a Letter PDF with headless Chromium.
// Prints one line per page whose content runs past the sheet, so a build can fail loudly instead of clipping.
const { chromium } = require('playwright');
(async () => {
  const [html, pdf] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + html, { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  const over = await page.evaluate(() => [...document.querySelectorAll('.page')].map((p, i) => {
    const pr = p.getBoundingClientRect();
    const foot = p.querySelector('.rf').getBoundingClientRect();
    const wide = [...p.querySelectorAll('table, .fig, .tfh')].some(el => el.getBoundingClientRect().right > pr.right - 40);
    return { page: i + 1, px: Math.round(foot.bottom - (pr.bottom - 37)), wide };
  }).filter(o => o.px > 1 || o.wide));
  for (const o of over) console.log(`OVERFLOW page ${o.page}: ${o.px}px past the bottom margin${o.wide ? ', content too wide' : ''}`);
  await page.pdf({ path: pdf, format: 'Letter', printBackground: true, preferCSSPageSize: true,
                   margin: { top: '0', right: '0', bottom: '0', left: '0' } });
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
