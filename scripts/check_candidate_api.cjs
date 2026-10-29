const fs = require('node:fs');
const assert = require('node:assert/strict');
const { request } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const { url } = JSON.parse(fs.readFileSync('.test-artifacts/candidate-access-v2.json', 'utf8'));
  const access = new URL(url);
  assert(access.hostname.startsWith('workout-progression-api-candidate-'));
  const client = await request.newContext({ timeout: 60000 });
  const endpoint = path => new URL(path, access.origin).href;
  const json = async response => { assert.equal(response.status(), 200); return response.json(); };
  try {
    const auth = new URL('/api/health', access.origin);
    auth.search = access.search;
    const health = await json(await client.get(auth.href));
    // Pin the user-provided test branch observed during verification.
    assert(health.database.target.includes('ep-billowing-leaf-ah13xc14-pooler'));
    const initial = await json(await client.get(endpoint('/api/workout-data')));
    const [group, muscle] = Object.entries(initial.muscle_groups)[0];
    const exercise = muscle.exercises[0];
    const draft = [{ set_number: 1, weight: 77.5, reps: 11 }];
    await json(await client.post(endpoint('/api/sets/draft'), { data: {
      session_id: initial.session_id, workout_exercise_id: exercise.we_id, rows: draft,
    }}));
    let reloaded = await json(await client.get(endpoint('/api/workout-data')));
    assert.deepEqual(reloaded.muscle_groups[group].exercises[0].draft, draft);
    await json(await client.post(endpoint('/api/feedback/soreness'), { data: {
      session_id: initial.session_id, muscle_group: group, soreness: 3,
    }}));
    const logged = { session_id: initial.session_id, workout_exercise_id: exercise.we_id,
      rows: [{ ...draft[0], done: true }] };
    for (let i = 0; i < 2; i++) await json(await client.post(endpoint('/api/sets/save'), { data: logged }));
    reloaded = await json(await client.get(endpoint('/api/workout-data')));
    const sets = reloaded.muscle_groups[group].exercises[0].existing_sets.filter(s => s.set_number === 1);
    assert.equal(sets.length, 1);
    assert.equal(sets[0].weight, 77.5);
    assert.equal(sets[0].reps, 11);
    for (const name of Object.keys(initial.muscle_groups)) {
      await json(await client.post(endpoint('/api/feedback/muscle-group'), { data: {
        session_id: initial.session_id, muscle_group: name, soreness: 3, pump: 3, workload: 3,
      }}));
    }
    const next = await json(await client.post(endpoint(`/api/sessions/${initial.session_id}/complete`)));
    assert.equal(next.session_number, initial.session_number + 1);
    const current = await json(await client.get(endpoint('/api/workout-data')));
    assert.equal(current.session_id, next.session_id);
    const previous = await json(await client.get(endpoint(`/api/workout-data?session_number=${initial.session_number}`)));
    assert.equal(previous.completed, 1);
    assert.equal(previous.muscle_groups[group].exercises[0].existing_sets.find(s => s.set_number === 1).weight, 77.5);
    console.log('PASS: hosted test database drafts, soreness, idempotent set save, feedback, completion, and history');
    fs.writeFileSync('.test-artifacts/last-candidate-request.json', JSON.stringify({ time: Date.now() }));
  } finally { await client.dispose(); }
})().catch(error => { console.error(error.message.replace(/https?:\/\/\S+/g, '[URL]')); process.exitCode = 1; });
