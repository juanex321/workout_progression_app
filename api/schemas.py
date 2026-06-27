from pydantic import BaseModel
from typing import Literal, Optional


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


class SorenessRequest(BaseModel):
    session_id: int
    muscle_group: str
    soreness: int


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


class LastSessionSummary(BaseModel):
    last_weight: float
    avg_reps: int
    recommended_rir: int
    set_count: int


class WeightRecommendation(BaseModel):
    level: Literal["standard", "strong", "hold", "apply"]
    message: str
    context_note: Optional[str] = None


class ExerciseData(BaseModel):
    we_id: int
    name: str
    muscle_group: Optional[str] = None
    order_idx: int
    existing_sets: list[SetData]
    recommendations: list[RecommendedSet]
    is_finisher: bool
    target_sets: int
    min_sets: int
    max_sets: int
    target_reps: int
    last_session_summary: Optional[LastSessionSummary] = None
    weight_recommendation: Optional[WeightRecommendation] = None


class MuscleGroupData(BaseModel):
    exercises: list[ExerciseData]
    target_rir: int
    phase: str
    feedback_summary: str
    feedback_exists: bool
    feedback_values: Optional[dict] = None
    soreness_value: Optional[int] = None


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


# --- Myo reps schemas ---

class MyoSessionResponse(BaseModel):
    session_id: int
    date: str
    completed: int


class MyoStartExerciseRequest(BaseModel):
    myo_session_id: int
    exercise_id: int
    activation_weight: Optional[float] = None
    activation_reps: Optional[int] = None


class MyoActivationSetRequest(BaseModel):
    weight: Optional[float] = None
    reps: int


class MyoMiniSetRequest(BaseModel):
    reps: int


class MyoCompleteRequest(BaseModel):
    workload_feedback: int  # 1-5


class MyoMiniSetData(BaseModel):
    order_index: int
    reps: int


class MyoExerciseSessionResponse(BaseModel):
    exercise_session_id: int
    exercise_id: int
    exercise_name: str
    muscle_group: Optional[str]
    calibrated: bool
    calibration_session: Optional[int]
    target_mini_sets: Optional[int]
    baseline_mini_sets: Optional[int]
    activation_weight: Optional[float]
    activation_reps: Optional[int]
    mini_sets: list[MyoMiniSetData]
    completed: int
    workload_feedback: Optional[int]
