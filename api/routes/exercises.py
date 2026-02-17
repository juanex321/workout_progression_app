from collections import OrderedDict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as OrmSession

from deps import get_db
from schemas import (
    WorkoutDataResponse,
    MuscleGroupData,
    ExerciseData,
    SetData,
    RecommendedSet,
    SaveSetsRequest,
)
from db import Session, Workout, Program
from services import (
    get_current_session,
    get_session_by_number,
    get_or_create_workout_exercise,
    load_existing_sets,
    save_sets,
    check_muscle_group_feedback_exists,
    get_muscle_group_feedback,
    is_last_exercise_for_muscle_group,
)
from plan import get_session_exercises, EXERCISE_MUSCLE_GROUPS
from progression import recommend_weights_and_reps, is_finisher
from rir_progression import get_rir_for_muscle_group, get_feedback_summary

router = APIRouter()


def _get_default_workout(db: OrmSession) -> Workout:
    program = db.query(Program).first()
    if not program:
        raise HTTPException(status_code=404, detail="No program found")
    workout = db.query(Workout).filter(Workout.program_id == program.id).first()
    if not workout:
        raise HTTPException(status_code=404, detail="No workout found")
    return workout


@router.get("/workout-data", response_model=WorkoutDataResponse)
def get_workout_data(
    session_id: int = None,
    session_number: int = None,
    db: OrmSession = Depends(get_db),
):
    """
    Main data-loading endpoint. Returns everything the frontend needs for a session.

    Provide either session_id or session_number. If neither, returns current session.
    """
    workout = _get_default_workout(db)

    # Resolve session
    if session_id:
        sess = db.query(Session).filter(Session.id == session_id).first()
        if not sess:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    elif session_number:
        sess = get_session_by_number(db, workout.id, session_number)
        if not sess:
            raise HTTPException(status_code=404, detail=f"Session number {session_number} not found")
    else:
        sess = get_current_session(db, workout.id)

    # Get exercises for this session's rotation
    exercise_names = get_session_exercises(sess.rotation_index)

    # Build muscle group data
    muscle_groups: OrderedDict[str, MuscleGroupData] = OrderedDict()

    for idx, ex_name in enumerate(exercise_names):
        we = get_or_create_workout_exercise(db, workout, ex_name, idx)
        muscle_group = EXERCISE_MUSCLE_GROUPS.get(ex_name, "Other")

        # Get existing logged sets
        existing = load_existing_sets(db, sess.id, we.id)
        existing_sets = [
            SetData(
                set_number=s.set_number,
                weight=s.weight,
                reps=s.reps,
                rir=s.rir,
                logged=True,
            )
            for s in existing
        ]

        # Get recommendations
        recs_raw = recommend_weights_and_reps(db, we, muscle_group)
        recommendations = [
            RecommendedSet(
                set_number=r["set_number"],
                weight=r["weight"],
                reps=r["reps"],
                done=r.get("done", False),
                suggest_weight_increase=r.get("_suggest_weight_increase"),
            )
            for r in recs_raw
        ]

        exercise_data = ExerciseData(
            we_id=we.id,
            name=ex_name,
            muscle_group=muscle_group,
            order_idx=idx,
            existing_sets=existing_sets,
            recommendations=recommendations,
            is_finisher=is_finisher(we),
            target_sets=we.target_sets,
            target_reps=we.target_reps,
        )

        # Add to muscle group or create new
        if muscle_group not in muscle_groups:
            rir, phase, _ = get_rir_for_muscle_group(db, muscle_group)
            fb_summary = get_feedback_summary(db, muscle_group)
            fb_exists = check_muscle_group_feedback_exists(db, sess.id, muscle_group)
            fb_values = get_muscle_group_feedback(db, sess.id, muscle_group)

            muscle_groups[muscle_group] = MuscleGroupData(
                exercises=[exercise_data],
                target_rir=rir,
                phase=phase,
                feedback_summary=fb_summary,
                feedback_exists=fb_exists,
                feedback_values=fb_values,
            )
        else:
            muscle_groups[muscle_group].exercises.append(exercise_data)

    db.commit()  # Persist any new WorkoutExercise records created

    return WorkoutDataResponse(
        session_id=sess.id,
        session_number=sess.session_number,
        completed=sess.completed,
        rotation_index=sess.rotation_index,
        muscle_groups=muscle_groups,
    )


@router.post("/sets/save")
def save_exercise_sets(req: SaveSetsRequest, db: OrmSession = Depends(get_db)):
    """Save sets for one exercise in a session."""
    save_sets(db, req.session_id, req.workout_exercise_id, req.rows)
    return {"status": "ok"}
