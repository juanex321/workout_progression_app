"use client";
import { useEffect, useState } from "react";

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
  session: { session_id: number; date: string; completed: number };
  straight_session_id: number;
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
const ACTIVATION_LOW = 10;
const ACTIVATION_HIGH = 20;

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text.trimStart().startsWith("<") ? `Server error (${res.status})` : `${res.status}: ${text.slice(0, 200)}`);
  }
  return res.json();
}

function toInt(value: string): number {
  const n = parseInt(value);
  return Number.isFinite(n) ? n : 0;
}

function miniTotal(state?: ExerciseState): number {
  return state?.miniSets.reduce((sum, set) => sum + set.reps, 0) ?? 0;
}

function totalReps(state?: ExerciseState): number {
  if (!state) return 0;
  return (state.loggedActivationReps ?? 0) + miniTotal(state);
}

function progressPercent(current: number, target: number): number {
  return target > 0 ? Math.min((current / target) * 100, 100) : 0;
}

function RepProgress({ current, target }: { current: number; target: number }) {
  const remaining = Math.max(target - current, 0);
  return (
    <div className="rounded-xl border border-zinc-700/50 bg-zinc-900/50 px-3 py-3 space-y-2">
      <div className="flex items-center justify-between text-xs">
        <span className="text-zinc-400">Rep budget</span>
        <span className="font-semibold text-zinc-100">{current} / {target}</span>
      </div>
      <div className="h-2 rounded-full bg-zinc-700 overflow-hidden">
        <div className="h-2 rounded-full bg-red-500 transition-all" style={{ width: `${progressPercent(current, target)}%` }} />
      </div>
      <p className="text-[11px] text-zinc-500">
        {remaining > 0 ? `${remaining} reps remaining` : "Target reached. Stop here unless it still feels too easy."}
      </p>
    </div>
  );
}

function SorenessBlock({ muscleGroup, value, onChange }: { muscleGroup: string; value: number | null; onChange: (v: number) => void }) {
  const [expanded, setExpanded] = useState(value === null);
  if (!expanded && value !== null) {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-zinc-700/50 bg-zinc-900/40 px-3 py-2 text-xs">
        <span className="text-zinc-500">Recovery:</span>
        <span className="font-medium text-zinc-200">{SORENESS_LABELS[value - 1]}</span>
        <button onClick={() => setExpanded(true)} className="ml-auto text-zinc-500 underline underline-offset-2 hover:text-zinc-300">edit</button>
      </div>
    );
  }
  return (
    <div className="rounded-xl border border-zinc-700/50 bg-zinc-900/40 p-3">
      <p className="text-xs font-medium text-zinc-300 mb-2">How did {muscleGroup} recover?</p>
      <div className="grid grid-cols-2 gap-1.5">
        {SORENESS_LABELS.map((label, i) => {
          const v = i + 1;
          return (
            <button key={label} onClick={() => { onChange(v); setExpanded(false); }} className={`rounded-lg border px-2.5 py-2 text-left text-xs ${v === value ? "border-red-500/60 bg-red-500/20 text-red-100" : "border-zinc-700 bg-zinc-800 text-zinc-300"}`}>
              {label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function MuscleFeedbackBlock({ muscleGroup, feedback, onChange, onSubmit }: {
  muscleGroup: string;
  feedback: MuscleFeedbackState;
  onChange: (patch: Partial<MuscleFeedbackState>) => void;
  onSubmit: () => void;
}) {
  return (
    <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 space-y-3">
      {feedback.error && <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-3 py-2 text-xs text-red-300">{feedback.error}</div>}
      <p className="text-sm font-semibold text-zinc-100">{muscleGroup} feedback</p>
      <div className="space-y-1.5">
        <p className="text-xs text-zinc-400">How was the workload?</p>
        <div className="flex gap-1">
          {WORKLOAD_LABELS.map((label, i) => {
            const v = i + 1;
            return <button key={label} onClick={() => onChange({ workload: v })} className={`flex-1 py-2 rounded-lg text-xs font-medium ${feedback.workload === v ? "bg-red-600 text-white" : "bg-zinc-700 text-zinc-300"}`}>{label}</button>;
          })}
        </div>
      </div>
      <div className="space-y-1.5">
        <p className="text-xs text-zinc-400">How was the pump?</p>
        <div className="flex gap-1">
          {PUMP_LABELS.map((label, i) => {
            const v = i + 1;
            return <button key={label} onClick={() => onChange({ pump: v })} className={`flex-1 py-2 rounded-lg text-xs font-medium ${feedback.pump === v ? "bg-red-600 text-white" : "bg-zinc-700 text-zinc-300"}`}>{label}</button>;
          })}
        </div>
      </div>
      <button onClick={onSubmit} disabled={feedback.submitting} className="w-full h-10 rounded-lg bg-red-600 text-white text-sm font-medium disabled:opacity-50">
        {feedback.submitting ? "Saving..." : "Submit muscle feedback"}
      </button>
    </div>
  );
}

function ExerciseCard({ exercise, myoSessionId, state, onChange }: {
  exercise: TodayExercise;
  myoSessionId: number;
  state: ExerciseState;
  onChange: (patch: Partial<ExerciseState>) => void;
}) {
  const { stage, sessionId, weight, reps, loggedActivationReps, miniSets, miniRepsInput, submitting, error } = state;
  const target = exercise.target_total_reps ?? exercise.muscle_target_total_reps ?? 45;
  const activationInput = toInt(reps);
  const activationLogged = loggedActivationReps ?? 0;
  const current = totalReps(state);
  const minis = miniTotal(state);
  const lastMini = miniSets.at(-1)?.reps ?? null;

  const logActivation = async () => {
    if (activationInput < 1) {
      onChange({ error: "Enter activation reps" });
      return;
    }
    onChange({ submitting: true, error: "" });
    try {
      const es = await fetchJSON<ExistingExerciseSession>("/api/myo/exercise-sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          myo_session_id: myoSessionId,
          exercise_id: exercise.id,
          activation_weight: weight ? parseFloat(weight) : null,
          activation_reps: activationInput,
        }),
      });
      onChange({
        sessionId: es.exercise_session_id,
        stage: es.completed === 1 ? "done" : "mini",
        miniSets: es.mini_sets,
        weight: es.activation_weight != null ? String(es.activation_weight) : weight,
        reps: es.activation_reps != null ? String(es.activation_reps) : reps,
        loggedActivationReps: es.activation_reps ?? activationInput,
        workload: es.workload_feedback ?? 3,
        submitting: false,
      });
    } catch (e) {
      onChange({ error: (e as Error).message, submitting: false });
    }
  };

  const logMiniSet = async () => {
    if (!sessionId) {
      onChange({ error: "Log activation first" });
      return;
    }
    const parsed = parseInt(miniRepsInput);
    if (!parsed || parsed < 1) {
      onChange({ error: "Enter mini-set reps" });
      return;
    }
    onChange({ submitting: true, error: "" });
    try {
      const es = await fetchJSON<ExistingExerciseSession>(`/api/myo/exercise-sessions/${sessionId}/miniset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reps: parsed }),
      });
      onChange({ miniSets: es.mini_sets, miniRepsInput: "", submitting: false });
    } catch (e) {
      onChange({ error: (e as Error).message, submitting: false });
    }
  };

  return (
    <div className="rounded-xl border border-zinc-700 bg-zinc-800/60 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-700/60">
        <div>
          <span className="font-medium text-zinc-100">{exercise.name}</span>
          <span className="ml-2 text-[10px] uppercase tracking-wider text-zinc-500">{exercise.exercise_role === "finisher" ? "Finisher" : "Main"}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-400">{target} reps</span>
          {!exercise.calibrated && <span className="text-xs bg-red-500/20 text-red-400 border border-red-500/30 px-2 py-0.5 rounded">Cal {exercise.calibration_session}/3</span>}
          {stage === "ready" && <span className="text-xs bg-yellow-500/20 text-yellow-300 border border-yellow-500/30 px-2 py-0.5 rounded">Logged</span>}
          {stage === "done" && <span className="text-xs bg-green-500/20 text-green-400 border border-green-500/30 px-2 py-0.5 rounded">Done</span>}
        </div>
      </div>

      <div className="px-4 py-3 space-y-3">
        {error && <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-3 py-2 text-xs text-red-400">{error}</div>}

        {(exercise.last_weight || exercise.last_reps || exercise.last_total_reps != null || exercise.last_mini_sets != null) && stage !== "done" && (
          <div className="rounded-lg bg-zinc-900/70 border border-zinc-700/40 px-3 py-2.5 flex items-center justify-between">
            <div>
              <p className="text-[10px] uppercase tracking-widest text-zinc-500">Last session</p>
              <p className="text-sm font-semibold text-zinc-100">
                {exercise.last_weight ? `${exercise.last_weight}` : ""}{exercise.last_weight && exercise.last_reps ? " × " : ""}{exercise.last_reps ? `${exercise.last_reps} activation` : ""}
              </p>
            </div>
            {(exercise.last_total_reps ?? exercise.last_mini_sets) != null && (
              <div className="text-right">
                <span className="text-2xl font-bold text-red-400 leading-none">{exercise.last_total_reps ?? exercise.last_mini_sets}</span>
                <p className="text-[10px] text-zinc-500 mt-0.5">total reps</p>
              </div>
            )}
          </div>
        )}

        {stage === "idle" && (
          <div className="space-y-3">
            <p className="text-xs text-zinc-400 uppercase tracking-wide">Activation set — hard set</p>
            <div className="flex gap-2">
              <div className="flex-1">
                <label className="text-xs text-zinc-500 block mb-1">Weight</label>
                <input type="number" value={weight} onChange={(e) => onChange({ weight: e.target.value })} placeholder={exercise.last_weight ? String(exercise.last_weight) : "—"} className="w-full bg-zinc-700/80 rounded-lg px-3 py-2 text-sm text-zinc-100 outline-none focus:ring-1 focus:ring-red-500" />
              </div>
              <div className="flex-1">
                <label className="text-xs text-zinc-500 block mb-1">Reps</label>
                <input type="number" value={reps} onChange={(e) => onChange({ reps: e.target.value })} placeholder={exercise.last_reps ? String(exercise.last_reps) : "0"} className="w-full bg-zinc-700/80 rounded-lg px-3 py-2 text-sm text-zinc-100 outline-none focus:ring-1 focus:ring-red-500" />
              </div>
              <div className="flex items-end"><button onClick={logActivation} disabled={submitting} className="h-9 px-4 rounded-lg bg-red-600 text-white text-sm font-medium disabled:opacity-50">{submitting ? "..." : "Log"}</button></div>
            </div>
          </div>
        )}

        {stage === "mini" && (
          <div className="space-y-3">
            <RepProgress current={current} target={target} />
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div className="rounded-lg bg-zinc-900/60 border border-zinc-700/50 px-2 py-2"><p className="text-zinc-500">Activation</p><p className="font-semibold text-zinc-100">{weight || exercise.last_weight} × {activationLogged}</p></div>
              <div className="rounded-lg bg-zinc-900/60 border border-zinc-700/50 px-2 py-2"><p className="text-zinc-500">Mini reps</p><p className="font-semibold text-zinc-100">{minis}</p></div>
              <div className="rounded-lg bg-zinc-900/60 border border-zinc-700/50 px-2 py-2"><p className="text-zinc-500">Total</p><p className="font-semibold text-zinc-100">{current}</p></div>
            </div>
            {activationLogged > ACTIVATION_HIGH && <p className="text-xs text-green-400">Activation was above {ACTIVATION_HIGH}; consider increasing weight next time.</p>}
            {activationLogged > 0 && activationLogged < ACTIVATION_LOW && <p className="text-xs text-orange-400">Activation was below {ACTIVATION_LOW}; weight may be too high today.</p>}
            {miniSets.length > 0 && <div className="grid grid-cols-6 gap-1">{miniSets.map((ms) => <div key={ms.order_index} className={`text-center py-1.5 rounded text-xs font-medium ${ms.reps < MIN_REPS_FLOOR ? "bg-red-500/15 text-red-400" : "bg-zinc-700/80 text-zinc-300"}`}>{ms.reps}</div>)}</div>}
            {lastMini !== null && lastMini < MIN_REPS_FLOOR && <p className="text-xs text-orange-400">Dropped below {MIN_REPS_FLOOR} reps — stop here.</p>}
            <div className="flex gap-2">
              <input type="number" value={miniRepsInput} onChange={(e) => onChange({ miniRepsInput: e.target.value })} onKeyDown={(e) => e.key === "Enter" && logMiniSet()} placeholder="Mini-set reps" className="flex-1 bg-zinc-700/80 rounded-lg px-3 py-2 text-sm text-zinc-100 outline-none focus:ring-1 focus:ring-red-500" />
              <button onClick={logMiniSet} disabled={submitting} className="px-4 h-10 rounded-lg bg-zinc-600 text-zinc-100 text-sm font-medium disabled:opacity-50">{submitting ? "..." : "Add"}</button>
            </div>
            <button onClick={() => onChange({ stage: "ready" })} disabled={miniSets.length === 0} className={`w-full h-10 rounded-lg text-sm font-medium disabled:opacity-50 ${current >= target ? "bg-red-600 text-white" : "bg-zinc-700 text-zinc-400"}`}>{current >= target ? `Exercise logged — ${current} reps` : `Log exercise · ${current} of ${target}`}</button>
          </div>
        )}

        {stage === "ready" && (
          <div className="space-y-2">
            <RepProgress current={current} target={target} />
            <div className="flex items-center justify-between text-sm text-zinc-400"><span>{weight || exercise.last_weight} × {activationLogged} activation</span><span>{minis} mini reps</span></div>
            <button onClick={() => onChange({ stage: "mini" })} className="text-xs text-zinc-500 underline underline-offset-2">Add more reps</button>
          </div>
        )}

        {stage === "done" && (
          <div className="space-y-2">
            <RepProgress current={current} target={target} />
            <div className="flex items-center justify-between text-sm text-zinc-400"><span>{weight || exercise.last_weight} × {activationLogged} activation</span><span>{minis} mini reps</span></div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function MyoRepsPage() {
  const [exercises, setExercises] = useState<TodayExercise[]>([]);
  const [loading, setLoading] = useState(true);
  const [myoSessionId, setMyoSessionId] = useState<number | null>(null);
  const [straightSessionId, setStraightSessionId] = useState<number | null>(null);
  const [pageError, setPageError] = useState("");
  const [exStates, setExStates] = useState<Record<number, ExerciseState>>({});
  const [sorenessState, setSorenessState] = useState<Record<string, number | null>>({});
  const [muscleFeedback, setMuscleFeedback] = useState<Record<string, MuscleFeedbackState>>({});
  const [sessionDone, setSessionDone] = useState(false);
  const [finishing, setFinishing] = useState(false);

  const patchExState = (exerciseId: number, patch: Partial<ExerciseState>) => {
    setExStates((prev) => ({ ...prev, [exerciseId]: { ...prev[exerciseId], ...patch } }));
  };

  const patchMuscleFeedback = (muscleGroup: string, patch: Partial<MuscleFeedbackState>) => {
    setMuscleFeedback((prev) => ({
      ...prev,
      [muscleGroup]: { ...(prev[muscleGroup] ?? { workload: 3, pump: 3, submitting: false, error: "" }), ...patch },
    }));
  };

  useEffect(() => {
    async function init() {
      try {
        const payload = await fetchJSON<BootstrapPayload>("/api/myo/current");
        setMyoSessionId(payload.session.session_id);
        setStraightSessionId(payload.straight_session_id);
        setExercises(payload.exercises);
        const existingByExerciseId = new Map<number, ExistingExerciseSession>();
        for (const es of payload.exercise_sessions) existingByExerciseId.set(es.exercise_id, es);
        const initial: Record<number, ExerciseState> = {};
        for (const ex of payload.exercises) {
          const existing = existingByExerciseId.get(ex.id);
          initial[ex.id] = {
            stage: existing?.completed === 1 ? "done" : existing?.activation_reps != null ? "mini" : "idle",
            sessionId: existing?.exercise_session_id ?? null,
            weight: existing?.activation_weight != null ? String(existing.activation_weight) : ex.last_weight != null ? String(ex.last_weight) : "",
            reps: existing?.activation_reps != null ? String(existing.activation_reps) : ex.last_reps != null ? String(ex.last_reps) : "",
            loggedActivationReps: existing?.activation_reps ?? null,
            miniSets: existing?.mini_sets ?? [],
            miniRepsInput: "",
            workload: existing?.workload_feedback ?? 3,
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

  const grouped: Record<string, TodayExercise[]> = {};
  const orderedGroups: string[] = [];
  for (const ex of exercises) {
    const mg = ex.muscle_group ?? "Other";
    if (!grouped[mg]) { grouped[mg] = []; orderedGroups.push(mg); }
    grouped[mg].push(ex);
  }

  const submitMuscleFeedback = async (muscleGroup: string, muscleExercises: TodayExercise[]) => {
    const feedback = muscleFeedback[muscleGroup] ?? { workload: 3, pump: 3, submitting: false, error: "" };
    patchMuscleFeedback(muscleGroup, { submitting: true, error: "" });
    try {
      const readyExercises = muscleExercises.filter((ex) => exStates[ex.id]?.stage === "ready" && exStates[ex.id]?.sessionId);
      await Promise.all(readyExercises.map((ex) => fetchJSON(`/api/myo/exercise-sessions/${exStates[ex.id].sessionId}/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workload_feedback: feedback.workload }),
      })));

      if (straightSessionId) {
        await fetchJSON("/api/feedback/muscle-group", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: straightSessionId,
            muscle_group: muscleGroup,
            soreness: sorenessState[muscleGroup] ?? 3,
            pump: feedback.pump,
            workload: feedback.workload,
          }),
        });
      }

      for (const ex of readyExercises) {
        patchExState(ex.id, { stage: "done", workload: feedback.workload });
      }
      patchMuscleFeedback(muscleGroup, { submitting: false });
    } catch (e) {
      patchMuscleFeedback(muscleGroup, { error: (e as Error).message, submitting: false });
    }
  };

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

  if (loading) return <div className="flex items-center justify-center min-h-screen"><p className="text-zinc-400">Loading...</p></div>;

  return (
    <main className="mx-auto max-w-xl px-3 pb-24 pt-4 space-y-4">
      <div className="flex items-center justify-between">
        <div><h1 className="text-lg font-semibold text-zinc-100">Myo Reps</h1><p className="text-xs text-zinc-500">Activation drives weight. Total reps drive workload.</p></div>
        <a href="/straight-sets" className="text-xs text-zinc-400 border border-zinc-700 rounded-lg px-3 py-1.5 hover:border-red-600 hover:text-red-500 transition-colors">Straight Sets</a>
      </div>

      {pageError && <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-3 py-2 text-xs text-red-400">{pageError}</div>}
      {sessionDone && <div className="rounded-xl border border-green-500/30 bg-green-500/10 px-4 py-4 text-center"><p className="text-green-400 font-semibold">Session complete!</p><p className="text-xs text-zinc-400 mt-1">Rotation advanced.</p></div>}

      {!sessionDone && myoSessionId && orderedGroups.map((mg) => {
        const muscleExercises = grouped[mg];
        const current = muscleExercises.reduce((sum, ex) => sum + totalReps(exStates[ex.id]), 0);
        const target = muscleExercises.reduce((sum, ex) => sum + (ex.target_total_reps ?? 0), 0) || muscleExercises[0]?.muscle_target_total_reps || 45;
        const muscleReady = muscleExercises.every((ex) => ["ready", "done"].includes(exStates[ex.id]?.stage));
        const muscleDone = muscleExercises.every((ex) => exStates[ex.id]?.stage === "done");
        const feedback = muscleFeedback[mg] ?? { workload: 3, pump: 3, submitting: false, error: "" };
        return (
          <div key={mg} className="space-y-2">
            <div className="flex items-center gap-2 px-1"><span className="w-2.5 h-2.5 rounded-full bg-red-500 shrink-0" /><span className="text-sm font-semibold text-zinc-100">{mg}</span><span className="ml-auto text-xs text-zinc-500">{current} / {target} reps</span></div>
            <RepProgress current={current} target={target} />
            <SorenessBlock muscleGroup={mg} value={sorenessState[mg] ?? null} onChange={(v) => setSorenessState((prev) => ({ ...prev, [mg]: v }))} />
            {muscleExercises.map((ex) => <ExerciseCard key={ex.id} exercise={ex} myoSessionId={myoSessionId} state={exStates[ex.id] ?? { stage: "idle", sessionId: null, weight: "", reps: "", loggedActivationReps: null, miniSets: [], miniRepsInput: "", workload: 3, submitting: false, error: "" }} onChange={(patch) => patchExState(ex.id, patch)} />)}
            {muscleReady && !muscleDone && <MuscleFeedbackBlock muscleGroup={mg} feedback={feedback} onChange={(patch) => patchMuscleFeedback(mg, patch)} onSubmit={() => submitMuscleFeedback(mg, muscleExercises)} />}
          </div>
        );
      })}

      {!sessionDone && myoSessionId && totalCount > 0 && <div className="pt-2"><button onClick={finishSession} disabled={finishing || !allDone} className={`w-full h-14 rounded-2xl border font-bold text-base transition-colors disabled:opacity-50 ${allDone ? "border-green-400/30 bg-green-500 text-zinc-950" : "border-zinc-600 bg-zinc-800 text-zinc-300"}`}>{finishing ? "Finishing..." : allDone ? "Finish Session" : `Finish Session · ${doneCount} / ${totalCount} done`}</button></div>}
    </main>
  );
}
