from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session as OrmSession

from deps import get_db
from db import Exercise, MyoExerciseSession, MyoSession, Set as DbSet, WorkoutExercise
from myo_progression import allocate_muscle_reps, get_recommendation, starting_total_rep_target
from plan import EXERCISE_DEFAULT_SETS, EXERCISE_MUSCLE_GROUPS, get_session_exercises
from routes.myo import _default_exercise_target, _exercise_role, _exercise_session_response, _get_default_workout
from services import get_current_session

router = APIRouter()


def _get_or_create_open_myo_session(db: OrmSession) -> MyoSession:
    today = date.today()
    sess = db.query(MyoSession).filter(MyoSession.date == today, MyoSession.completed == 0).first()
    if not sess:
        sess = MyoSession(date=today)
        db.add(sess)
        db.commit()
        db.refresh(sess)
    return sess


def _today_exercises_payload(db: OrmSession, exercise_names: list[str]) -> list[dict]:
    lower_names = [name.lower() for name in exercise_names]
    exercises = db.query(Exercise).filter(func.lower(Exercise.name).in_(lower_names)).all()
    ex_by_name = {e.name.lower(): e for e in exercises}

    muscle_counts: dict[str, list[str]] = {}
    for name in exercise_names:
        muscle_group = EXERCISE_MUSCLE_GROUPS.get(name, "Other")
        muscle_counts.setdefault(muscle_group, []).append(name)

    payload = []
    for name in exercise_names:
        ex = ex_by_name.get(name.lower())
        if not ex:
            continue

        muscle_group = EXERCISE_MUSCLE_GROUPS.get(name, "Other")
        role = _exercise_role(name, muscle_group, exercise_names)
        has_finisher = any(EXERCISE_DEFAULT_SETS.get(n) == 1 for n in muscle_counts.get(muscle_group, []))
        muscle_target = starting_total_rep_target(muscle_group, has_finisher=has_finisher)
        default_target = allocate_muscle_reps(muscle_target, role)
        rec = get_recommendation(db, ex.id, default_total_reps=default_target)

        last_set = (
            db.query(DbSet)
            .join(WorkoutExercise, DbSet.workout_exercise_id == WorkoutExercise.id)
            .filter(WorkoutExercise.exercise_id == ex.id, DbSet.set_number == 1)
            .order_by(DbSet.logged_at.desc())
            .first()
        )
        last_es = (
            db.query(MyoExerciseSession)
            .filter(MyoExerciseSession.exercise_id == ex.id, MyoExerciseSession.completed == 1)
            .order_by(MyoExerciseSession.created_at.desc())
            .first()
        )
        last_total_reps = last_es.completed_mini_sets if last_es else None

        payload.append({
            "id": ex.id,
            "name": name,
            "muscle_group": muscle_group,
            "exercise_role": role,
            "calibrated": rec["calibrated"],
            "calibration_session": rec.get("calibration_session"),
            "target_total_reps": rec.get("target_total_reps"),
            "muscle_target_total_reps": muscle_target,
            "baseline_total_reps": rec.get("baseline"),
            "target_mini_sets": None,
            "baseline_mini_sets": None,
            "last_weight": last_set.weight if last_set else None,
            "last_reps": last_set.reps if last_set else None,
            "last_total_reps": last_total_reps,
            "last_mini_sets": last_total_reps,
        })
    return payload


@router.get("/current")
def get_current_myo_payload(db: OrmSession = Depends(get_db)):
    """One round-trip bootstrap for the myo page.

    Returns the open myo session, today's exercises, and any already-logged exercise
    sessions. This replaces the frontend sequence of /sessions + /today +
    /sessions/{id}/exercise-sessions.
    """
    myo_session = _get_or_create_open_myo_session(db)
    workout = _get_default_workout(db)
    straight_session = get_current_session(db, workout.id)
    exercise_names = get_session_exercises(straight_session.rotation_index)

    existing_sessions = (
        db.query(MyoExerciseSession)
        .filter(MyoExerciseSession.myo_session_id == myo_session.id)
        .order_by(MyoExerciseSession.created_at.asc(), MyoExerciseSession.id.asc())
        .all()
    )

    return {
        "session": {
            "session_id": myo_session.id,
            "date": str(myo_session.date),
            "completed": myo_session.completed,
        },
        "exercises": _today_exercises_payload(db, exercise_names),
        "exercise_sessions": [
            _exercise_session_response(
                es,
                get_recommendation(
                    db,
                    es.exercise_id,
                    default_total_reps=_default_exercise_target(es.exercise.name, exercise_names),
                ),
                exercise_names,
            ).model_dump()
            for es in existing_sessions
        ],
    }
