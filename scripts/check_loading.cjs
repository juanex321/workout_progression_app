// Run against serve_test_api.py and a production frontend on localhost:3100.
// Requires Playwright; PLAYWRIGHT_MODULE can point to an existing installation.
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    let context = await browser.newContext();
    let page = await context.newPage();
    const errors = [];
    const requests = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (request.url().includes('/api/')) requests.push(new URL(request.url()).pathname + new URL(request.url()).search);
    });
    await page.goto('http://localhost:3100/straight-sets');
    await page.getByRole('heading', { name: 'Session 3', exact: true }).waitFor();
    await page.waitForLoadState('networkidle');
    assert.deepEqual(requests.filter(url => url !== '/api/health'), ['/api/workout-data']);
    console.log('PASS: initial workout loads with one data request');

    const recoverySaved = page.waitForResponse(r => r.url().endsWith('/api/feedback/soreness') && r.request().method() === 'POST');
    await page.getByRole('button', { name: 'Healed right on time', exact: true }).first().click();
    assert.equal((await recoverySaved).status(), 200);
    const draftSaved = page.waitForResponse(r => r.url().endsWith('/api/sets/draft') && r.request().method() === 'POST');
    await page.locator('input').first().fill('77.5');
    await page.locator('input').first().blur();
    assert.equal((await draftSaved).status(), 200);

    // A new browser context has no localStorage: the draft must come from the API.
    await context.close();
    context = await browser.newContext();
    page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('http://localhost:3100/straight-sets');
    await page.getByRole('heading', { name: 'Session 3', exact: true }).waitFor();
    assert.equal(await page.locator('input').first().inputValue(), '77.5');
    const setSaved = page.waitForResponse(r => r.url().endsWith('/api/sets/save') && r.request().method() === 'POST');
    await page.getByRole('button', { name: 'Log Set, set 1', exact: true }).first().click();
    assert.equal((await setSaved).status(), 200);
    await page.getByRole('button', { name: 'Done, set 1', exact: true }).first().waitFor();
    const data = await (await page.request.get('http://localhost:3100/api/workout-data')).json();
    assert.equal(Object.values(data.muscle_groups)[0].exercises[0].existing_sets[0].weight, 77.5);
    console.log('PASS: recovery, server draft restore, and set saving');

    // Populate feedback in the disposable API to exercise the finish/cache transition.
    for (const muscleGroup of Object.keys(data.muscle_groups)) {
      const response = await page.request.post('http://localhost:3100/api/feedback/muscle-group', {
        data: { session_id: data.session_id, muscle_group: muscleGroup, soreness: 3, pump: 3, workload: 3 },
      });
      assert.equal(response.status(), 200);
    }
    await page.reload();
    await page.getByRole('button', { name: 'Finish Session', exact: true }).click();
    await page.getByRole('heading', { name: 'Session 4', exact: true }).waitFor();
    await page.getByRole('button', { name: '←', exact: true }).click();
    await page.getByRole('heading', { name: 'Session 3', exact: true }).waitFor();
    await page.getByText('Completed', { exact: true }).waitFor();
    await page.getByRole('button', { name: '→', exact: true }).click();
    await page.getByRole('heading', { name: 'Session 4', exact: true }).waitFor();
    assert.deepEqual(errors, []);
    console.log('PASS: completion, backward/forward navigation, no browser exceptions');
    await context.close();
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
