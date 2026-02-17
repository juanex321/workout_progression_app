from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as OrmSession

from deps import get_db
from rir_progression import get_rir_for_muscle_group, get_feedback_summary, get_rir_description

router = APIRouter()


@router.get("/rir/{muscle_group}")
def get_rir(muscle_group: str, db: OrmSession = Depends(get_db)):
    """Get current RIR info for a muscle group (debug/info endpoint)."""
    rir, phase, analysis = get_rir_for_muscle_group(db, muscle_group)
    return {
        "muscle_group": muscle_group,
        "rir": rir,
        "phase": phase,
        "description": get_rir_description(rir),
        "feedback_summary": get_feedback_summary(db, muscle_group),
        "analysis": analysis,
    }
