export interface SetData {
  set_number: number;
  weight: number | null;
  reps: number | null;
  rir: number | null;
  logged: boolean;
}

export interface RecommendedSet {
  set_number: number;
  weight: number;
  reps: number;
  done: boolean;
  suggest_weight_increase?: boolean;
}

export interface LastSessionSummary {
  last_weight: number;
  avg_reps: number;
  recommended_rir: number;
  set_count: number;
}

export interface WeightRecommendation {
  level: "standard" | "strong" | "hold" | "apply";
  message: string;
  context_note: string | null;
}

export interface ExerciseData {
  we_id: number;
  name: string;
  muscle_group: string | null;
  order_idx: number;
  existing_sets: SetData[];
  recommendations: RecommendedSet[];
  is_finisher: boolean;
  target_sets: number;
  min_sets: number;
  max_sets: number;
  target_reps: number;
  last_session_summary: LastSessionSummary | null;
  weight_recommendation: WeightRecommendation | null;
}

export interface MuscleGroupData {
  exercises: ExerciseData[];
  target_rir: number;
  phase: string;
  feedback_summary: string;
  feedback_exists: boolean;
  feedback_values: {
    soreness: number;
    pump: number;
    workload: number;
  } | null;
  soreness_value: number | null;
}

export interface SessionResponse {
  session_id: number;
  session_number: number;
  rotation_index: number;
  completed: number;
  workout_id: number;
}

export interface WorkoutDataResponse {
  session_id: number;
  session_number: number;
  completed: number;
  rotation_index: number;
  muscle_groups: Record<string, MuscleGroupData>;
}

export interface SaveSetsRequest {
  session_id: number;
  workout_exercise_id: number;
  rows: {
    set_number: number;
    weight: number;
    reps: number;
    done: boolean;
    rir?: number;
  }[];
}

export interface FeedbackRequest {
  session_id: number;
  muscle_group: string;
  soreness: number;
  pump: number;
  workload: number;
}

export interface SorenessRequest {
  session_id: number;
  muscle_group: string;
  soreness: number;
}
