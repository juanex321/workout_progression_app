from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as OrmSession

from db import Exercise, Session, Set, WorkoutExercise
from deps import get_db


router = APIRouter()

SESSION_NUMBER = 53
EXPECTED_SETS = {
    1: (100.0, 16),
    2: (100.0, 9),
    3: (100.0, 8),
    4: (100.0, 9),
}


def _serialized(rows: list[Set]) -> list[dict]:
    return [
        {
            "set_number": row.set_number,
            "weight": float(row.weight),
            "reps": row.reps,
        }
        for row in sorted(rows, key=lambda item: item.set_number)
    ]


def _matches_expected(rows: list[Set]) -> bool:
    if len(rows) != len(EXPECTED_SETS):
        return False
    return all(
        row.set_number in EXPECTED_SETS
        and (float(row.weight), row.reps) == EXPECTED_SETS[row.set_number]
        for row in rows
    )


@router.post("/reassign-session-53-leg-curl")
def reassign_session_53_leg_curl(db: OrmSession = Depends(get_db)):
    """One-time, exact-match correction for the verified Session 53 logging error."""
    session = (
        db.query(Session)
        .filter(Session.session_number == SESSION_NUMBER)
        .one_or_none()
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session 53 was not found")

    workout_exercises = (
        db.query(WorkoutExercise)
        .join(Exercise, WorkoutExercise.exercise_id == Exercise.id)
        .filter(
            WorkoutExercise.workout_id == session.workout_id,
            Exercise.name.in_(["Romanian Deadlift", "Leg Curl"]),
        )
        .all()
    )
    by_name = {row.exercise.name: row for row in workout_exercises}
    if set(by_name) != {"Romanian Deadlift", "Leg Curl"}:
        raise HTTPException(status_code=409, detail="Required exercise mappings are missing")

    rdl_id = by_name["Romanian Deadlift"].id
    leg_curl_id = by_name["Leg Curl"].id
    rows = (
        db.query(Set)
        .filter(
            Set.session_id == session.id,
            Set.workout_exercise_id.in_([rdl_id, leg_curl_id]),
        )
        .with_for_update()
        .all()
    )
    rdl_rows = [row for row in rows if row.workout_exercise_id == rdl_id]
    leg_curl_rows = [row for row in rows if row.workout_exercise_id == leg_curl_id]

    if not rdl_rows and _matches_expected(leg_curl_rows):
        return {
            "status": "already_corrected",
            "session_number": SESSION_NUMBER,
            "exercise": "Leg Curl",
            "sets": _serialized(leg_curl_rows),
        }

    if leg_curl_rows or not _matches_expected(rdl_rows):
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Session 53 no longer matches the verified correction preconditions",
                "rdl_sets": _serialized(rdl_rows),
                "leg_curl_sets": _serialized(leg_curl_rows),
            },
        )

    for row in rdl_rows:
        row.workout_exercise_id = leg_curl_id
    db.commit()

    corrected_rows = (
        db.query(Set)
        .filter(
            Set.session_id == session.id,
            Set.workout_exercise_id == leg_curl_id,
        )
        .order_by(Set.set_number.asc())
        .all()
    )
    return {
        "status": "corrected",
        "session_number": SESSION_NUMBER,
        "exercise": "Leg Curl",
        "sets": _serialized(corrected_rows),
    }
