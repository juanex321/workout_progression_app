// Auth link lives only in an ignored local file. No credentials are logged.
const fs = require('node:fs');
const assert = require('node:assert/strict');
const { request } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const { url } = JSON.parse(fs.readFileSync('.test-artifacts/candidate-access-v2.json', 'utf8'));
  const candidate = new URL(url);
  assert(candidate.hostname.startsWith('workout-progression-api-candidate-'));
  const client = await request.newContext({ timeout: 90000 });
  const measurements = {};
  try {
    for (const [name, origin] of [['candidate', candidate.origin], ['existing', 'https://workout-progression-app.vercel.app']]) {
      const samples = [];
      let payload;
      for (let i = 0; i < 6; i++) {
        const target = new URL('/api/workout-data', origin);
        if (name === 'candidate' && i === 0) target.search = candidate.search;
        const start = performance.now();
        const response = await client.get(target.href);
        const body = await response.text();
        const elapsed = performance.now() - start;
        assert.equal(response.status(), 200, `${name}: HTTP ${response.status()}`);
        assert(response.headers()['content-type']?.includes('application/json'), `${name}: not JSON`);
        payload = JSON.parse(body);
        assert(payload.muscle_groups, `${name}: no workout data`);
        samples.push(Math.round(elapsed));
      }
      measurements[name] = { milliseconds: samples, session: payload.session_number,
        exercises: Object.values(payload.muscle_groups).reduce((sum, g) => sum + g.exercises.length, 0) };
      fs.writeFileSync(`.test-artifacts/${name}-workout.json`, JSON.stringify(payload));
      console.log(name, JSON.stringify(measurements[name]));
    }
    const first = JSON.parse(fs.readFileSync('.test-artifacts/candidate-workout.json'));
    const second = JSON.parse(fs.readFileSync('.test-artifacts/existing-workout.json'));
    try { assert.deepEqual(first, second); console.log('PASS: candidate and existing workout JSON are identical'); }
    catch { console.log('NOTE: datasets differ; timings are not an equivalent-data comparison'); }
    fs.writeFileSync('.test-artifacts/benchmark.json', JSON.stringify(measurements, null, 2));
  } finally { await client.dispose(); }
})().catch(error => { console.error(error.message.replace(/https?:\/\/\S+/g, '[URL]')); process.exitCode = 1; });
