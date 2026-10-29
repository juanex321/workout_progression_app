const fs = require('node:fs');
const assert = require('node:assert/strict');
const { request } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const last = JSON.parse(fs.readFileSync('.test-artifacts/last-candidate-request.json', 'utf8')).time;
  const deadline = last + 6 * 60 * 1000;
  console.log('Waiting until six minutes after the last test-database request; no keep-alive traffic.');
  while (Date.now() < deadline) await new Promise(resolve => setTimeout(resolve, Math.min(30000, deadline - Date.now())));
  const { url } = JSON.parse(fs.readFileSync('.test-artifacts/candidate-access-v2.json', 'utf8'));
  const access = new URL(url);
  const client = await request.newContext({ timeout: 90000 });
  const timings = [];
  try {
    for (let i = 0; i < 3; i++) {
      const target = new URL('/api/workout-data', access.origin);
      if (i === 0) target.search = access.search;
      const start = performance.now();
      const response = await client.get(target.href);
      assert.equal(response.status(), 200);
      const payload = await response.json();
      assert(payload.muscle_groups);
      timings.push(Math.round(performance.now() - start));
    }
    fs.writeFileSync('.test-artifacts/idle-benchmark.json', JSON.stringify({ idleMinutes: 6, milliseconds: timings }, null, 2));
    console.log('After six minutes idle:', JSON.stringify(timings), 'ms; all responses HTTP 200');
  } finally { await client.dispose(); }
})().catch(error => { console.error(error.message.replace(/https?:\/\/\S+/g, '[URL]')); process.exitCode = 1; });
