# Hosting Migration: Railway → Free Stack (Neon + Render + Vercel)

## Overview

| Service       | Old (Railway)     | New (Free)                  |
|---------------|-------------------|-----------------------------|
| Database      | Railway Postgres  | Neon Postgres (free tier)   |
| API Backend   | Railway           | Render (free tier)          |
| Frontend      | Local / manual    | Vercel (free tier)          |

Total cost: **$0/month**

---

## Step 1: Set Up Neon Database

1. Go to [neon.tech](https://neon.tech) and sign up (GitHub login works)
2. Create a new project (any name, e.g., "workout-progression")
3. Pick the **region closest to you**
4. Copy the **connection string** — it looks like:
   ```
   postgresql://username:password@ep-cool-name-123456.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
5. Save this — you'll need it for Render

### Migrate Existing Data (Optional)

If you have workout data in Railway's Postgres you want to keep:

```bash
# Export from Railway (run while Railway is still active)
pg_dump "YOUR_RAILWAY_DATABASE_URL" --no-owner --no-acl > backup.sql

# Import to Neon
psql "YOUR_NEON_CONNECTION_STRING" < backup.sql
```

If Railway is already down, the app will auto-seed default exercise data on first
boot — you'll just lose past session history.

---

## Step 2: Deploy API to Render

1. Go to [render.com](https://render.com) and sign up (GitHub login works)
2. Click **New → Web Service**
3. Connect your GitHub repo
4. Configure:
   - **Name**: `workout-progression-api`
   - **Root Directory**: leave empty (uses repo root)
   - **Runtime**: Python
   - **Build Command**: `pip install --upgrade pip && pip install -r api/requirements.txt`
   - **Start Command**: `python -m uvicorn api.index:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: **Free**
5. Add environment variable:
   - `DATABASE_URL` = your Neon connection string from Step 1
6. Click **Deploy**
7. Note your Render URL (e.g., `https://workout-progression-api.onrender.com`)
8. Verify: visit `https://YOUR-RENDER-URL/api/health`

### Note on Cold Starts

Render free tier spins down after 15 min of inactivity. First request after idle
takes ~30-60 seconds. The API and frontend both have retry logic to handle this
gracefully — no data loss will occur.

---

## Step 3: Deploy Frontend to Vercel

1. Go to [vercel.com](https://vercel.com) and sign up (GitHub login works)
2. Click **Add New → Project**
3. Import your GitHub repo
4. Configure:
   - **Framework Preset**: Next.js (auto-detected)
   - **Root Directory**: `frontend`
5. Add environment variable:
   - `BACKEND_URL` = your Render API URL from Step 2 (e.g., `https://workout-progression-api.onrender.com`)
6. Click **Deploy**
7. Your app is now live at the Vercel URL!

---

## Step 4: Clean Up Railway

Once everything works on the new stack:

1. Go to your Railway dashboard
2. Delete the project to stop any billing

---

## Troubleshooting

**App shows loading spinner for a long time on first visit**
Normal — Render free tier is waking up (~30-60s). Subsequent requests are fast.

**"Failed to load current session" error**
Check that `BACKEND_URL` is set correctly in Vercel (no trailing slash).
Check that `DATABASE_URL` is set correctly in Render.

**Data is empty after migration**
If you didn't export/import data, the app auto-seeds exercises on first boot.
Create a new session to start fresh.
