from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as OrmSession

from deps import get_db
from schemas import FeedbackRequest, SorenessRequest
from services import save_muscle_group_feedback, save_soreness_only

router = APIRouter()


@router.post("/muscle-group")
def submit_muscle_group_feedback(req: FeedbackRequest, db: OrmSession = Depends(get_db)):
    """Save or update feedback for a muscle group in a session."""
    save_muscle_group_feedback(
        db, req.session_id, req.muscle_group,
        req.soreness, req.pump, req.workload,
    )
    return {"status": "ok"}


@router.post("/soreness")
def submit_soreness(req: SorenessRequest, db: OrmSession = Depends(get_db)):
    """Save or update soreness only for a muscle group (pre-session, before sets are logged)."""
    save_soreness_only(db, req.session_id, req.muscle_group, req.soreness)
    return {"status": "ok"}
