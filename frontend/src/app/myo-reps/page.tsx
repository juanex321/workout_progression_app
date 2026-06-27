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
const SORENESS_LABELS = ["Never got sore", "Healed a while ago", "Healed right on time", "I'm still sore"];
const MIN_REPS_FLOOR = 3;

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

// ---- Soreness Block ----
function SorenessBlock({
  muscleGroup,
  value,
  onChange,
}: {
  muscleGroup: string;
  value: number | null;
  onChange: (v: number) => void;
}) {
  const [expanded, setExpanded] = useState(value === null);

  if (!expanded && value !== null) {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-zinc-700/50 bg-zinc-900/40 px-3 py-2 text-xs mb-1">
        <span className="text-zinc-500">Recovery:</span>
        <span className="font-medium text-zinc-200">{SORENESS_LABELS[value - 1]}</span>
        <button
          onClick={() => setExpanded(true)}
          className="ml-auto text-zinc-500 underline underline-offset-2 hover:text-zinc-300"
        >
          edit
        </button>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-zinc-700/50 bg-zinc-900/40 p-3 mb-1">
      <p className="text-xs font-medium text-zinc-300 mb-2">How did {muscleGroup} recover?</p>
      <div className="grid grid-cols-2 gap-1.5">
        {SORENESS_LABELS.map((label, i) => {
          const v = i + 1;
          const selected = v === value;
          return (
            <button
              key={label}
              onClick={() => {
                onChange(v);
                setExpanded(false);
              }}
              className={`rounded-lg border px-2.5 py-2 text-left text-xs transition-colors
                ${selected
                  ? "border-red-500/60 bg-red-500/20 text-red-100"
                  : "border-zinc-700 bg-zinc-800 text-zinc-300 hover:border-zinc-600 hover:bg-zinc-700"
                }`}
            >
              {label}
            </button>
          );
        })}
      </div>
    </div>
  );
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
      // Create session + log activation set in a single request
      const es = await fetchJSON<{ exercise_session_id: number }>("/api/myo/exercise-sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          myo_session_id: myoSessionId,
          exercise_id: exercise.id,
          activation_weight: weight ? parseFloat(weight) : null,
          activation_reps: parsedReps,
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
            <span className="text-xs bg-red-500/20 text-red-400 border border-red-500/30 px-2 py-0.5 rounded">
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
        {error && <p className="text-xs text-red-400">{error}</p>}

        {/* Last session reference block */}
        {(exercise.last_reps || exercise.last_weight || exercise.last_mini_sets != null) && stage !== "done" && (
          <div className="rounded-lg bg-zinc-900/70 border border-zinc-700/40 px-3 py-2.5 space-y-2">
            <p className="text-[10px] uppercase tracking-widest text-zinc-500">Last session</p>
            <div className="flex items-center">
              <div className="flex-1">
                {(exercise.last_weight || exercise.last_reps) && (
                  <div>
                    <span className="text-sm font-semibold text-zinc-100">
                      {exercise.last_weight ? `${exercise.last_weight}` : ""}
                      {exercise.last_weight && exercise.last_reps ? " × " : ""}
                      {exercise.last_reps ? `${exercise.last_reps} reps` : ""}
                    </span>
                    <span className="text-xs text-zinc-500 ml-1.5">activation</span>
                  </div>
                )}
              </div>
              {exercise.last_mini_sets != null && (
                <div className="text-right">
                  <span className="text-2xl font-bold text-red-400 leading-none">{exercise.last_mini_sets}</span>
                  <p className="text-[10px] text-zinc-500 mt-0.5">mini-sets</p>
                </div>
              )}
            </div>
            {exercise.last_reps != null && exercise.last_reps >= 15 && (
              <div className="flex items-center gap-1.5 rounded-md bg-red-500/10 border border-red-500/25 px-2.5 py-1.5">
                <span className="text-red-400 text-base leading-none">↑</span>
                <span className="text-xs text-red-300">
                  Consider increasing weight — hit {exercise.last_reps} reps last session
                </span>
              </div>
            )}
          </div>
        )}

        {/* IDLE / ACTIVATION stage */}
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
                  className="w-full bg-zinc-700/80 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:ring-1 focus:ring-red-500"
                />
              </div>
              <div className="flex-1">
                <label className="text-xs text-zinc-500 block mb-1">Reps</label>
                <input
                  type="number"
                  value={reps}
                  onChange={(e) => onChange({ reps: e.target.value })}
                  placeholder={exercise.last_reps ? String(exercise.last_reps) : "0"}
                  className="w-full bg-zinc-700/80 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:ring-1 focus:ring-red-500"
                />
              </div>
              <div className="flex items-end">
                <button
                  onClick={logActivation}
                  disabled={submitting}
                  className="h-9 px-4 rounded-lg bg-red-600 text-white text-sm font-medium active:bg-red-500 disabled:opacity-50 whitespace-nowrap"
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
                    className="h-1 rounded-full bg-red-500 transition-all"
                    style={{ width: `${Math.min((miniSets.length / exercise.target_mini_sets) * 100, 100)}%` }}
                  />
                </div>
              </div>
            )}

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

            <div className="flex gap-2">
              <input
                type="number"
                value={miniRepsInput}
                onChange={(e) => onChange({ miniRepsInput: e.target.value })}
                onKeyDown={(e) => e.key === "Enter" && logMiniSet()}
                placeholder={`Mini-set ${miniSets.length + 1} reps`}
                className="flex-1 bg-zinc-700/80 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:ring-1 focus:ring-red-500"
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
                className={`w-full h-10 rounded-lg text-sm font-medium transition-colors
                  ${atFloor || (exercise.target_mini_sets != null && miniSets.length >= exercise.target_mini_sets)
                    ? "bg-red-600 text-white active:bg-red-500"
                    : "bg-zinc-700 text-zinc-400 active:bg-zinc-600"
                  }`}
              >
                {atFloor || (exercise.target_mini_sets != null && miniSets.length >= exercise.target_mini_sets)
                  ? `Done — ${miniSets.length} mini-sets`
                  : `Stop here · ${miniSets.length} mini-sets${exercise.target_mini_sets ? ` (target: ${exercise.target_mini_sets})` : ""}`}
              </button>
            )}
          </div>
        )}

        {/* FEEDBACK stage */}
        {stage === "feedback" && (
          <div className="space-y-3">
            <button
              onClick={() => onChange({ stage: "mini-sets" })}
              className="text-xs text-zinc-500 hover:text-zinc-300 underline underline-offset-2"
            >
              ← Add more mini-sets
            </button>
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
                          ? "bg-red-600 text-white"
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
              className="w-full h-10 rounded-lg bg-red-600 text-white text-sm font-medium active:bg-red-500 disabled:opacity-50"
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
  const [exStates, setExStates] = useState<Record<number, ExerciseState>>({});
  const [sorenessState, setSorenessState] = useState<Record<string, number | null>>({});
  const [sessionDone, setSessionDone] = useState(false);
  const [finishing, setFinishing] = useState(false);

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

  const doneCount = exercises.filter((ex) => exStates[ex.id]?.stage === "done").length;
  const totalCount = exercises.length;
  const allDone = doneCount === totalCount && totalCount > 0;

  const finishSession = async () => {
    if (!myoSessionId) return;
    setFinishing(true);
    try {
      await fetchJSON(`/api/myo/sessions/${myoSessionId}/complete`, { method: "POST" });
      setSessionDone(true);
    } catch (e) {
      setPageError((e as Error).message);
    } finally {
      setFinishing(false);
    }
  };

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
          className="text-xs text-zinc-400 border border-zinc-700 rounded-lg px-3 py-1.5 hover:border-red-600 hover:text-red-500 transition-colors"
        >
          Back to Straight Sets
        </a>
      </div>

      {pageError && (
        <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-3 py-2 text-xs text-red-400">
          {pageError}
        </div>
      )}

      {/* Session complete banner */}
      {sessionDone && (
        <div className="rounded-xl border border-green-500/30 bg-green-500/10 px-4 py-4 text-center">
          <p className="text-green-400 font-semibold">Session complete!</p>
          <p className="text-xs text-zinc-400 mt-1">Rotation advanced — next session is queued for both modes.</p>
          <a href="/" className="mt-3 inline-block text-xs text-zinc-400 underline underline-offset-2 hover:text-zinc-200">
            Back to Straight Sets
          </a>
        </div>
      )}

      {/* Muscle group sections */}
      {!sessionDone && myoSessionId && orderedGroups.map((mg) => (
        <div key={mg} className="space-y-2">
          {/* Muscle group header */}
          <div className="flex items-center gap-2 px-1">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 shrink-0" />
            <span className="text-sm font-semibold text-zinc-100">{mg}</span>
          </div>

          {/* Soreness question */}
          <SorenessBlock
            muscleGroup={mg}
            value={sorenessState[mg] ?? null}
            onChange={(v) => setSorenessState((prev) => ({ ...prev, [mg]: v }))}
          />

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

      {/* Finish session button */}
      {!sessionDone && myoSessionId && totalCount > 0 && (
        <div className="pt-2">
          <button
            onClick={finishSession}
            disabled={finishing}
            className={`w-full h-14 rounded-2xl border font-bold text-base transition-colors disabled:opacity-50
              ${allDone
                ? "border-green-400/30 bg-green-500 text-zinc-950 active:bg-green-400"
                : "border-zinc-600 bg-zinc-800 text-zinc-300 active:bg-zinc-700"
              }`}
          >
            {finishing
              ? "Finishing..."
              : allDone
                ? "Finish Session"
                : `Finish Session · ${doneCount} / ${totalCount} done`}
          </button>
        </div>
      )}
    </main>
  );
}
