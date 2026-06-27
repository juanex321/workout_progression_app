"use client";
import { useState, useEffect } from "react";

// ---- Types ----
interface Exercise {
  id: number;
  name: string;
  muscle_group: string | null;
}

interface MiniSetData {
  order_index: number;
  reps: number;
}

interface ExerciseSession {
  exercise_session_id: number;
  exercise_id: number;
  exercise_name: string;
  muscle_group: string | null;
  calibrated: boolean;
  calibration_session: number | null;
  target_mini_sets: number | null;
  baseline_mini_sets: number | null;
  activation_weight: number | null;
  activation_reps: number | null;
  mini_sets: MiniSetData[];
  completed: number;
  completed_mini_sets: number | null;
  workload_feedback: number | null;
}

const WORKLOAD_LABELS = ["Easy", "Light", "Just Right", "Hard", "Too Much"];
const MIN_REPS_FLOOR = 3;

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

// ---- Sub-components ----

function BackLink() {
  return (
    <a
      href="/"
      className="text-xs text-zinc-400 border border-zinc-700 rounded-lg px-3 py-1.5 hover:border-yellow-600 hover:text-yellow-500 transition-colors"
    >
      Back to Straight Sets
    </a>
  );
}

function ExercisePicker({
  exercises,
  onSelect,
}: {
  exercises: Exercise[];
  onSelect: (ex: Exercise) => void;
}) {
  const grouped = exercises.reduce<Record<string, Exercise[]>>((acc, ex) => {
    const mg = ex.muscle_group ?? "Other";
    (acc[mg] ??= []).push(ex);
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      {Object.entries(grouped).map(([mg, exs]) => (
        <div key={mg}>
          <p className="text-xs text-zinc-500 uppercase tracking-wider mb-2">{mg}</p>
          <div className="space-y-1">
            {exs.map((ex) => (
              <button
                key={ex.id}
                onClick={() => onSelect(ex)}
                className="w-full text-left px-4 py-3 rounded-lg bg-zinc-800 text-sm text-zinc-200 hover:bg-zinc-700 active:bg-zinc-600 transition-colors"
              >
                {ex.name}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function CalibrationBadge({
  calibrated,
  calibrationSession,
}: {
  calibrated: boolean;
  calibrationSession: number | null;
}) {
  if (calibrated) return null;
  return (
    <div className="rounded-lg bg-yellow-500/10 border border-yellow-500/30 px-3 py-2 text-xs text-yellow-400">
      Calibration session {calibrationSession} of 3 — do as many mini-sets as feels right, no target yet.
    </div>
  );
}

function ProgressBar({
  completed,
  target,
}: {
  completed: number;
  target: number | null;
}) {
  if (!target) return null;
  const pct = Math.min((completed / target) * 100, 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-zinc-400">
        <span>{completed} / {target} mini-sets</span>
        <span>{pct >= 100 ? "Target reached!" : `${Math.round(pct)}%`}</span>
      </div>
      <div className="h-1.5 rounded-full bg-zinc-700">
        <div
          className="h-1.5 rounded-full bg-yellow-500 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function MiniSetList({ miniSets }: { miniSets: MiniSetData[] }) {
  if (miniSets.length === 0) return null;
  return (
    <div className="space-y-1">
      {miniSets.map((ms) => (
        <div
          key={ms.order_index}
          className={`flex justify-between items-center px-3 py-2 rounded-lg text-sm ${
            ms.reps < MIN_REPS_FLOOR
              ? "bg-red-500/10 border border-red-500/30 text-red-400"
              : "bg-zinc-800 text-zinc-300"
          }`}
        >
          <span className="text-zinc-500">Mini-set {ms.order_index}</span>
          <span className="font-medium">{ms.reps} reps</span>
        </div>
      ))}
    </div>
  );
}

function WorkloadPicker({
  value,
  onChange,
}: {
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-2">
      <p className="text-xs text-zinc-400">How was the workload?</p>
      <div className="flex gap-1.5">
        {WORKLOAD_LABELS.map((label, i) => {
          const v = i + 1;
          return (
            <button
              key={label}
              onClick={() => onChange(v)}
              className={`flex-1 py-2 px-1 rounded-lg text-xs font-medium text-center transition-colors
                ${value === v
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
  );
}

// ---- Main page ----

type Stage = "pick-exercise" | "activation" | "mini-sets" | "feedback" | "done";

export default function MyoRepsPage() {
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [loadingExercises, setLoadingExercises] = useState(true);
  const [myoSessionId, setMyoSessionId] = useState<number | null>(null);
  const [exerciseSession, setExerciseSession] = useState<ExerciseSession | null>(null);
  const [stage, setStage] = useState<Stage>("pick-exercise");

  // Activation set inputs
  const [activationWeight, setActivationWeight] = useState("");
  const [activationReps, setActivationReps] = useState("");
  const [activationError, setActivationError] = useState("");

  // Mini-set input
  const [miniReps, setMiniReps] = useState("");
  const [miniError, setMiniError] = useState("");

  // Feedback
  const [workload, setWorkload] = useState(3);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [sessionHistory, setSessionHistory] = useState<ExerciseSession[]>([]);

  // Load exercises + create/get myo session
  useEffect(() => {
    async function init() {
      try {
        const [exs, sess] = await Promise.all([
          fetchJSON<Exercise[]>("/api/myo/exercises"),
          fetchJSON<{ session_id: number; date: string; completed: number }>("/api/myo/sessions", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({}),
          }),
        ]);
        setExercises(exs);
        setMyoSessionId(sess.session_id);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoadingExercises(false);
      }
    }
    init();
  }, []);

  const handleSelectExercise = async (ex: Exercise) => {
    if (!myoSessionId) return;
    setSubmitting(true);
    setError("");
    try {
      const es = await fetchJSON<ExerciseSession>("/api/myo/exercise-sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ myo_session_id: myoSessionId, exercise_id: ex.id }),
      });
      setExerciseSession(es);
      setActivationWeight("");
      setActivationReps("");
      setMiniReps("");
      setWorkload(3);
      setStage("activation");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleLogActivation = async () => {
    if (!exerciseSession) return;
    const reps = parseInt(activationReps);
    if (!reps || reps < 1) {
      setActivationError("Enter reps completed");
      return;
    }
    setActivationError("");
    setSubmitting(true);
    try {
      const es = await fetchJSON<ExerciseSession>(
        `/api/myo/exercise-sessions/${exerciseSession.exercise_session_id}/activation`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            weight: activationWeight ? parseFloat(activationWeight) : null,
            reps,
          }),
        }
      );
      setExerciseSession(es);
      setStage("mini-sets");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleLogMiniSet = async () => {
    if (!exerciseSession) return;
    const reps = parseInt(miniReps);
    if (!reps || reps < 1) {
      setMiniError("Enter reps completed");
      return;
    }
    setMiniError("");
    setSubmitting(true);
    try {
      const es = await fetchJSON<ExerciseSession>(
        `/api/myo/exercise-sessions/${exerciseSession.exercise_session_id}/miniset`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reps }),
        }
      );
      setExerciseSession(es);
      setMiniReps("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleFinishMiniSets = () => {
    setStage("feedback");
  };

  const handleSubmitFeedback = async () => {
    if (!exerciseSession) return;
    setSubmitting(true);
    try {
      const es = await fetchJSON<ExerciseSession>(
        `/api/myo/exercise-sessions/${exerciseSession.exercise_session_id}/complete`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ workload_feedback: workload }),
        }
      );
      setSessionHistory((h) => [...h, es]);
      setExerciseSession(es);
      setStage("done");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleAddAnother = () => {
    setExerciseSession(null);
    setStage("pick-exercise");
    setError("");
  };

  const lastMiniReps = exerciseSession?.mini_sets.at(-1)?.reps ?? null;
  const atFloor = lastMiniReps !== null && lastMiniReps < MIN_REPS_FLOOR;

  if (loadingExercises) {
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
          <p className="text-xs text-zinc-500">Activation set + mini-sets to floor</p>
        </div>
        <BackLink />
      </div>

      {error && (
        <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}

      {/* Session history summary */}
      {sessionHistory.length > 0 && stage !== "done" && (
        <div className="rounded-lg bg-zinc-800/50 p-3 space-y-1">
          <p className="text-xs text-zinc-500 uppercase tracking-wider">Done today</p>
          {sessionHistory.map((s) => (
            <div key={s.exercise_session_id} className="flex justify-between text-sm">
              <span className="text-zinc-300">{s.exercise_name}</span>
              <span className="text-zinc-500">{s.completed_mini_sets} mini-sets</span>
            </div>
          ))}
        </div>
      )}

      {/* Stage: pick exercise */}
      {stage === "pick-exercise" && (
        <div className="space-y-3">
          <p className="text-sm text-zinc-400">Select an exercise</p>
          {submitting ? (
            <p className="text-zinc-500 text-sm">Starting...</p>
          ) : (
            <ExercisePicker exercises={exercises} onSelect={handleSelectExercise} />
          )}
        </div>
      )}

      {/* Stage: activation set */}
      {stage === "activation" && exerciseSession && (
        <div className="space-y-4">
          <div className="rounded-lg bg-zinc-800 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="font-medium text-zinc-100">{exerciseSession.exercise_name}</h2>
              {exerciseSession.muscle_group && (
                <span className="text-xs text-zinc-500 bg-zinc-700 px-2 py-0.5 rounded">
                  {exerciseSession.muscle_group}
                </span>
              )}
            </div>

            <CalibrationBadge
              calibrated={exerciseSession.calibrated}
              calibrationSession={exerciseSession.calibration_session}
            />

            <div className="space-y-2">
              <p className="text-sm font-medium text-zinc-300">Activation set — go to near failure</p>
              <div className="flex gap-2">
                <div className="flex-1">
                  <label className="text-xs text-zinc-500 block mb-1">Weight (kg/lb)</label>
                  <input
                    type="number"
                    value={activationWeight}
                    onChange={(e) => setActivationWeight(e.target.value)}
                    placeholder="—"
                    className="w-full bg-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:ring-1 focus:ring-yellow-500"
                  />
                </div>
                <div className="flex-1">
                  <label className="text-xs text-zinc-500 block mb-1">Reps *</label>
                  <input
                    type="number"
                    value={activationReps}
                    onChange={(e) => setActivationReps(e.target.value)}
                    placeholder="0"
                    className="w-full bg-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:ring-1 focus:ring-yellow-500"
                  />
                </div>
              </div>
              {activationError && (
                <p className="text-xs text-red-400">{activationError}</p>
              )}
            </div>

            <button
              onClick={handleLogActivation}
              disabled={submitting}
              className="w-full h-11 rounded-lg bg-yellow-600 text-black font-medium text-sm active:bg-yellow-500 disabled:opacity-50"
            >
              {submitting ? "Saving..." : "Done — start mini-sets"}
            </button>
          </div>
        </div>
      )}

      {/* Stage: mini-sets */}
      {stage === "mini-sets" && exerciseSession && (
        <div className="space-y-4">
          <div className="rounded-lg bg-zinc-800 p-4 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-medium text-zinc-100">{exerciseSession.exercise_name}</h2>
              <span className="text-xs text-zinc-400">
                Activation: {exerciseSession.activation_reps} reps
                {exerciseSession.activation_weight
                  ? ` @ ${exerciseSession.activation_weight}`
                  : ""}
              </span>
            </div>

            <ProgressBar
              completed={exerciseSession.mini_sets.length}
              target={exerciseSession.target_mini_sets}
            />

            <MiniSetList miniSets={exerciseSession.mini_sets} />

            {atFloor ? (
              <div className="rounded-lg bg-orange-500/10 border border-orange-500/30 px-3 py-2 text-xs text-orange-400">
                Last mini-set dropped below {MIN_REPS_FLOOR} reps — good time to stop.
              </div>
            ) : null}

            <div className="space-y-2">
              <p className="text-sm text-zinc-400">
                Mini-set {exerciseSession.mini_sets.length + 1} — reps completed
              </p>
              <div className="flex gap-2">
                <input
                  type="number"
                  value={miniReps}
                  onChange={(e) => setMiniReps(e.target.value)}
                  placeholder="0"
                  className="flex-1 bg-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:ring-1 focus:ring-yellow-500"
                />
                <button
                  onClick={handleLogMiniSet}
                  disabled={submitting}
                  className="px-4 h-10 rounded-lg bg-zinc-600 text-zinc-100 font-medium text-sm active:bg-zinc-500 disabled:opacity-50"
                >
                  {submitting ? "..." : "Log"}
                </button>
              </div>
              {miniError && <p className="text-xs text-red-400">{miniError}</p>}
            </div>

            {exerciseSession.mini_sets.length > 0 && (
              <button
                onClick={handleFinishMiniSets}
                className="w-full h-11 rounded-lg bg-yellow-600 text-black font-medium text-sm active:bg-yellow-500"
              >
                Done — {exerciseSession.mini_sets.length} mini-sets
              </button>
            )}
          </div>
        </div>
      )}

      {/* Stage: feedback */}
      {stage === "feedback" && exerciseSession && (
        <div className="rounded-lg bg-zinc-800 p-4 space-y-4">
          <h2 className="font-medium text-zinc-100">{exerciseSession.exercise_name}</h2>
          <div className="flex justify-between text-sm text-zinc-400">
            <span>Activation: {exerciseSession.activation_reps} reps</span>
            <span>{exerciseSession.mini_sets.length} mini-sets</span>
          </div>
          <MiniSetList miniSets={exerciseSession.mini_sets} />
          <WorkloadPicker value={workload} onChange={setWorkload} />
          <button
            onClick={handleSubmitFeedback}
            disabled={submitting}
            className="w-full h-11 rounded-lg bg-yellow-600 text-black font-medium text-sm active:bg-yellow-500 disabled:opacity-50"
          >
            {submitting ? "Saving..." : "Submit"}
          </button>
        </div>
      )}

      {/* Stage: done */}
      {stage === "done" && exerciseSession && (
        <div className="space-y-4">
          <div className="rounded-lg bg-green-500/10 border border-green-500/20 p-4 space-y-2">
            <p className="font-medium text-green-400">{exerciseSession.exercise_name} done</p>
            <div className="flex justify-between text-sm text-zinc-400">
              <span>Activation: {exerciseSession.activation_reps} reps</span>
              <span>{exerciseSession.completed_mini_sets} mini-sets</span>
            </div>
            {exerciseSession.calibrated && exerciseSession.target_mini_sets && (
              <p className="text-xs text-zinc-500">
                Next target:{" "}
                <span className="text-zinc-300 font-medium">
                  {/* The backend already updated target, so show it from the next recommendation */}
                  {exerciseSession.completed_mini_sets! >= exerciseSession.target_mini_sets
                    ? exerciseSession.target_mini_sets + 1
                    : exerciseSession.target_mini_sets}{" "}
                  mini-sets
                </span>
              </p>
            )}
            {!exerciseSession.calibrated && (
              <p className="text-xs text-zinc-500">
                Calibration session {exerciseSession.calibration_session} of 3 recorded.
              </p>
            )}
          </div>

          {/* Full history */}
          {sessionHistory.length > 0 && (
            <div className="rounded-lg bg-zinc-800/50 p-3 space-y-1">
              <p className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Today&apos;s session</p>
              {sessionHistory.map((s) => (
                <div key={s.exercise_session_id} className="flex justify-between text-sm">
                  <span className="text-zinc-300">{s.exercise_name}</span>
                  <span className="text-zinc-500">{s.completed_mini_sets} mini-sets</span>
                </div>
              ))}
            </div>
          )}

          <button
            onClick={handleAddAnother}
            className="w-full h-11 rounded-lg bg-zinc-700 text-zinc-100 font-medium text-sm active:bg-zinc-600"
          >
            Add another exercise
          </button>
        </div>
      )}
    </main>
  );
}
