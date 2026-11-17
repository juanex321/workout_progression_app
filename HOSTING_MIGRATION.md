# Hosting

Current stack (since 2026-10-16):

| Piece    | Host   | Project / service                          | Deploys                         |
|----------|--------|--------------------------------------------|---------------------------------|
| Frontend | Vercel | `workout-progression-app` (root `frontend`) | Automatically from Git `main`   |
| API      | Vercel | `workout-progression-api-candidate`        | By hand, from a packaged folder |
| Database | Neon   | Production Postgres (plus a test branch)    | n/a                             |

- Live app: https://workout-progression-app.vercel.app
- Live API: https://workout-progression-api-candidate.vercel.app (the project
  kept its original "candidate" name; renaming it would change this alias)

History: Railway → Neon + Render + Vercel, then the API moved from Render to
Vercel on 2026-10-16 to remove Render free-tier cold starts (~30 s+). The
measurements and rollout record are in `PERFORMANCE_ROLLOUT.md`. Render has
been retired.

---

## Frontend (Vercel, Git-connected)

- Root directory: `frontend`, framework preset Next.js.
- `frontend/next.config.js` rewrites `/api/**` to `BACKEND_URL`. Rewrites are
  compiled at build time, so changing `BACKEND_URL` needs a rebuild.
- `BACKEND_URL`:
  - Production: `https://workout-progression-api-candidate.vercel.app`
  - Preview / Development: still the old Render URL. Point it somewhere
    else before relying on frontend previews.
- Every push to `main` deploys the frontend. API changes are **not**
  deployed by that push; see below.

## API (Vercel, deployed by hand)

The API project is not connected to Git. When a PR changes `api/`,
`progression.py` or `plan.py`, repackage and deploy it separately.
Otherwise the live frontend runs against an older API.

1. From an up-to-date `main`:
   ```bash
   python scripts/package_vercel_api.py
   ```
   This builds `.vercel-api-candidate/`, an allowlisted folder (API source,
   `plan.py`, `progression.py`, requirements, FastAPI entrypoint, `iad1` Fluid
   config) with no databases or secrets. The script refuses to run if the
   folder already exists; delete the old folder first.
2. Deploy that folder to the `workout-progression-api-candidate` project:
   ```bash
   cd .vercel-api-candidate
   npx vercel link --yes --project workout-progression-api-candidate
   npx vercel deploy --prod
   ```
3. Verify with read-only checks: `/api/health` (liveness only, no DB) and a
   full `GET /api/workout-data`, which reads the database. Optionally run
   `node scripts/check_production_readonly.cjs https://workout-progression-app.vercel.app`
   with `PLAYWRIGHT_MODULE` pointing at a Playwright install.
4. Rollback: promote the previous production deployment of the API project
   in the Vercel dashboard.

### API environment variables

| Key            | Production                         | Preview                  |
|----------------|------------------------------------|--------------------------|
| `DATABASE_URL` | Neon production (sensitive)        | **not set**              |
| `SKIP_DB_INIT` | `true`                             | `true`                   |

Preview has no `DATABASE_URL`. Before testing a preview build, add the Neon
**test-branch** connection string as a Preview secret. Never point a preview
at production data.

### Schema changes

- `SKIP_DB_INIT=true` skips `create_all`, index creation and seeding on
  startup. `ensure_schema_columns()` (in `api/db.py`) still runs and adds any
  new nullable columns the ORM expects, e.g. `feedback.recovery_days`.
- Anything beyond adding a nullable column needs an Alembic migration
  (`alembic/versions/`), run against the target database before the API
  deploy that depends on it.
- `python -m api.bootstrap` initializes a fresh database (tables, indexes,
  seed data). Run it before enabling `SKIP_DB_INIT` on a new database.

## Database (Neon)

- Production and a test branch live in the same Neon project. Write tests go
  to the test branch only.
- The API forces the `pg8000` driver on Vercel and translates `sslmode` into
  a verified TLS context (`api/db.py`).

---

## Troubleshooting

**"Failed to load current session"**
Check the API project's Production `DATABASE_URL` and the frontend's
Production `BACKEND_URL` (no trailing slash). Then check the API's runtime
logs in Vercel.

**A feature works locally but not in production**
The API was probably not redeployed after the PR merged. Compare the API
project's latest production deployment date with the merge date.

**Slow first request**
An idle Neon compute plus a cold Vercel function takes about 1–3 s. Later
requests take about 0.3–0.5 s.
