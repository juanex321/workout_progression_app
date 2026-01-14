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
   - **Soreness** (1-5): How sore/fatigued does the muscle feel?
   - **Pump** (1-5): How good was the pump?
   - **Workload** (1-5): Was it too easy, just right, or too much?
3. **App adapts** - Next session automatically adjusts:
   - **Sets** (primary): Increase if under-stimulated, decrease if overtrained
   - **Reps** (secondary): Increase by 1 if hitting all targets (up to 15)
   - **RIR** (intensity): Suggests how many reps to leave in reserve

### Progression Rules

| Feedback Pattern | Action |
|------------------|--------|
| Low soreness + Low pump + Low workload | +1 set (up to max) |
| High soreness OR High workload | -1 set (down to 1) |
| All sets hit target reps | +1 rep (up to 15) |
| 2+ sessions with workload=5 | Trigger deload (55% weight) |

**Weights stay the same** - you manually increase weight when you're ready. The app never auto-increases weight.

### Exercise Rotation

The app rotates through exercises automatically:

- **Legs**: Leg Extension -> Leg Curl -> Hip Thrust + Glute Lunges (3-day rotation)
- **Upper**: Push day (Chest/Triceps) alternates with Pull day (Back/Biceps)
- **Every session**: Lateral raises for shoulders

## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | Streamlit |
| Database (Cloud) | PostgreSQL (Neon) |
| Database (Local) | SQLite |
| ORM | SQLAlchemy 2.0 |
| Python | 3.10+ |

## Project Structure

```
workout_progression_app/
├── app.py                 # Main Streamlit UI
├── db.py                  # SQLAlchemy models & connection
├── services.py            # Session/set CRUD operations
├── progression.py         # Volume & rep progression logic
├── rir_progression.py     # RIR (intensity) progression logic
├── plan.py                # Exercise rotation configuration
├── init_db.py             # Database seeding script
├── check_db.py            # Database health check
├── backup_db.py           # Backup/restore utilities
└── migrate_sqlite_to_postgres.py  # SQLite -> PostgreSQL migration
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
- **Set**: Logged set with `weight`, `reps`, `rir`, `logged_at`
- **Feedback**: Per muscle group with `soreness`, `pump`, `workload` (1-5 scale)

## Quick Start

### Local Development

```bash
# Clone and install
git clone <repo-url>
cd workout_progression_app
pip install -r requirements.txt

# Initialize database (creates exercises & sample workout)
python init_db.py

# Run the app
streamlit run app.py
```

SQLite database (`workout.db`) is created automatically.

### Deploy to Streamlit Cloud

1. **Get a PostgreSQL database** from [Neon.tech](https://neon.tech) (free tier)

2. **Add secret** in Streamlit Cloud dashboard:
   ```toml
   DATABASE_URL = "postgresql://user:password@ep-xxx.region.aws.neon.tech/neondb?sslmode=require"
   ```

3. **Create tables** - Run this SQL in Neon SQL Editor:
   ```sql
   -- Tables are created automatically, but run this to seed data:
   INSERT INTO exercises (name, muscle_group) VALUES
   ('Leg Extension', 'Quads'),
   ('Sissy Squat', 'Quads'),
   ('Leg Curl', 'Hamstrings'),
   ('Hip Thrust + Glute Lunges', 'Glutes'),
   ('Incline DB Bench Press', 'Chest'),
   ('Single-arm Chest Fly', 'Chest'),
   ('Lat Pulldown', 'Lats'),
   ('Cable Row', 'Lats'),
   ('Straight-arm Pulldown', 'Lats'),
   ('Cable Tricep Pushdown', 'Triceps'),
   ('Overhead Cable Extension', 'Triceps'),
   ('Cable Curl', 'Biceps'),
   ('Incline DB Curl', 'Biceps'),
   ('Dumbbell Lateral Raise', 'Shoulders');

   INSERT INTO programs (name) VALUES ('Full Body IV');
   INSERT INTO workouts (program_id, name, day_label) VALUES (1, 'Week 6 Day 4', 'W6D4 Thursday');
   ```

4. **Deploy** - Push to GitHub and connect to Streamlit Cloud

## Utilities

### Check Database Health
```bash
python check_db.py
```

### Migrate Local Data to Cloud
```bash
export DATABASE_URL="postgresql://..."
python migrate_sqlite_to_postgres.py
```

### Backup Database
```bash
python backup_db.py backup    # Creates timestamped backup
python backup_db.py restore <backup_file>  # Restore from backup
```

## Configuration

Edit `plan.py` to customize:

```python
# Exercise rotations
LEG_ROTATION = ["Leg Extension", "Leg Curl", "Hip Thrust + Glute Lunges"]
PULL_MAIN_ROTATION = ["Lat Pulldown", "Cable Row"]

# Default targets
DEFAULT_TARGET_SETS = 4
DEFAULT_TARGET_REPS = 10

# Finisher exercises (start with 1 set, max 3)
EXERCISE_DEFAULT_SETS = {
    "Single-arm Chest Fly": 1,
    "Sissy Squat": 1,
    # ...
}
```

## License

MIT License
