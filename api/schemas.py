from pydantic import BaseModel
from typing import Optional


# --- Request models ---

class SaveSetsRequest(BaseModel):
    session_id: int
    workout_exercise_id: int
    rows: list[dict]


class FeedbackRequest(BaseModel):
    session_id: int
    muscle_group: str
    soreness: int
    pump: int
    workload: int


# --- Response models ---

class SetData(BaseModel):
    set_number: int
    weight: Optional[float] = None
    reps: Optional[int] = None
    rir: Optional[int] = None
    logged: bool = False


class RecommendedSet(BaseModel):
    set_number: int
    weight: float
    reps: int
    done: bool = False
    suggest_weight_increase: Optional[bool] = None


class ExerciseData(BaseModel):
    we_id: int
    name: str
    muscle_group: Optional[str] = None
    order_idx: int
    existing_sets: list[SetData]
    recommendations: list[RecommendedSet]
    is_finisher: bool
    target_sets: int
    target_reps: int


class MuscleGroupData(BaseModel):
    exercises: list[ExerciseData]
    target_rir: int
    phase: str
    feedback_summary: str
    feedback_exists: bool
    feedback_values: Optional[dict] = None


class SessionResponse(BaseModel):
    session_id: int
    session_number: int
    rotation_index: int
    completed: int
    workout_id: int


class WorkoutDataResponse(BaseModel):
    session_id: int
    session_number: int
    completed: int
    rotation_index: int
    muscle_groups: dict[str, MuscleGroupData]
