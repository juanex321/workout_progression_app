const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
(async () => {
  const input = process.argv[2];
  const url = new URL(input.startsWith('https:') ? input : JSON.parse(fs.readFileSync(input)).url);
  const browser = await chromium.launch({headless:true});
  try {
    const context = await browser.newContext();
    const page = await context.newPage();
    const errors = [], calls = [], blocked = [];
    await page.route('**/api/**', route => {
      if (!['GET','HEAD'].includes(route.request().method())) {
        blocked.push(route.request().method()); return route.abort();
      }
      return route.continue();
    });
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', r => { if(new URL(r.url()).pathname.startsWith('/api/')) calls.push(new URL(r.url()).pathname); });
    url.pathname = '/straight-sets';
    const start = Date.now();
    await page.goto(url.href);
    await page.getByRole('heading', {name:/^Session \d+$/,exact:true}).waitFor({timeout:60000});
    const renderedMs = Date.now()-start;
    await page.waitForLoadState('networkidle');
    assert.deepEqual(calls.filter(p=>p!='/api/health'), ['/api/workout-data']);
    const timings=[]; let data;
    for(let i=0;i<3;i++) {
      const t=Date.now(); const r=await context.request.get(url.origin+'/api/workout-data');
      assert.equal(r.status(),200); data=await r.json(); timings.push(Date.now()-t);
    }
    const baseline=await (await context.request.get('https://workout-progression-app.vercel.app/api/workout-data',{timeout:90000})).json();
    assert.deepEqual(data,baseline);
    await page.getByRole('button',{name:'←',exact:true}).click();
    await page.getByRole('heading',{name:`Session ${data.session_number-1}`,exact:true}).waitFor();
    await page.getByRole('button',{name:'→',exact:true}).click();
    await page.getByRole('heading',{name:`Session ${data.session_number}`,exact:true}).waitFor();
    assert.deepEqual(errors,[]); assert.deepEqual(blocked,[]);
    console.log(JSON.stringify({passed:true,session:data.session_id,renderedMs,apiMs:timings,initialDataRequests:1,matchingLiveData:true,navigation:true,browserErrors:errors,blockedWrites:blocked}));
  } finally { await browser.close(); }
})().catch(e=>{console.error(e.message);process.exitCode=1;});
