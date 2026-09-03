from collections import OrderedDict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session as OrmSession, joinedload

from deps import get_db
from schemas import (
    WorkoutDataResponse,
    MuscleGroupData,
    ExerciseData,
    SetData,
    RecommendedSet,
    SaveSetsRequest,
    SaveDraftRequest,
)
from db import Session, Workout, Program, Exercise, Feedback, Set, WorkoutExercise
from services import (
    get_current_session,
    get_session_by_number,
    get_exercise_last_session_metadata,
    get_set_drafts_by_workout_exercise,
    save_sets,
    save_set_draft,
)
from plan import (
    DEFAULT_TARGET_REPS,
    DEFAULT_TARGET_SETS,
    EXERCISE_DEFAULT_REPS,
    EXERCISE_DEFAULT_SETS,
    EXERCISE_MUSCLE_GROUPS,
    get_session_exercises,
)
from progression import (
    recommend_weights_and_reps,
    is_finisher,
    get_exercise_set_bounds,
    get_feedback_summary,
)

router = APIRouter()


def _get_default_workout(db: OrmSession) -> Workout:
    program = db.query(Program).first()
    if not program:
        raise HTTPException(status_code=404, detail="No program found")
    workout = db.query(Workout).filter(Workout.program_id == program.id).first()
    if not workout:
        raise HTTPException(status_code=404, detail="No workout found")
    return workout


def _load_workout_exercises(
    db: OrmSession, workout: Workout, exercise_names: list[str]
) -> list[WorkoutExercise]:
    """Batch load or create the WorkoutExercise rows needed for one session."""
    lower_names = [name.lower() for name in exercise_names]
    exercises = (
        db.query(Exercise)
        .filter(func.lower(Exercise.name).in_(lower_names))
        .all()
    )
    exercise_by_name = {exercise.name.lower(): exercise for exercise in exercises}

    for exercise_name in exercise_names:
        key = exercise_name.lower()
        if key not in exercise_by_name:
            exercise = Exercise(
                name=exercise_name,
                muscle_group=EXERCISE_MUSCLE_GROUPS.get(exercise_name),
            )
            db.add(exercise)
            exercise_by_name[key] = exercise

    db.flush()

    exercise_ids = [exercise_by_name[name.lower()].id for name in exercise_names]
    workout_exercises = (
        db.query(WorkoutExercise)
        .options(joinedload(WorkoutExercise.exercise))
        .filter(
            WorkoutExercise.workout_id == workout.id,
            WorkoutExercise.exercise_id.in_(exercise_ids),
        )
        .all()
    )
    we_by_exercise_id = {we.exercise_id: we for we in workout_exercises}

    ordered_workout_exercises: list[WorkoutExercise] = []
    for idx, exercise_name in enumerate(exercise_names):
        exercise = exercise_by_name[exercise_name.lower()]
        we = we_by_exercise_id.get(exercise.id)
        if not we:
            we = WorkoutExercise(
                workout_id=workout.id,
                exercise_id=exercise.id,
                order_index=idx,
                target_sets=EXERCISE_DEFAULT_SETS.get(exercise_name, DEFAULT_TARGET_SETS),
                target_reps=EXERCISE_DEFAULT_REPS.get(exercise_name, DEFAULT_TARGET_REPS),
            )
            we.exercise = exercise
            db.add(we)
            we_by_exercise_id[exercise.id] = we
        elif we.exercise is None:
            we.exercise = exercise
        ordered_workout_exercises.append(we)

    db.flush()
    return ordered_workout_exercises


def _load_sets_by_workout_exercise(
    db: OrmSession, session_id: int, workout_exercise_ids: list[int]
) -> dict[int, list[Set]]:
    if not workout_exercise_ids:
        return {}

    rows = (
        db.query(Set)
        .filter(
            Set.session_id == session_id,
            Set.workout_exercise_id.in_(workout_exercise_ids),
        )
        .order_by(Set.workout_exercise_id.asc(), Set.set_number.asc())
        .all()
    )
    grouped: dict[int, list[Set]] = {}
    for row in rows:
        grouped.setdefault(row.workout_exercise_id, []).append(row)
    return grouped


def _load_feedback_by_muscle_group(
    db: OrmSession, session_id: int, muscle_groups: list[str]
) -> dict[str, Feedback]:
    if not muscle_groups:
        return {}

    rows = (
        db.query(Feedback)
        .filter(
            Feedback.session_id == session_id,
            Feedback.muscle_group.in_(muscle_groups),
        )
        .order_by(Feedback.created_at.desc())
        .all()
    )
    feedback_by_group: dict[str, Feedback] = {}
    for row in rows:
        if row.muscle_group and row.muscle_group not in feedback_by_group:
            feedback_by_group[row.muscle_group] = row
    return feedback_by_group


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
    workout_exercises = _load_workout_exercises(db, workout, exercise_names)
    existing_sets_by_we = _load_sets_by_workout_exercise(
        db, sess.id, [we.id for we in workout_exercises]
    )
    drafts_by_we = get_set_drafts_by_workout_exercise(
        db, sess.id, [we.id for we in workout_exercises]
    )
    session_muscle_groups = list(OrderedDict(
        (EXERCISE_MUSCLE_GROUPS.get(name, "Other"), None)
        for name in exercise_names
    ).keys())
    feedback_by_muscle_group = _load_feedback_by_muscle_group(
        db, sess.id, session_muscle_groups
    )

    # Build muscle group data
    muscle_groups: OrderedDict[str, MuscleGroupData] = OrderedDict()

    for idx, (ex_name, we) in enumerate(zip(exercise_names, workout_exercises)):
        muscle_group = EXERCISE_MUSCLE_GROUPS.get(ex_name, "Other")

        if muscle_group in muscle_groups:
            fb_summary = muscle_groups[muscle_group].feedback_summary
            fb_exists = muscle_groups[muscle_group].feedback_exists
            fb_values = muscle_groups[muscle_group].feedback_values
            soreness_val = muscle_groups[muscle_group].soreness_value
        else:
            fb_summary = get_feedback_summary(db, muscle_group)
            feedback = feedback_by_muscle_group.get(muscle_group)
            fb_exists = bool(
                feedback
                and feedback.pump is not None
                and feedback.workload is not None
            )
            fb_values = (
                {
                    "soreness": feedback.soreness or 3,
                    "pump": feedback.pump or 3,
                    "workload": feedback.workload or 3,
                }
                if feedback
                else None
            )
            soreness_val = feedback.soreness if feedback else None

        # Get existing logged sets
        existing = existing_sets_by_we.get(we.id, [])
        existing_sets = [
            SetData(
                set_number=s.set_number,
                weight=s.weight,
                reps=s.reps,
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
            )
            for r in recs_raw
        ]
        min_sets, max_sets = get_exercise_set_bounds(db, we)
        recommended_set_count = len(recommendations)
        last_session_summary, weight_recommendation = get_exercise_last_session_metadata(
            db,
            workout_exercise_id=we.id,
            before_session_number=sess.session_number,
        )

        exercise_data = ExerciseData(
            we_id=we.id,
            name=ex_name,
            muscle_group=muscle_group,
            order_idx=idx,
            existing_sets=existing_sets,
            recommendations=recommendations,
            is_finisher=is_finisher(we),
            target_sets=recommended_set_count,
            min_sets=min_sets,
            max_sets=max_sets,
            target_reps=we.target_reps,
            last_session_summary=last_session_summary,
            weight_recommendation=weight_recommendation,
            draft=drafts_by_we.get(we.id),
        )

        # Add to muscle group or create new
        if muscle_group not in muscle_groups:
            muscle_groups[muscle_group] = MuscleGroupData(
                exercises=[exercise_data],
                feedback_summary=fb_summary,
                feedback_exists=fb_exists,
                feedback_values=fb_values,
                soreness_value=soreness_val,
            )
        else:
            muscle_groups[muscle_group].exercises.append(exercise_data)

    db.commit()

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


@router.post("/sets/draft")
def save_exercise_draft(req: SaveDraftRequest, db: OrmSession = Depends(get_db)):
    """Autosave in-progress (not yet logged) set values for one exercise."""
    save_set_draft(
        db,
        req.session_id,
        req.workout_exercise_id,
        [row.model_dump() for row in req.rows],
    )
    return {"status": "ok"}
