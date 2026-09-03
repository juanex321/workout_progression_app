# Workout Progression App

A smart workout tracking app that automatically adjusts your training volume and intensity based on how your muscles respond to each session.

## How It Works

### The Progression System

This app implements **feedback-driven progressive overload** - instead of following a fixed program, it adapts to YOUR body's response:

```
Log Sets -> Submit Feedback -> App Adjusts Next Session
```

1. **You train** - Log weight, reps for each set
2. **You rate the session** - After finishing all exercises for a muscle group, rate:
   - **Soreness** (1-4): How sore/fatigued does the muscle feel?
   - **Pump** (1-4): How good was the pump?
   - **Workload** (1-4): Was it too easy, just right, or too much?
3. **App adapts** - Next session automatically adjusts:
   - **Sets** (primary): Increase if under-stimulated, decrease if overtrained
   - **Reps** (secondary): Increase by 1 if hitting all targets (up to 15)

Every set is trained to failure - there's no RIR/reps-in-reserve target and no
automatic deload. The feedback-driven +/-1 set adjustment is the only backoff
mechanism for overtraining.

### Progression Rules

| Feedback Pattern | Action |
|------------------|--------|
| Low soreness + Low pump + Low workload | +1 set (no upper cap) |
| High soreness OR High workload | -1 set (down to the muscle's minimum) |
| First set hits target reps | +1 rep (up to 15) |

**Weights stay the same** - you manually increase weight when you're ready. The app never auto-increases weight.

### Exercise Rotation

The app rotates through exercises automatically:

- **Hamstrings**: Romanian deadlifts (50 lb starting weight) on push/chest days; leg curls on pull/back days
- **Upper**: Push day (Chest/Triceps) alternates with Pull day (Back/Biceps)
- **Every session**: Lateral raises for shoulders

## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | Next.js 16 |
| API | FastAPI (Python) |
| Database (Cloud) | PostgreSQL (Neon) |
| Database (Local) | SQLite |
| ORM | SQLAlchemy 2.0 |
| Python | 3.10+ |

## Project Structure

```
workout_progression_app/
├── api/                   # FastAPI app
│   ├── index.py           # App entry point (port 8000)
│   ├── db.py              # API DB config & models
│   ├── services.py        # CRUD operations
│   ├── schemas.py         # Pydantic request/response models
│   ├── deps.py            # FastAPI DB dependency
│   └── routes/            # sessions, exercises, feedback, progression
├── frontend/              # Next.js app (port 3000)
│   └── src/
├── db.py                  # SQLAlchemy models (used by scripts/tests)
├── services.py            # Legacy root service layer
├── progression.py         # Volume & rep progression logic
├── plan.py                # Exercise rotation configuration
├── init_db.py             # Database seeding script
└── scripts/               # One-off maintenance scripts
```

## Database Schema

```
Program (1) ─── (*) Workout (1) ─── (*) WorkoutExercise ─── Exercise
                        │                    │
                        │                    │
                   Session (1) ───────── (*) Set
                        │
                        └─── (*) Feedback (per muscle group)
```

### Key Models

- **Session**: A single workout instance with `rotation_index` to track exercise rotation
- **Set**: Logged set with `weight`, `reps`, `logged_at`
- **Feedback**: Per muscle group with `soreness`, `pump`, `workload` (1-4 scale)

## Quick Start

### Local Development

```bash
# Clone and install Python deps
git clone <repo-url>
cd workout_progression_app
pip install -r api/requirements.txt

# Install frontend deps
cd frontend && npm install && cd ..

# Initialize database
python init_db.py

# Start API (port 8000)
cd api && uvicorn index:app --reload

# Start frontend (port 3000, separate terminal)
cd frontend && npm run dev
```

Copy `frontend/.env.example` to `frontend/.env.local` and set `BACKEND_URL` if your API runs somewhere other than `http://localhost:8000`.

SQLite database (`workout.db`) is created automatically for local dev.

### Deploy to Railway

1. **Get a PostgreSQL database** from [Neon.tech](https://neon.tech) (free tier)

2. **Set environment variables** in Railway:
   ```
   DATABASE_URL=postgresql://user:password@ep-xxx.region.aws.neon.tech/neondb?sslmode=require
   ```

3. **Deploy** - Railway uses `railway.json` at the repo root automatically.

## Configuration

Edit `plan.py` to customize:

```python
# Hamstring exercise by upper-body focus
HAMSTRING_PUSH_EXERCISE = "Romanian Deadlift"
HAMSTRING_PULL_EXERCISE = "Leg Curl"

# Default targets
DEFAULT_TARGET_SETS = 4
DEFAULT_TARGET_REPS = 10
```

## License

MIT License


