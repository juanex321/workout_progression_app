from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session as OrmSession

from deps import get_db
from db import (
    Exercise,
    MyoSession,
    MyoExerciseSession,
    MyoActivationSet,
    MyoMiniSet,
    Workout,
    Program,
    Set as DbSet,
    WorkoutExercise,
    Session as StraightSetsSession,
)
from schemas import (
    MyoSessionResponse,
    MyoStartExerciseRequest,
    MyoActivationSetRequest,
    MyoMiniSetRequest,
    MyoCompleteRequest,
    MyoExerciseSessionResponse,
    MyoMiniSetData,
)
from myo_progression import (
    allocate_muscle_reps,
    get_recommendation,
    record_session_result,
    starting_total_rep_target,
)
from plan import EXERCISE_DEFAULT_SETS, EXERCISE_MUSCLE_GROUPS, get_session_exercises
from progression import INITIAL_EXERCISE_WEIGHTS
from services import get_myo_session_exercises

router = APIRouter()


def _get_default_workout(db: OrmSession) -> Workout:
    program = db.query(Program).first()
    if not program:
        raise HTTPException(status_code=404, detail="No program found")
    workout = db.query(Workout).filter(Workout.program_id == program.id).first()
    if not workout:
        raise HTTPException(status_code=404, detail="No workout found")
    return workout


def _exercise_role(name: str, muscle_group: str | None, session_exercise_names: list[str] | None = None) -> str:
    if EXERCISE_DEFAULT_SETS.get(name) == 1:
        return "finisher"
    if session_exercise_names and muscle_group:
        same_muscle = [n for n in session_exercise_names if EXERCISE_MUSCLE_GROUPS.get(n) == muscle_group]
        has_finisher = any(EXERCISE_DEFAULT_SETS.get(n) == 1 for n in same_muscle)
        if has_finisher:
            return "main_with_finisher"
    return "main"


def _default_exercise_target(name: str, session_exercise_names: list[str] | None = None) -> int:
    muscle_group = EXERCISE_MUSCLE_GROUPS.get(name, "Other")
    role = _exercise_role(name, muscle_group, session_exercise_names)
    has_finisher = role in {"main_with_finisher", "finisher"}
    muscle_target = starting_total_rep_target(muscle_group, has_finisher=has_finisher)
    return allocate_muscle_reps(muscle_target, role)


def _total_reps(es: MyoExerciseSession) -> int:
    activation = es.activation_set.reps if es.activation_set and es.activation_set.reps else 0
    mini_total = sum(m.reps for m in es.mini_sets)
    return activation + mini_total


def _mini_reps(es: MyoExerciseSession) -> int:
    return sum(m.reps for m in es.mini_sets)


def _exercise_session_response(
    es: MyoExerciseSession,
    rec: dict,
    session_exercise_names: list[str] | None = None,
) -> MyoExerciseSessionResponse:
    mini_sets = sorted(es.mini_sets, key=lambda m: m.order_index)
    muscle_group = EXERCISE_MUSCLE_GROUPS.get(es.exercise.name, es.exercise.muscle_group)
    role = _exercise_role(es.exercise.name, muscle_group, session_exercise_names)
    target_total_reps = es.target_mini_sets or rec.get("target_total_reps")
    return MyoExerciseSessionResponse(
        exercise_session_id=es.id,
        exercise_id=es.exercise_id,
        exercise_name=es.exercise.name,
        muscle_group=muscle_group,
        calibrated=rec["calibrated"],
        calibration_session=rec.get("calibration_session"),
        target_total_reps=target_total_reps,
        baseline_total_reps=rec.get("baseline"),
        total_reps_completed=_total_reps(es),
        mini_reps_completed=_mini_reps(es),
        exercise_role=role,
        target_mini_sets=None,
        baseline_mini_sets=None,
        activation_weight=es.activation_set.weight if es.activation_set else None,
        activation_reps=es.activation_set.reps if es.activation_set else None,
        mini_sets=[MyoMiniSetData(order_index=m.order_index, reps=m.reps) for m in mini_sets],
        completed=es.completed,
        workload_feedback=es.workload_feedback,
    )


def _open_exercise_session(
    db: OrmSession,
    *,
    myo_session_id: int,
    exercise_id: int,
) -> MyoExerciseSession | None:
    """Return the in-progress row for this exercise in this myo session, if one exists."""
    return (
        db.query(MyoExerciseSession)
        .filter(
            MyoExerciseSession.myo_session_id == myo_session_id,
            MyoExerciseSession.exercise_id == exercise_id,
            MyoExerciseSession.completed == 0,
        )
        .order_by(MyoExerciseSession.created_at.desc(), MyoExerciseSession.id.desc())
        .first()
    )


@router.get("/today")
def get_today_exercises(db: OrmSession = Depends(get_db)):
    """Return today's scheduled exercises with calibration state and last session data."""
    today = date.today()
    myo_session = (
        db.query(MyoSession)
        .filter(MyoSession.date == today, MyoSession.completed == 0)
        .first()
    )
    if not myo_session:
        myo_session = MyoSession(date=today)
        db.add(myo_session)
        db.flush()
    exercise_names = get_myo_session_exercises(db, myo_session)

    lower_names = [name.lower() for name in exercise_names]
    exercises = (
        db.query(Exercise)
        .filter(func.lower(Exercise.name).in_(lower_names))
        .all()
    )
    ex_by_name = {e.name.lower(): e for e in exercises}

    for name in exercise_names:
        if name.lower() not in ex_by_name:
            exercise = Exercise(name=name, muscle_group=EXERCISE_MUSCLE_GROUPS.get(name))
            db.add(exercise)
            ex_by_name[name.lower()] = exercise
    db.flush()

    muscle_counts: dict[str, list[str]] = {}
    for name in exercise_names:
        mg = EXERCISE_MUSCLE_GROUPS.get(name, "Other")
        muscle_counts.setdefault(mg, []).append(name)

    result = []
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

        # Pull last weight/reps from straight sets history (set_number=1 = top set)
        last_set = (
            db.query(DbSet)
            .join(WorkoutExercise, DbSet.workout_exercise_id == WorkoutExercise.id)
            .filter(WorkoutExercise.exercise_id == ex.id, DbSet.set_number == 1)
            .order_by(DbSet.logged_at.desc())
            .first()
        )
        last_weight = last_set.weight if last_set else INITIAL_EXERCISE_WEIGHTS.get(name)
        last_reps = last_set.reps if last_set else None

        # Last myo session total-rep count for reference. completed_mini_sets is legacy-named
        # but now stores total reps completed for the exercise.
        last_es = (
            db.query(MyoExerciseSession)
            .filter(MyoExerciseSession.exercise_id == ex.id, MyoExerciseSession.completed == 1)
            .order_by(MyoExerciseSession.created_at.desc())
            .first()
        )
        last_total_reps = last_es.completed_mini_sets if last_es else None

        result.append({
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
            "last_weight": last_weight,
            "last_reps": last_reps,
            "last_total_reps": last_total_reps,
            "last_mini_sets": last_total_reps,
        })
    return result


@router.post("/sessions", response_model=MyoSessionResponse)
def get_or_create_session(db: OrmSession = Depends(get_db)):
    """Get today's open myo session or create one."""
    today = date.today()
    sess = (
        db.query(MyoSession)
        .filter(MyoSession.date == today, MyoSession.completed == 0)
        .first()
    )
    if not sess:
        sess = MyoSession(date=today)
        db.add(sess)
        db.flush()
        get_myo_session_exercises(db, sess)
        db.commit()
        db.refresh(sess)
    return MyoSessionResponse(session_id=sess.id, date=str(sess.date), completed=sess.completed)


@router.get("/sessions/{session_id}/exercise-sessions", response_model=list[MyoExerciseSessionResponse])
def get_session_exercise_sessions(session_id: int, db: OrmSession = Depends(get_db)):
    """Return all exercise sessions already logged in a myo session."""
    sess = db.get(MyoSession, session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Myo session not found")

    exercise_sessions = (
        db.query(MyoExerciseSession)
        .filter(MyoExerciseSession.myo_session_id == session_id)
        .order_by(MyoExerciseSession.created_at.asc(), MyoExerciseSession.id.asc())
        .all()
    )
    exercise_names = [es.exercise.name for es in exercise_sessions] or get_myo_session_exercises(db, sess)
    return [
        _exercise_session_response(
            es,
            get_recommendation(
                db,
                es.exercise_id,
                default_total_reps=_default_exercise_target(es.exercise.name, exercise_names),
            ),
            exercise_names,
        )
        for es in exercise_sessions
    ]


@router.post("/sessions/{session_id}/complete", response_model=MyoSessionResponse)
def finish_myo_session(session_id: int, db: OrmSession = Depends(get_db)):
    sess = db.get(MyoSession, session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    sess.completed = 1
    db.commit()

    return MyoSessionResponse(session_id=sess.id, date=str(sess.date), completed=sess.completed)


@router.post("/exercise-sessions", response_model=MyoExerciseSessionResponse)
def start_exercise(req: MyoStartExerciseRequest, db: OrmSession = Depends(get_db)):
    """Start or resume an exercise and optionally log/update the activation set."""
    sess = db.get(MyoSession, req.myo_session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Myo session not found")
    if sess.completed:
        raise HTTPException(status_code=400, detail="Myo session already completed")

    exercise = db.get(Exercise, req.exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    exercise_names = get_myo_session_exercises(db, sess)
    default_target = _default_exercise_target(exercise.name, exercise_names)
    rec = get_recommendation(db, req.exercise_id, default_total_reps=default_target)
    es = _open_exercise_session(
        db,
        myo_session_id=req.myo_session_id,
        exercise_id=req.exercise_id,
    )

    if not es:
        es = MyoExerciseSession(
            myo_session_id=req.myo_session_id,
            exercise_id=req.exercise_id,
            target_mini_sets=rec["target_total_reps"],
        )
        db.add(es)
        db.flush()
    elif es.target_mini_sets is None:
        es.target_mini_sets = rec["target_total_reps"]

    if req.activation_reps:
        if es.activation_set:
            es.activation_set.weight = req.activation_weight
            es.activation_set.reps = req.activation_reps
        else:
            act = MyoActivationSet(
                exercise_session=es,
                weight=req.activation_weight,
                reps=req.activation_reps,
            )
            db.add(act)

    db.commit()
    db.refresh(es)

    return _exercise_session_response(es, rec, exercise_names)


@router.get("/exercise-sessions/{exercise_session_id}", response_model=MyoExerciseSessionResponse)
def get_exercise_session(exercise_session_id: int, db: OrmSession = Depends(get_db)):
    es = db.get(MyoExerciseSession, exercise_session_id)
    if not es:
        raise HTTPException(status_code=404, detail="Exercise session not found")
    rec = get_recommendation(db, es.exercise_id)
    return _exercise_session_response(es, rec)


@router.post("/exercise-sessions/{exercise_session_id}/activation", response_model=MyoExerciseSessionResponse)
def log_activation_set(
    exercise_session_id: int,
    req: MyoActivationSetRequest,
    db: OrmSession = Depends(get_db),
):
    es = db.get(MyoExerciseSession, exercise_session_id)
    if not es:
        raise HTTPException(status_code=404, detail="Exercise session not found")
    if es.completed:
        raise HTTPException(status_code=400, detail="Exercise session already completed")

    if es.activation_set:
        es.activation_set.weight = req.weight
        es.activation_set.reps = req.reps
    else:
        act = MyoActivationSet(exercise_session_id=exercise_session_id, weight=req.weight, reps=req.reps)
        db.add(act)
    db.commit()
    db.refresh(es)

    rec = get_recommendation(db, es.exercise_id)
    return _exercise_session_response(es, rec)


@router.post("/exercise-sessions/{exercise_session_id}/miniset", response_model=MyoExerciseSessionResponse)
def log_mini_set(
    exercise_session_id: int,
    req: MyoMiniSetRequest,
    db: OrmSession = Depends(get_db),
):
    es = db.get(MyoExerciseSession, exercise_session_id)
    if not es:
        raise HTTPException(status_code=404, detail="Exercise session not found")
    if es.completed:
        raise HTTPException(status_code=400, detail="Exercise session already completed")
    if not es.activation_set:
        raise HTTPException(status_code=400, detail="Log activation set first")

    next_index = (max((m.order_index for m in es.mini_sets), default=0) + 1)
    mini = MyoMiniSet(exercise_session_id=exercise_session_id, order_index=next_index, reps=req.reps)
    db.add(mini)
    db.commit()
    db.refresh(es)

    rec = get_recommendation(db, es.exercise_id)
    return _exercise_session_response(es, rec)


@router.post("/exercise-sessions/{exercise_session_id}/complete", response_model=MyoExerciseSessionResponse)
def complete_exercise_session(
    exercise_session_id: int,
    req: MyoCompleteRequest,
    db: OrmSession = Depends(get_db),
):
    es = db.get(MyoExerciseSession, exercise_session_id)
    if not es:
        raise HTTPException(status_code=404, detail="Exercise session not found")
    if es.completed:
        raise HTTPException(status_code=400, detail="Already completed")

    total_reps_completed = _total_reps(es)
    # Legacy column name; now stores total reps completed.
    es.completed_mini_sets = total_reps_completed
    es.workload_feedback = req.workload_feedback
    es.completed = 1

    record_session_result(
        db,
        exercise_id=es.exercise_id,
        total_reps_completed=total_reps_completed,
        target_total_reps=es.target_mini_sets,
        workload_feedback=req.workload_feedback,
        soreness_feedback=req.soreness_feedback or 3,
        pump_feedback=req.pump_feedback or 3,
    )

    db.commit()
    db.refresh(es)

    rec = get_recommendation(db, es.exercise_id)
    return _exercise_session_response(es, rec)
