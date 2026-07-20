"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { SessionHeader } from "@/components/SessionHeader";

type Stage = "idle" | "mini" | "ready" | "done";
type MiniSet = { order_index: number; reps: number };

type TodayExercise = {
  id: number;
  name: string;
  muscle_group: string | null;
  exercise_role?: string;
  calibrated: boolean;
  calibration_session: number | null;
  target_total_reps: number | null;
  muscle_target_total_reps?: number | null;
  baseline_total_reps?: number | null;
  target_mini_sets?: number | null;
  baseline_mini_sets?: number | null;
  last_weight: number | null;
  last_reps: number | null;
  last_total_reps?: number | null;
  last_mini_sets?: number | null;
};

type ExistingExerciseSession = {
  exercise_session_id: number;
  exercise_id: number;
  activation_weight: number | null;
  activation_reps: number | null;
  mini_sets: MiniSet[];
  completed: number;
  workload_feedback: number | null;
};

type BootstrapPayload = {
  session: {
    session_id: number;
    session_number: number;
    latest_session_number: number;
    date: string;
    completed: number;
  };
  straight_session_id: number | null;
  exercises: TodayExercise[];
  exercise_sessions: ExistingExerciseSession[];
};

type ExerciseState = {
  stage: Stage;
  sessionId: number | null;
  weight: string;
  reps: string;
  loggedActivationReps: number | null;
  miniSets: MiniSet[];
  miniRepsInput: string;
  workload: number;
  submitting: boolean;
  error: string;
};

type Snapshot = Record<number, ExerciseState>;

type MuscleFeedbackState = {
  workload: number;
  pump: number;
  submitting: boolean;
  error: string;
};

const WORKLOAD_LABELS = ["Easy", "Light", "Just Right", "Hard", "Too Much"];
const PUMP_LABELS = ["Low", "Okay", "Good", "Great", "Huge"];
const SORENESS_LABELS = ["Never got sore", "Healed a while ago", "Healed right on time", "Still sore"];
const MIN_REPS_FLOOR = 3;

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text.trimStart().startsWith("<") ? `Server error (${response.status})` : `${response.status}: ${text.slice(0, 200)}`);
  }
  return response.json();
}

function toInt(value: string): number {
  const parsed = parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : 0;
}

function toNumber(value: string): number {
  const parsed = parseFloat(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function stepValue(value: string, delta: number, min: number): string {
  const next = Math.max(min, toNumber(value) + delta);
  return String(Number.isInteger(next) ? next : Number(next.toFixed(1)));
}

function miniTotal(state?: ExerciseState): number {
  return state?.miniSets.reduce((sum, set) => sum + set.reps, 0) ?? 0;
}

function totalReps(state?: ExerciseState): number {
  return (state?.loggedActivationReps ?? 0) + miniTotal(state);
}

function cloneStates(states: Snapshot): Snapshot {
  return Object.fromEntries(
    Object.entries(states).map(([key, value]) => [
      Number(key),
      { ...value, miniSets: value.miniSets.map((set) => ({ ...set })) },
    ])
  );
}

function InlineStepper({ value, onChange, step, min, suffix, disabled, onEnter }: {
  value: string;
  onChange: (value: string) => void;
  step: number;
  min: number;
  suffix: string;
  disabled?: boolean;
  onEnter?: () => void;
}) {
  return (
    <div className="flex min-w-0 flex-1 items-center">
      <button type="button" onClick={() => onChange(stepValue(value, -step, min))} disabled={disabled || toNumber(value) <= min} className="h-10 w-10 rounded-l-lg border border-zinc-600 bg-zinc-700 text-lg font-bold disabled:opacity-30">−</button>
      <div className="relative h-10 min-w-0 flex-1 border-y border-zinc-600 bg-zinc-900/70">
        <input type="number" value={value} onChange={(event) => onChange(event.target.value)} onKeyDown={(event) => event.key === "Enter" && onEnter?.()} disabled={disabled} className="h-full w-full bg-transparent px-4 text-center text-sm font-semibold outline-none focus:ring-1 focus:ring-red-500" />
        <span className="pointer-events-none absolute right-1.5 top-1/2 -translate-y-1/2 text-[10px] uppercase tracking-widest text-zinc-500">{suffix}</span>
      </div>
      <button type="button" onClick={() => onChange(stepValue(value, step, min))} disabled={disabled} className="h-10 w-10 rounded-r-lg border border-zinc-600 bg-zinc-700 text-lg font-bold disabled:opacity-30">+</button>
    </div>
  );
}

function CompactSummary({ state, target }: { state: ExerciseState; target: number }) {
  const total = totalReps(state);
  return (
    <div className="rounded-lg border border-zinc-700/40 bg-zinc-900/45 px-3 py-2">
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="font-semibold text-zinc-100">{state.weight || "—"} × {state.loggedActivationReps ?? 0} <span className="text-xs font-normal text-zinc-500">activation</span></span>
        <span className="font-semibold text-zinc-100">{total} / {target}</span>
      </div>
      <div className="mt-1 flex items-center justify-between text-[11px] text-zinc-500">
        <span>{miniTotal(state)} mini reps</span>
        <span>{Math.max(target - total, 0)} left</span>
      </div>
    </div>
  );
}

function ExerciseCard({ exercise, myoSessionId, state, editable, onChange }: {
  exercise: TodayExercise;
  myoSessionId: number;
  state: ExerciseState;
  editable: boolean;
  onChange: (patch: Partial<ExerciseState>) => void;
}) {
  const target = exercise.target_total_reps ?? exercise.muscle_target_total_reps ?? 45;
  const [miniEdit, setMiniEdit] = useState<{ orderIndex: number; reps: string } | null>(null);

  const applyResponse = (response: ExistingExerciseSession, patch: Partial<ExerciseState> = {}) => {
    onChange({
      sessionId: response.exercise_session_id,
      weight: response.activation_weight != null ? String(response.activation_weight) : state.weight,
      reps: response.activation_reps != null ? String(response.activation_reps) : state.reps,
      loggedActivationReps: response.activation_reps,
      miniSets: response.mini_sets,
      workload: response.workload_feedback ?? state.workload,
      submitting: false,
      error: "",
      ...patch,
    });
  };

  const saveActivation = async () => {
    const activationReps = toInt(state.reps);
    if (activationReps < 1) return onChange({ error: "Enter activation reps" });
    onChange({ submitting: true, error: "" });
    try {
      const response = state.sessionId
        ? await fetchJSON<ExistingExerciseSession>(`/api/myo/exercise-sessions/${state.sessionId}/activation`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ weight: state.weight ? toNumber(state.weight) : null, reps: activationReps }),
          })
        : await fetchJSON<ExistingExerciseSession>("/api/myo/exercise-sessions", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ myo_session_id: myoSessionId, exercise_id: exercise.id, activation_weight: state.weight ? toNumber(state.weight) : null, activation_reps: activationReps }),
          });
      applyResponse(response, { stage: response.completed ? "done" : "mini" });
    } catch (error) {
      onChange({ submitting: false, error: (error as Error).message });
    }
  };

  const addMiniSet = async () => {
    if (!state.sessionId) return onChange({ error: "Log activation first" });
    const reps = toInt(state.miniRepsInput);
    if (reps < 1) return onChange({ error: "Enter mini-set reps" });
    onChange({ submitting: true, error: "" });
    try {
      const response = await fetchJSON<ExistingExerciseSession>(`/api/myo/exercise-sessions/${state.sessionId}/miniset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reps }),
      });
      applyResponse(response, { miniRepsInput: String(reps) });
    } catch (error) {
      onChange({ submitting: false, error: (error as Error).message });
    }
  };

  const saveMiniEdit = async () => {
    if (!state.sessionId || !miniEdit) return;
    const reps = toInt(miniEdit.reps);
    if (reps < 1) return onChange({ error: "Enter mini-set reps" });
    onChange({ submitting: true, error: "" });
    try {
      const response = await fetchJSON<ExistingExerciseSession>(`/api/myo/exercise-sessions/${state.sessionId}/miniset/${miniEdit.orderIndex}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reps }),
      });
      applyResponse(response);
      setMiniEdit(null);
    } catch (error) {
      onChange({ submitting: false, error: (error as Error).message });
    }
  };

  const deleteMiniSet = async (orderIndex: number) => {
    if (!state.sessionId) return;
    onChange({ submitting: true, error: "" });
    try {
      const response = await fetchJSON<ExistingExerciseSession>(`/api/myo/exercise-sessions/${state.sessionId}/miniset/${orderIndex}`, { method: "DELETE" });
      applyResponse(response);
      setMiniEdit(null);
    } catch (error) {
      onChange({ submitting: false, error: (error as Error).message });
    }
  };

  return (
    <div className="overflow-hidden rounded-xl border border-zinc-700 bg-zinc-800/60">
      <div className="flex items-center justify-between border-b border-zinc-700/60 px-4 py-3">
        <div><span className="font-medium text-zinc-100">{exercise.name}</span><span className="ml-2 text-[10px] uppercase tracking-wider text-zinc-500">{exercise.exercise_role === "finisher" ? "Finisher" : "Main"}</span></div>
        <span className={`rounded border px-2 py-0.5 text-xs ${state.stage === "done" ? "border-green-500/30 bg-green-500/20 text-green-400" : "border-zinc-600 text-zinc-400"}`}>{state.stage === "done" ? "Done" : `${target} reps`}</span>
      </div>
      <div className="space-y-3 px-4 py-3">
        {state.error && <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-400">{state.error}</div>}
        <CompactSummary state={state} target={target} />

        {!editable && state.miniSets.length > 0 && (
          <div><p className="mb-1 text-[10px] uppercase tracking-widest text-zinc-500">Mini-sets</p><div className="flex flex-wrap gap-1.5">{state.miniSets.map((set) => <span key={set.order_index} className="min-w-8 rounded bg-zinc-700/80 px-2 py-1 text-center text-xs text-zinc-200">{set.reps}</span>)}</div></div>
        )}

        {editable && (
          <>
            <div>
              <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-zinc-400">Activation set</p>
              <div className="flex gap-2">
                <InlineStepper value={state.weight} onChange={(value) => onChange({ weight: value })} step={2.5} min={0} suffix="lb" disabled={state.submitting} />
                <InlineStepper value={state.reps} onChange={(value) => onChange({ reps: value })} step={1} min={1} suffix="reps" disabled={state.submitting} onEnter={saveActivation} />
                <button onClick={saveActivation} disabled={state.submitting} className="h-10 rounded-lg bg-red-600 px-3 text-sm font-medium text-white disabled:opacity-50">Save</button>
              </div>
            </div>

            {state.miniSets.length > 0 && <div className="grid grid-cols-6 gap-1.5">{state.miniSets.map((set) => <button key={set.order_index} type="button" onClick={() => setMiniEdit({ orderIndex: set.order_index, reps: String(set.reps) })} className={`rounded py-1.5 text-xs font-medium ${set.reps < MIN_REPS_FLOOR ? "bg-red-500/15 text-red-400" : "bg-zinc-700/80 text-zinc-200"}`}>{set.reps}</button>)}</div>}

            {miniEdit ? (
              <div className="rounded-lg border border-zinc-700 bg-zinc-900/60 p-3">
                <p className="mb-2 text-xs font-medium text-zinc-300">Edit mini-set {miniEdit.orderIndex}</p>
                <div className="flex gap-2">
                  <InlineStepper value={miniEdit.reps} onChange={(value) => setMiniEdit((previous) => previous ? { ...previous, reps: value } : previous)} step={1} min={1} suffix="reps" disabled={state.submitting} onEnter={saveMiniEdit} />
                  <button onClick={saveMiniEdit} disabled={state.submitting} className="h-10 rounded-lg bg-red-600 px-3 text-sm font-medium text-white">Save</button>
                  <button onClick={() => deleteMiniSet(miniEdit.orderIndex)} disabled={state.submitting} className="h-10 rounded-lg border border-red-500/40 px-3 text-sm text-red-300">Delete</button>
                  <button onClick={() => setMiniEdit(null)} disabled={state.submitting} className="h-10 rounded-lg bg-zinc-700 px-3 text-sm text-zinc-300">Cancel</button>
                </div>
              </div>
            ) : (
              <div className="flex gap-2">
                <InlineStepper value={state.miniRepsInput} onChange={(value) => onChange({ miniRepsInput: value })} step={1} min={1} suffix="reps" disabled={state.submitting} onEnter={addMiniSet} />
                <button onClick={addMiniSet} disabled={state.submitting || !state.sessionId} className="h-10 rounded-lg bg-zinc-600 px-4 text-sm font-medium disabled:opacity-50">Add</button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default function MyoRepsPage() {
  const [exercises, setExercises] = useState<TodayExercise[]>([]);
  const [exStates, setExStates] = useState<Snapshot>({});
  const [editSnapshot, setEditSnapshot] = useState<Snapshot | null>(null);
  const [myoSessionId, setMyoSessionId] = useState<number | null>(null);
  const [straightSessionId, setStraightSessionId] = useState<number | null>(null);
  const [sessionNumber, setSessionNumber] = useState(1);
  const [latestSessionNumber, setLatestSessionNumber] = useState(1);
  const [sessionCompleted, setSessionCompleted] = useState(0);
  const [editingWorkout, setEditingWorkout] = useState(false);
  const [loading, setLoading] = useState(true);
  const [isNavigating, setIsNavigating] = useState(false);
  const [pageError, setPageError] = useState("");
  const [finishing, setFinishing] = useState(false);
  const [sorenessState, setSorenessState] = useState<Record<string, number | null>>({});
  const [muscleFeedback, setMuscleFeedback] = useState<Record<string, MuscleFeedbackState>>({});

  const patchExState = (exerciseId: number, patch: Partial<ExerciseState>) => setExStates((previous) => ({ ...previous, [exerciseId]: { ...previous[exerciseId], ...patch } }));

  const applySessionPayload = useCallback((payload: BootstrapPayload) => {
    setMyoSessionId(payload.session.session_id);
    setStraightSessionId(payload.straight_session_id);
    setSessionNumber(payload.session.session_number);
    setLatestSessionNumber(payload.session.latest_session_number);
    setSessionCompleted(payload.session.completed);
    setExercises(payload.exercises);
    setEditingWorkout(false);
    setEditSnapshot(null);
    setSorenessState({});
    setMuscleFeedback({});
    const existingByExercise = new Map(payload.exercise_sessions.map((session) => [session.exercise_id, session]));
    const initial: Snapshot = {};
    for (const exercise of payload.exercises) {
      const existing = existingByExercise.get(exercise.id);
      initial[exercise.id] = {
        stage: existing?.completed ? "done" : existing?.activation_reps != null ? "mini" : "idle",
        sessionId: existing?.exercise_session_id ?? null,
        weight: existing?.activation_weight != null ? String(existing.activation_weight) : exercise.last_weight != null ? String(exercise.last_weight) : "",
        reps: existing?.activation_reps != null ? String(existing.activation_reps) : exercise.last_reps != null ? String(exercise.last_reps) : "",
        loggedActivationReps: existing?.activation_reps ?? null,
        miniSets: existing?.mini_sets ?? [],
        miniRepsInput: existing?.mini_sets.at(-1)?.reps != null ? String(existing.mini_sets.at(-1)?.reps) : "",
        workload: existing?.workload_feedback ?? 3,
        submitting: false,
        error: "",
      };
    }
    setExStates(initial);
  }, []);

  const loadCurrentSession = useCallback(async () => applySessionPayload(await fetchJSON<BootstrapPayload>("/api/myo/current")), [applySessionPayload]);

  useEffect(() => {
    loadCurrentSession().catch((error) => setPageError((error as Error).message)).finally(() => setLoading(false));
  }, [loadCurrentSession]);

  const navigateSession = async (next: number) => {
    if (isNavigating || next < 1 || next > latestSessionNumber) return;
    setIsNavigating(true);
    setPageError("");
    try {
      applySessionPayload(await fetchJSON<BootstrapPayload>(next === latestSessionNumber ? "/api/myo/current" : `/api/myo/sessions/by-number/${next}`));
    } catch (error) {
      setPageError((error as Error).message);
    } finally {
      setIsNavigating(false);
    }
  };

  const grouped = useMemo(() => {
    const result: Record<string, TodayExercise[]> = {};
    for (const exercise of exercises) (result[exercise.muscle_group ?? "Other"] ??= []).push(exercise);
    return result;
  }, [exercises]);

  const beginEdit = () => {
    setEditSnapshot(cloneStates(exStates));
    setEditingWorkout(true);
  };

  const cancelEdit = () => {
    if (editSnapshot) setExStates(cloneStates(editSnapshot));
    setEditSnapshot(null);
    setEditingWorkout(false);
  };

  const finishEdit = async () => {
    setEditingWorkout(false);
    setEditSnapshot(null);
    await navigateSession(sessionNumber);
  };

  const finishSession = async () => {
    if (!myoSessionId) return;
    setFinishing(true);
    setPageError("");
    try {
      await Promise.all(exercises.filter((exercise) => exStates[exercise.id]?.sessionId && exStates[exercise.id]?.stage !== "done").map((exercise) => fetchJSON(`/api/myo/exercise-sessions/${exStates[exercise.id].sessionId}/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workload_feedback: exStates[exercise.id].workload, soreness_feedback: sorenessState[exercise.muscle_group ?? "Other"] ?? 3, pump_feedback: muscleFeedback[exercise.muscle_group ?? "Other"]?.pump ?? 3 }),
      })));
      await fetchJSON(`/api/myo/sessions/${myoSessionId}/complete`, { method: "POST" });
      await loadCurrentSession();
    } catch (error) {
      setPageError((error as Error).message);
    } finally {
      setFinishing(false);
    }
  };

  if (loading) return <div className="flex min-h-screen items-center justify-center text-zinc-400">Loading...</div>;

  const historicalOrCompleted = sessionCompleted === 1 || sessionNumber < latestSessionNumber;
  const allLogged = exercises.length > 0 && exercises.every((exercise) => exStates[exercise.id]?.sessionId && totalReps(exStates[exercise.id]) > 0);

  return (
    <main className="mx-auto max-w-xl space-y-4 px-3 pb-24 pt-4">
      <div className="flex items-center justify-between"><div><h1 className="text-lg font-semibold text-zinc-100">Myo Reps</h1><p className="text-xs text-zinc-500">Activation drives weight. Total reps drive workload.</p></div><a href="/straight-sets" className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-400">Straight Sets</a></div>

      <SessionHeader sessionNumber={sessionNumber} completed={sessionCompleted} maxSession={latestSessionNumber} isNavigating={isNavigating} showForward={sessionNumber < latestSessionNumber} onNavigate={navigateSession} />

      {historicalOrCompleted && (
        <div className="flex items-center justify-between rounded-xl border border-zinc-700 bg-zinc-900/50 px-3 py-2">
          <div><p className="text-sm font-medium text-zinc-100">{editingWorkout ? "Editing logged workout" : "Logged workout"}</p><p className="text-xs text-zinc-500">Review every set or correct an entry.</p></div>
          {editingWorkout ? <div className="flex gap-2"><button onClick={cancelEdit} className="rounded-lg bg-zinc-700 px-3 py-2 text-xs text-zinc-200">Cancel</button><button onClick={finishEdit} className="rounded-lg bg-red-600 px-3 py-2 text-xs font-semibold text-white">Done editing</button></div> : <button onClick={beginEdit} className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs font-semibold text-red-300">Edit workout</button>}
        </div>
      )}

      {pageError && <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400">{pageError}</div>}

      {Object.entries(grouped).map(([muscleGroup, muscleExercises]) => {
        const current = muscleExercises.reduce((sum, exercise) => sum + totalReps(exStates[exercise.id]), 0);
        const target = muscleExercises.reduce((sum, exercise) => sum + (exercise.target_total_reps ?? 0), 0) || muscleExercises[0]?.muscle_target_total_reps || 45;
        return (
          <section key={muscleGroup} className="space-y-2">
            <div className="flex items-center gap-2 px-1"><span className="h-2.5 w-2.5 rounded-full bg-red-500"/><span className="text-sm font-semibold text-zinc-100">{muscleGroup}</span><span className="ml-auto text-xs text-zinc-500">{current} / {target} reps</span></div>
            {!historicalOrCompleted && <div className="rounded-xl border border-zinc-700/50 bg-zinc-900/40 p-3"><p className="mb-2 text-xs text-zinc-400">Recovery</p><div className="grid grid-cols-2 gap-1.5">{SORENESS_LABELS.map((label, index) => <button key={label} onClick={() => setSorenessState((previous) => ({ ...previous, [muscleGroup]: index + 1 }))} className={`rounded-lg border px-2.5 py-2 text-left text-xs ${(sorenessState[muscleGroup] ?? 0) === index + 1 ? "border-red-500/60 bg-red-500/20 text-red-100" : "border-zinc-700 bg-zinc-800 text-zinc-300"}`}>{label}</button>)}</div></div>}
            {muscleExercises.map((exercise) => <ExerciseCard key={exercise.id} exercise={exercise} myoSessionId={myoSessionId!} state={exStates[exercise.id]} editable={!historicalOrCompleted || editingWorkout} onChange={(patch) => patchExState(exercise.id, patch)} />)}
          </section>
        );
      })}

      {!historicalOrCompleted && myoSessionId && exercises.length > 0 && <button onClick={finishSession} disabled={finishing || !allLogged} className="h-14 w-full rounded-2xl border border-green-400/30 bg-green-500 font-bold text-zinc-950 disabled:border-zinc-600 disabled:bg-zinc-800 disabled:text-zinc-400">{finishing ? "Finishing..." : allLogged ? "Finish Session" : "Finish Session · log all exercises"}</button>}
    </main>
  );
}
