from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as OrmSession

from deps import get_db
from schemas import SessionResponse
from services import get_current_session, get_session_by_number, complete_session
from db import Program, Workout

router = APIRouter()


def _session_to_response(sess) -> SessionResponse:
    return SessionResponse(
        session_id=sess.id,
        session_number=sess.session_number,
        rotation_index=sess.rotation_index,
        completed=sess.completed,
        workout_id=sess.workout_id,
    )


def _get_default_workout_id(db: OrmSession) -> int:
    """Get the first workout ID (single-program app)."""
    program = db.query(Program).first()
    if not program:
        raise HTTPException(status_code=404, detail="No program found")
    workout = db.query(Workout).filter(Workout.program_id == program.id).first()
    if not workout:
        raise HTTPException(status_code=404, detail="No workout found")
    return workout.id


@router.get("/current", response_model=SessionResponse)
def current_session(workout_id: int = None, db: OrmSession = Depends(get_db)):
    if workout_id is None:
        workout_id = _get_default_workout_id(db)
    sess = get_current_session(db, workout_id)
    return _session_to_response(sess)


@router.get("/{session_number}", response_model=SessionResponse)
def session_by_number(session_number: int, workout_id: int = None, db: OrmSession = Depends(get_db)):
    if workout_id is None:
        workout_id = _get_default_workout_id(db)
    sess = get_session_by_number(db, workout_id, session_number)
    if not sess:
        raise HTTPException(status_code=404, detail=f"Session {session_number} not found")
    return _session_to_response(sess)


@router.post("/{session_id}/complete", response_model=SessionResponse)
def finish_session(session_id: int, db: OrmSession = Depends(get_db)):
    try:
        next_sess = complete_session(db, session_id)
        return _session_to_response(next_sess)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
