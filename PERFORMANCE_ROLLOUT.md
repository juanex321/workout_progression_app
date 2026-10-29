# Loading improvements and staged backend migration

The frontend now bootstraps from `/api/workout-data` and fills the existing
session-specific React Query cache. Progression formulas and mutation payloads
are unchanged. History queries select recent session IDs in SQL before loading
sets, retaining complete sets for each selected session.

## Verification

- Production Next.js build, ESLint and TypeScript checks.
- Existing progression tests and history-summary tests.
- Full response equivalence test against the old history queries: 60 completed
  sessions, 360 versus 3 loaded Set ORM objects, identical workout JSON.
- Browser checks against disposable SQLite: one initial data request, recovery
  saving, draft restoration without localStorage, set saving, completion, and
  previous/next navigation.

Run Python test modules in separate processes when mixing root-model tests with
API-model tests: both stacks use bare `db`/`services` imports.

```powershell
python -m pytest test_mev_progression.py test_set_progression.py -q
python -m pytest test_exercise_history_summary.py test_api_startup.py -q
cd frontend
npm run lint
npx tsc --noEmit
npm run build
```

For browser verification, install Playwright in your test environment, run
`python scripts/serve_test_api.py` and `npm run start -- --port 3100` in separate
terminals, then `node scripts/check_loading.cjs` from the repository root.
The fixture server always overrides DATABASE_URL with a disposable SQLite file.
Restart it for each test run. PLAYWRIGHT_MODULE optionally selects an existing
Playwright installation. The frontend must be built with the default local API.

## Candidate deployment

Keep the existing frontend project and Render service in place. The separate
Vercel project is `workout-progression-api-candidate`, on the existing team.

1. Configure a Neon test branch connection string as a Preview DATABASE_URL
   secret on the candidate project. Never use production data for write tests.
2. Run `python scripts/package_vercel_api.py` to create an allowlisted deployment
   directory `.vercel-api-candidate`. It contains API source, shared progression
   modules, API dependencies, a FastAPI entrypoint, and an iad1 Fluid config.
   It excludes local databases, backups, frontend files, and environment secrets.
   Packaging refuses to overlay an existing directory to prevent stale files.
3. Deploy that directory to the candidate project as a preview. Default startup
   initialization remains enabled so a fresh test database can initialize.
4. After initialization succeeds, set Preview SKIP_DB_INIT=true and redeploy.
   Alternatively initialize the test database explicitly with
   `python -m api.bootstrap` before the first deployment with SKIP_DB_INIT=true.
   Bootstrap creates missing tables/indexes and seeds defaults; it does not
   replace Alembic migrations for changing existing schemas.
5. Test the candidate API and a frontend preview pointing at it. Verify response
   parity, drafts, sets, soreness, feedback, completion, and navigation.
6. Measure full workout readiness, not only `/api/health`. Health is liveness;
   it does not query Neon. Compare cold and warm runs, including after Neon
   suspension, with equivalent data. Reject the migration if warm latency or
   correctness regresses. A local SQLite benchmark does not establish hosted
   PostgreSQL or serverless latency.

Only after those checks should production DATABASE_URL and BACKEND_URL be
changed. Preserve the old Render URL and previous frontend deployment for
rollback. Reverting BACKEND_URL requires a frontend rebuild because rewrites
are generated during the Next.js build. Leave Render available until the new
backend has passed production verification. Do not enable SKIP_DB_INIT on an
unprepared production database.

The browser keep-alive and existing retry policy are deliberately unchanged in
this pass. They do not remove Render idle sleep; the backend hosting switch is
still required to address that dominant delay.

## Hosted verification — 2026-10-16

Candidate project: `prj_iRtukMR5vyxe5q6Z538egTXIj5Ur` on team
`team_64sZZcy7XGfEen3HqZbMHT08`.
Verified deployment: `dpl_B7PebPFvJikK9jhVER4mhzPQHbCn` (staging/Preview),
`https://workout-progression-api-candidate-h5gqest01-juanex321s-projects.vercel.app`.
Preview DATABASE_URL points at the user-configured Neon test branch. Initialization
succeeded before Preview SKIP_DB_INIT=true was enabled and deployed.

Full `/api/workout-data` response, measured from the same client:

| Measurement | Existing app (Render API through Vercel) | Candidate API |
| --- | --- | --- |
| First request | 34,090 ms | 1,189 ms |
| Subsequent five requests | 2,598 / 2,595 / 2,518 / 2,698 / 2,606 ms | 394 / 386 / 359 / 396 / 381 ms |
| Warm median | 2,598 ms | 386 ms |

Before any test writes, both deployments returned identical JSON for session 65
with six exercises. This controls for payload differences, but the test and
production databases are separate computes. The candidate measurement is direct
to the API and includes preview authentication on the first request; the existing
app includes its Vercel-to-Render rewrite. These are API-response timings, not
browser rendering timings, and not a statistical latency guarantee.

Hosted test-branch writes passed: draft save/reload, soreness, idempotent repeated
set saves, all muscle feedback, completion to the next session, and previous
session history. The test branch was intentionally modified by these checks;
production data was not. The candidate runtime error-log query returned no errors.

After six minutes with no candidate API/health requests, the full workout response
took 2,422 ms, followed by 352 ms and 399 ms. All returned HTTP 200. This is an
observed idle-wake measurement; Neon suspension and Vercel instance eviction were
not independently confirmed. It does not guarantee every future cold start.

The transient authenticated access-link files were removed after verification.
Generate a new protected-deployment access link and save it in the ignored
`.test-artifacts/candidate-access-v2.json` before rerunning hosted scripts.

## Production rollout completed — 2026-10-16

Live frontend: https://workout-progression-app.vercel.app

- Frontend deployment: `dpl_2MSy8jEmwu3nb8nD1MziLcApqB4S`.
- Backend deployment: `dpl_Exiy1UkxyFYQEUmGGj42xAj5uiNB`.
- Backend production alias: https://workout-progression-api-candidate.vercel.app
  (the project retains its original candidate name).
- Production BACKEND_URL now points to that API. Development/Preview retain
  their previous Render setting. Existing NEXT_PUBLIC_API_URL is overridden by
  BACKEND_URL in the frontend rewrite configuration.
- The backend uses the existing production Neon database; no database copy or
  production initialization was performed. Full production workout reads proved
  schema compatibility before Production SKIP_DB_INIT=true was enabled.
- The user saved production DATABASE_URL over the Preview entry. That entry was
  moved to Production without reading its secret. Backend Preview now has no
  DATABASE_URL: re-add a separate test-branch secret before future preview builds.
  The previously tested immutable preview deployment still has its test secret.
- Automatic domain assignment was disabled for staging, then restored on both
  projects after promotion.

The staged frontend returned JSON identical to the old live application, rendered
in 1,202 ms, and returned subsequent full workout reads in 558/318/296 ms. The old
Render comparison initially exceeded a 30-second timeout; a retry with a longer
timeout succeeded. After promotion, a fresh live browser context rendered in
1,241 ms, with subsequent API reads of 438/271/423 ms. These are small observed
samples, not guaranteed latency or a confirmed cold-start measurement.

Both staged and live browser checks confirmed one initial workout-data request,
backward/forward session navigation, and no browser exceptions. Production checks
were read-only; the browser harness blocks non-GET/HEAD API requests and observed
none. Backend and frontend error-log queries for the final 10-minute verification
window returned no entries. Write flows were tested on the separate test branch
as documented above, not on production.

### Rollback and source continuity

Render remains available. Promote frontend deployment
`dpl_6N6BbuKntnPgkRJWgsTuJVG4rR6N` to restore its compiled Render rewrite immediately.
That rollback does not require changing database contents. To keep subsequent
builds on Render, also restore the prior BACKEND_URL configuration before building;
an environment edit alone does not change already-built rewrites.

The deployments were uploaded from this tested workspace. Source changes remain
uncommitted locally: commit/review them before the next Git-driven frontend deploy,
otherwise it can replace the frontend optimizations with the older Git version.
The API was deployed from the allowlisted package generated by
`scripts/package_vercel_api.py`; it is not connected to an automatic Git build.
Repackage and redeploy API changes separately. Never promote the old test-database
deployment into production.

Read-only browser verification can be repeated with
`node scripts/check_production_readonly.cjs https://workout-progression-app.vercel.app`
and PLAYWRIGHT_MODULE pointing to an installed Playwright package. Protected
deployment access-link files are temporary and must not be committed.
