from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session as OrmSession

from deps import get_db
from db import Exercise, MyoSession, MyoExerciseSession, MyoActivationSet, MyoMiniSet, Workout, Program, Session as DbSession
from schemas import (
    MyoSessionResponse,
    MyoStartExerciseRequest,
    MyoActivationSetRequest,
    MyoMiniSetRequest,
    MyoCompleteRequest,
    MyoExerciseSessionResponse,
    MyoMiniSetData,
)
from myo_progression import get_recommendation, record_session_result
from plan import EXERCISE_MUSCLE_GROUPS, get_session_exercises
from services import get_current_session

router = APIRouter()

MIN_REPS_FLOOR = 3


def _get_default_workout(db: OrmSession) -> Workout:
    program = db.query(Program).first()
    if not program:
        raise HTTPException(status_code=404, detail="No program found")
    workout = db.query(Workout).filter(Workout.program_id == program.id).first()
    if not workout:
        raise HTTPException(status_code=404, detail="No workout found")
    return workout


def _exercise_session_response(es: MyoExerciseSession, rec: dict) -> MyoExerciseSessionResponse:
    return MyoExerciseSessionResponse(
        exercise_session_id=es.id,
        exercise_id=es.exercise_id,
        exercise_name=es.exercise.name,
        muscle_group=es.exercise.muscle_group,
        calibrated=rec["calibrated"],
        calibration_session=rec.get("calibration_session"),
        target_mini_sets=es.target_mini_sets,
        baseline_mini_sets=rec.get("baseline"),
        activation_weight=es.activation_set.weight if es.activation_set else None,
        activation_reps=es.activation_set.reps if es.activation_set else None,
        mini_sets=[MyoMiniSetData(order_index=m.order_index, reps=m.reps) for m in es.mini_sets],
        completed=es.completed,
        workload_feedback=es.workload_feedback,
    )


@router.get("/today")
def get_today_exercises(db: OrmSession = Depends(get_db)):
    """Return today's scheduled exercises based on the current session rotation."""
    workout = _get_default_workout(db)
    sess = get_current_session(db, workout.id)
    exercise_names = get_session_exercises(sess.rotation_index)

    lower_names = [name.lower() for name in exercise_names]
    exercises = (
        db.query(Exercise)
        .filter(func.lower(Exercise.name).in_(lower_names))
        .all()
    )
    ex_by_name = {e.name.lower(): e for e in exercises}

    result = []
    for name in exercise_names:
        ex = ex_by_name.get(name.lower())
        if ex:
            result.append({
                "id": ex.id,
                "name": name,
                "muscle_group": EXERCISE_MUSCLE_GROUPS.get(name, "Other"),
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
    return MyoSessionResponse(session_id=sess.id, date=str(sess.date), completed=sess.completed)


@router.post("/sessions/{session_id}/complete", response_model=MyoSessionResponse)
def complete_session(session_id: int, db: OrmSession = Depends(get_db)):
    sess = db.query(MyoSession).get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    sess.completed = 1
    db.flush()
    return MyoSessionResponse(session_id=sess.id, date=str(sess.date), completed=sess.completed)


@router.post("/exercise-sessions", response_model=MyoExerciseSessionResponse)
def start_exercise(req: MyoStartExerciseRequest, db: OrmSession = Depends(get_db)):
    """Start a new exercise within a myo session."""
    sess = db.query(MyoSession).get(req.myo_session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Myo session not found")

    exercise = db.query(Exercise).get(req.exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    rec = get_recommendation(db, req.exercise_id)

    es = MyoExerciseSession(
        myo_session_id=req.myo_session_id,
        exercise_id=req.exercise_id,
        target_mini_sets=rec["target_mini_sets"],
    )
    db.add(es)
    db.flush()

    return _exercise_session_response(es, rec)


@router.get("/exercise-sessions/{exercise_session_id}", response_model=MyoExerciseSessionResponse)
def get_exercise_session(exercise_session_id: int, db: OrmSession = Depends(get_db)):
    es = db.query(MyoExerciseSession).get(exercise_session_id)
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
    es = db.query(MyoExerciseSession).get(exercise_session_id)
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
    db.flush()

    rec = get_recommendation(db, es.exercise_id)
    return _exercise_session_response(es, rec)


@router.post("/exercise-sessions/{exercise_session_id}/miniset", response_model=MyoExerciseSessionResponse)
def log_mini_set(
    exercise_session_id: int,
    req: MyoMiniSetRequest,
    db: OrmSession = Depends(get_db),
):
    es = db.query(MyoExerciseSession).get(exercise_session_id)
    if not es:
        raise HTTPException(status_code=404, detail="Exercise session not found")
    if es.completed:
        raise HTTPException(status_code=400, detail="Exercise session already completed")
    if not es.activation_set:
        raise HTTPException(status_code=400, detail="Log activation set first")

    next_index = len(es.mini_sets) + 1
    mini = MyoMiniSet(exercise_session_id=exercise_session_id, order_index=next_index, reps=req.reps)
    db.add(mini)
    db.flush()

    rec = get_recommendation(db, es.exercise_id)
    return _exercise_session_response(es, rec)


@router.post("/exercise-sessions/{exercise_session_id}/complete", response_model=MyoExerciseSessionResponse)
def complete_exercise_session(
    exercise_session_id: int,
    req: MyoCompleteRequest,
    db: OrmSession = Depends(get_db),
):
    es = db.query(MyoExerciseSession).get(exercise_session_id)
    if not es:
        raise HTTPException(status_code=404, detail="Exercise session not found")
    if es.completed:
        raise HTTPException(status_code=400, detail="Already completed")

    mini_sets_completed = len(es.mini_sets)
    es.completed_mini_sets = mini_sets_completed
    es.workload_feedback = req.workload_feedback
    es.completed = 1

    record_session_result(
        db,
        exercise_id=es.exercise_id,
        mini_sets_completed=mini_sets_completed,
        target_mini_sets=es.target_mini_sets,
        workload_feedback=req.workload_feedback,
    )

    rec = get_recommendation(db, es.exercise_id)
    return _exercise_session_response(es, rec)
