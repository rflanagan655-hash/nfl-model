// Load a standalone page (index.html built by build_site.py) in headless Chromium and print the JSON value of an expression.
// Usage: NODE_PATH=$(npm root -g) node tools/page_eval.js <index.html> "<js expression>"
const { chromium } = require('playwright');
(async () => {
  const [file, expr] = process.argv.slice(2);
  const b = await chromium.launch(); const p = await b.newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file://' + require('path').resolve(file)); await p.waitForTimeout(2500);
  if (errs.length) { console.error('PAGE ERRORS: ' + errs.join(' | ')); }
  const v = await p.evaluate(expr); process.stdout.write(JSON.stringify(v)); await b.close();
})();
