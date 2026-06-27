"use client";
import { useState, useEffect } from "react";

// ---- Types ----
interface TodayExercise {
  id: number;
  name: string;
  muscle_group: string | null;
  calibrated: boolean;
  calibration_session: number | null;
  target_mini_sets: number | null;
  baseline_mini_sets: number | null;
  last_weight: number | null;
  last_reps: number | null;
  last_mini_sets: number | null;
}

interface MiniSetData {
  order_index: number;
  reps: number;
}

type ExerciseStage = "idle" | "activation" | "mini-sets" | "feedback" | "done";

interface ExerciseState {
  stage: ExerciseStage;
  sessionId: number | null;
  weight: string;
  reps: string;
  miniSets: MiniSetData[];
  miniRepsInput: string;
  workload: number;
  submitting: boolean;
  error: string;
}

const WORKLOAD_LABELS = ["Easy", "Light", "Just Right", "Hard", "Too Much"];
const MIN_REPS_FLOOR = 3;

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

// ---- Exercise Card ----
function ExerciseCard({
  exercise,
  myoSessionId,
  state,
  onChange,
}: {
  exercise: TodayExercise;
  myoSessionId: number;
  state: ExerciseState;
  onChange: (patch: Partial<ExerciseState>) => void;
}) {
  const { stage, sessionId, weight, reps, miniSets, miniRepsInput, workload, submitting, error } = state;

  const logActivation = async () => {
    const parsedReps = parseInt(reps);
    if (!parsedReps || parsedReps < 1) {
      onChange({ error: "Enter reps completed" });
      return;
    }
    onChange({ submitting: true, error: "" });
    try {
      // Create exercise session
      const es = await fetchJSON<{ exercise_session_id: number }>("/api/myo/exercise-sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ myo_session_id: myoSessionId, exercise_id: exercise.id }),
      });
      // Log activation set
      await fetchJSON(`/api/myo/exercise-sessions/${es.exercise_session_id}/activation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          weight: weight ? parseFloat(weight) : null,
          reps: parsedReps,
        }),
      });
      onChange({ sessionId: es.exercise_session_id, stage: "mini-sets", submitting: false });
    } catch (e) {
      onChange({ error: (e as Error).message, submitting: false });
    }
  };

  const logMiniSet = async () => {
    const parsedReps = parseInt(miniRepsInput);
    if (!parsedReps || parsedReps < 1) {
      onChange({ error: "Enter reps" });
      return;
    }
    onChange({ submitting: true, error: "" });
    try {
      const es = await fetchJSON<{ mini_sets: MiniSetData[] }>(
        `/api/myo/exercise-sessions/${sessionId}/miniset`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reps: parsedReps }),
        }
      );
      onChange({ miniSets: es.mini_sets, miniRepsInput: "", submitting: false });
    } catch (e) {
      onChange({ error: (e as Error).message, submitting: false });
    }
  };

  const submitFeedback = async () => {
    onChange({ submitting: true, error: "" });
    try {
      await fetchJSON(`/api/myo/exercise-sessions/${sessionId}/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workload_feedback: workload }),
      });
      onChange({ stage: "done", submitting: false });
    } catch (e) {
      onChange({ error: (e as Error).message, submitting: false });
    }
  };

  const lastMiniReps = miniSets.at(-1)?.reps ?? null;
  const atFloor = lastMiniReps !== null && lastMiniReps < MIN_REPS_FLOOR;

  return (
    <div className="rounded-xl border border-zinc-700 bg-zinc-800/60 overflow-hidden">
      {/* Exercise header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-700/60">
        <span className="font-medium text-zinc-100">{exercise.name}</span>
        <div className="flex items-center gap-2">
          {exercise.calibrated && exercise.target_mini_sets && stage !== "done" && (
            <span className="text-xs text-zinc-400">Target: {exercise.target_mini_sets} mini-sets</span>
          )}
          {!exercise.calibrated && (
            <span className="text-xs bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 px-2 py-0.5 rounded">
              Cal {exercise.calibration_session}/3
            </span>
          )}
          {stage === "done" && (
            <span className="text-xs bg-green-500/20 text-green-400 border border-green-500/30 px-2 py-0.5 rounded">
              Done
            </span>
          )}
        </div>
      </div>

      <div className="px-4 py-3 space-y-3">
        {error && (
          <p className="text-xs text-red-400">{error}</p>
        )}

        {/* Last session reference */}
        {exercise.last_reps && stage !== "done" && (
          <p className="text-xs text-zinc-500">
            Last session: {exercise.last_weight ? `${exercise.last_weight} × ` : ""}{exercise.last_reps} reps
            {exercise.last_mini_sets ? `, ${exercise.last_mini_sets} mini-sets` : ""}
          </p>
        )}

        {/* IDLE / ACTIVATION stage: weight + reps inputs */}
        {(stage === "idle" || stage === "activation") && (
          <div className="space-y-3">
            <p className="text-xs text-zinc-400 uppercase tracking-wide">Activation set — near failure</p>
            <div className="flex gap-2">
              <div className="flex-1">
                <label className="text-xs text-zinc-500 block mb-1">Weight</label>
                <input
                  type="number"
                  value={weight}
                  onChange={(e) => onChange({ weight: e.target.value })}
                  placeholder={exercise.last_weight ? String(exercise.last_weight) : "—"}
                  className="w-full bg-zinc-700/80 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:ring-1 focus:ring-yellow-500"
                />
              </div>
              <div className="flex-1">
                <label className="text-xs text-zinc-500 block mb-1">Reps</label>
                <input
                  type="number"
                  value={reps}
                  onChange={(e) => onChange({ reps: e.target.value })}
                  placeholder={exercise.last_reps ? String(exercise.last_reps) : "0"}
                  className="w-full bg-zinc-700/80 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:ring-1 focus:ring-yellow-500"
                />
              </div>
              <div className="flex items-end">
                <button
                  onClick={logActivation}
                  disabled={submitting}
                  className="h-9 px-4 rounded-lg bg-yellow-600 text-black text-sm font-medium active:bg-yellow-500 disabled:opacity-50 whitespace-nowrap"
                >
                  {submitting ? "..." : "Log"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* MINI-SETS stage */}
        {stage === "mini-sets" && (
          <div className="space-y-3">
            <div className="text-xs text-zinc-400 uppercase tracking-wide">
              Activation: {weight || exercise.last_weight} × {reps} reps
            </div>

            {/* Progress bar */}
            {exercise.target_mini_sets && (
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-zinc-400">
                  <span>{miniSets.length} / {exercise.target_mini_sets} mini-sets</span>
                  <span>
                    {miniSets.length >= exercise.target_mini_sets
                      ? "Target reached!"
                      : `${Math.round((miniSets.length / exercise.target_mini_sets) * 100)}%`}
                  </span>
                </div>
                <div className="h-1 rounded-full bg-zinc-700">
                  <div
                    className="h-1 rounded-full bg-yellow-500 transition-all"
                    style={{ width: `${Math.min((miniSets.length / exercise.target_mini_sets) * 100, 100)}%` }}
                  />
                </div>
              </div>
            )}

            {/* Mini-set list */}
            {miniSets.length > 0 && (
              <div className="grid grid-cols-4 gap-1">
                {miniSets.map((ms) => (
                  <div
                    key={ms.order_index}
                    className={`text-center py-1.5 rounded text-xs font-medium ${
                      ms.reps < MIN_REPS_FLOOR
                        ? "bg-red-500/15 text-red-400"
                        : "bg-zinc-700/80 text-zinc-300"
                    }`}
                  >
                    {ms.reps}
                  </div>
                ))}
              </div>
            )}

            {atFloor && (
              <p className="text-xs text-orange-400">
                Dropped below {MIN_REPS_FLOOR} reps — good place to stop.
              </p>
            )}

            {/* Log mini-set row */}
            <div className="flex gap-2">
              <input
                type="number"
                value={miniRepsInput}
                onChange={(e) => onChange({ miniRepsInput: e.target.value })}
                onKeyDown={(e) => e.key === "Enter" && logMiniSet()}
                placeholder={`Mini-set ${miniSets.length + 1} reps`}
                className="flex-1 bg-zinc-700/80 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:ring-1 focus:ring-yellow-500"
              />
              <button
                onClick={logMiniSet}
                disabled={submitting}
                className="px-4 h-10 rounded-lg bg-zinc-600 text-zinc-100 text-sm font-medium active:bg-zinc-500 disabled:opacity-50"
              >
                {submitting ? "..." : "Log"}
              </button>
            </div>

            {miniSets.length > 0 && (
              <button
                onClick={() => onChange({ stage: "feedback" })}
                className="w-full h-10 rounded-lg bg-yellow-600 text-black text-sm font-medium active:bg-yellow-500"
              >
                Done — {miniSets.length} mini-sets
              </button>
            )}
          </div>
        )}

        {/* FEEDBACK stage */}
        {stage === "feedback" && (
          <div className="space-y-3">
            <div className="grid grid-cols-4 gap-1">
              {miniSets.map((ms) => (
                <div
                  key={ms.order_index}
                  className={`text-center py-1.5 rounded text-xs font-medium ${
                    ms.reps < MIN_REPS_FLOOR
                      ? "bg-red-500/15 text-red-400"
                      : "bg-zinc-700/80 text-zinc-300"
                  }`}
                >
                  {ms.reps}
                </div>
              ))}
            </div>
            <div className="space-y-1.5">
              <p className="text-xs text-zinc-400">How was the workload?</p>
              <div className="flex gap-1">
                {WORKLOAD_LABELS.map((label, i) => {
                  const v = i + 1;
                  return (
                    <button
                      key={label}
                      onClick={() => onChange({ workload: v })}
                      className={`flex-1 py-2 rounded-lg text-xs font-medium transition-colors
                        ${workload === v
                          ? "bg-yellow-600 text-black"
                          : "bg-zinc-700 text-zinc-300 active:bg-zinc-600"
                        }`}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>
            <button
              onClick={submitFeedback}
              disabled={submitting}
              className="w-full h-10 rounded-lg bg-yellow-600 text-black text-sm font-medium active:bg-yellow-500 disabled:opacity-50"
            >
              {submitting ? "Saving..." : "Submit"}
            </button>
          </div>
        )}

        {/* DONE stage */}
        {stage === "done" && (
          <div className="flex items-center justify-between text-sm text-zinc-400">
            <span>
              {weight || exercise.last_weight} × {reps} reps activation
            </span>
            <span>{miniSets.length} mini-sets · {WORKLOAD_LABELS[workload - 1]}</span>
          </div>
        )}
      </div>
    </div>
  );
}

// ---- Main page ----
export default function MyoRepsPage() {
  const [exercises, setExercises] = useState<TodayExercise[]>([]);
  const [loading, setLoading] = useState(true);
  const [myoSessionId, setMyoSessionId] = useState<number | null>(null);
  const [pageError, setPageError] = useState("");

  // Per-exercise state keyed by exercise id
  const [exStates, setExStates] = useState<Record<number, ExerciseState>>({});

  const patchExState = (exerciseId: number, patch: Partial<ExerciseState>) => {
    setExStates((prev) => ({
      ...prev,
      [exerciseId]: { ...prev[exerciseId], ...patch },
    }));
  };

  useEffect(() => {
    async function init() {
      try {
        const [exs, sess] = await Promise.all([
          fetchJSON<TodayExercise[]>("/api/myo/today"),
          fetchJSON<{ session_id: number }>("/api/myo/sessions", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({}),
          }),
        ]);
        setExercises(exs);
        setMyoSessionId(sess.session_id);

        // Init per-exercise state, pre-filling from last session
        const initial: Record<number, ExerciseState> = {};
        for (const ex of exs) {
          initial[ex.id] = {
            stage: "idle",
            sessionId: null,
            weight: ex.last_weight != null ? String(ex.last_weight) : "",
            reps: ex.last_reps != null ? String(ex.last_reps) : "",
            miniSets: [],
            miniRepsInput: "",
            workload: 3,
            submitting: false,
            error: "",
          };
        }
        setExStates(initial);
      } catch (e) {
        setPageError((e as Error).message);
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  // Group exercises by muscle group preserving order
  const grouped: Record<string, TodayExercise[]> = {};
  const orderedGroups: string[] = [];
  for (const ex of exercises) {
    const mg = ex.muscle_group ?? "Other";
    if (!grouped[mg]) {
      grouped[mg] = [];
      orderedGroups.push(mg);
    }
    grouped[mg].push(ex);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-zinc-400">Loading...</p>
      </div>
    );
  }

  return (
    <main className="mx-auto max-w-xl px-3 pb-24 pt-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-zinc-100">Myo Reps</h1>
          <p className="text-xs text-zinc-500">Today&apos;s session — myo reps style</p>
        </div>
        <a
          href="/"
          className="text-xs text-zinc-400 border border-zinc-700 rounded-lg px-3 py-1.5 hover:border-yellow-600 hover:text-yellow-500 transition-colors"
        >
          Back to Straight Sets
        </a>
      </div>

      {pageError && (
        <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-3 py-2 text-xs text-red-400">
          {pageError}
        </div>
      )}

      {/* Muscle group sections */}
      {myoSessionId && orderedGroups.map((mg) => (
        <div key={mg} className="space-y-2">
          {/* Muscle group header */}
          <div className="flex items-center gap-2 px-1">
            <span className="w-2.5 h-2.5 rounded-full bg-yellow-500 shrink-0" />
            <span className="text-sm font-semibold text-zinc-100">{mg}</span>
          </div>

          {/* Exercise cards */}
          {grouped[mg].map((ex) => (
            <ExerciseCard
              key={ex.id}
              exercise={ex}
              myoSessionId={myoSessionId}
              state={exStates[ex.id] ?? {
                stage: "idle", sessionId: null, weight: "", reps: "",
                miniSets: [], miniRepsInput: "", workload: 3, submitting: false, error: "",
              }}
              onChange={(patch) => patchExState(ex.id, patch)}
            />
          ))}
        </div>
      ))}
    </main>
  );
}
