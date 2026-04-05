"use client";
import { useState, useCallback, useEffect, useRef } from "react";
import type { ExerciseData } from "@/lib/types";
import { SetRow } from "./SetRow";
import { SetCounter } from "./SetCounter";
import { useLogSet } from "@/hooks/useLogSet";

interface DraftSet {
  set_number: number;
  weight: number;
  reps: number;
  logged: boolean;
  saveError?: boolean;
}

function draftStorageKey(sessionId: number, weId: number): string {
  return `draft_sets_${sessionId}_${weId}`;
}

function loadDraft(sessionId: number, weId: number): DraftSet[] | null {
  try {
    const raw = localStorage.getItem(draftStorageKey(sessionId, weId));
    if (!raw) return null;
    return JSON.parse(raw) as DraftSet[];
  } catch {
    return null;
  }
}

function saveDraft(sessionId: number, weId: number, sets: DraftSet[]): void {
  try {
    localStorage.setItem(draftStorageKey(sessionId, weId), JSON.stringify(sets));
  } catch {
    // Storage full or unavailable; ignore.
  }
}

function clearDraft(sessionId: number, weId: number): void {
  try {
    localStorage.removeItem(draftStorageKey(sessionId, weId));
  } catch {
    // Ignore.
  }
}

interface ExerciseSetsProps {
  exercise: ExerciseData;
  sessionId: number;
  targetRir: number;
  disabled: boolean;
  sorenessLocked?: boolean;
  feedbackSummary?: string;
  onAllLogged?: (allLogged: boolean) => void;
}

export function ExerciseSets({
  exercise,
  sessionId,
  targetRir,
  disabled,
  sorenessLocked,
  feedbackSummary,
  onAllLogged,
}: ExerciseSetsProps) {
  const formatWeight = (value: number): string =>
    Number.isInteger(value) ? `${value}` : value.toFixed(1);

  const initSets = (): DraftSet[] => {
    if (exercise.existing_sets.length > 0) {
      clearDraft(sessionId, exercise.we_id);
      return exercise.existing_sets.map((setRow) => ({
        set_number: setRow.set_number,
        weight: setRow.weight ?? 0,
        reps: setRow.reps ?? 0,
        logged: true,
      }));
    }

    const cached = loadDraft(sessionId, exercise.we_id);
    if (cached && cached.length > 0) return cached;

    return exercise.recommendations.map((recommendation) => ({
      set_number: recommendation.set_number,
      weight: recommendation.weight,
      reps: recommendation.reps,
      logged: false,
    }));
  };

  const [sets, setSets] = useState<DraftSet[]>(initSets);
  const [plannedCount, setPlannedCount] = useState(sets.length || exercise.target_sets);
  const [savingSet, setSavingSet] = useState<number | null>(null);
  const [showAllSets, setShowAllSets] = useState(false);

  const isInitialMount = useRef(true);
  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }

    if (sets.every((setRow) => setRow.logged)) {
      clearDraft(sessionId, exercise.we_id);
    } else {
      saveDraft(sessionId, exercise.we_id, sets);
    }
  }, [sets, sessionId, exercise.we_id]);

  const logSet = useLogSet();

  useEffect(() => {
    onAllLogged?.(sets.length > 0 && sets.every((setRow) => setRow.logged));
  }, [sets, onAllLogged]);

  const updateSet = useCallback(
    (setNumber: number, field: "weight" | "reps", value: number) => {
      setSets((prev) =>
        prev.map((setRow) =>
          setRow.set_number === setNumber
            ? { ...setRow, [field]: value, logged: false }
            : setRow
        )
      );
    },
    []
  );

  const handleLog = useCallback(
    (setNumber: number) => {
      setSets((prev) =>
        prev.map((setRow) =>
          setRow.set_number === setNumber ? { ...setRow, saveError: false } : setRow
        )
      );
      setSavingSet(setNumber);

      const updatedSets = sets.map((setRow) =>
        setRow.set_number === setNumber ? { ...setRow, logged: true } : setRow
      );

      logSet.mutate(
        {
          session_id: sessionId,
          workout_exercise_id: exercise.we_id,
          rows: updatedSets
            .filter((setRow) => setRow.logged)
            .map((setRow) => ({
              set_number: setRow.set_number,
              weight: setRow.weight,
              reps: setRow.reps,
              done: true,
              rir: targetRir,
            })),
        },
        {
          onSuccess: () => {
            setSets((prev) =>
              prev.map((setRow) =>
                setRow.set_number === setNumber
                  ? { ...setRow, logged: true, saveError: false }
                  : setRow
              )
            );
            setSavingSet(null);
          },
          onError: () => {
            setSets((prev) =>
              prev.map((setRow) =>
                setRow.set_number === setNumber
                  ? { ...setRow, logged: false, saveError: true }
                  : setRow
              )
            );
            setSavingSet(null);
          },
        }
      );
    },
    [sets, sessionId, exercise.we_id, targetRir, logSet]
  );

  const handleSetCountChange = useCallback((newCount: number) => {
    setPlannedCount(newCount);
    setSets((prev) => {
      if (newCount > prev.length) {
        const lastSet = prev[prev.length - 1];
        const newSets = [...prev];
        for (let i = prev.length + 1; i <= newCount; i++) {
          newSets.push({
            set_number: i,
            weight: lastSet?.weight ?? 0,
            reps: Math.max((lastSet?.reps ?? 10) - 1, 5),
            logged: false,
          });
        }
        return newSets;
      }

      return prev.slice(0, newCount);
    });
  }, []);

  const allLogged = sets.length > 0 && sets.every((setRow) => setRow.logged);
  const activeSet = sets.find((setRow) => !setRow.logged) ?? sets[sets.length - 1] ?? null;
  const hasRecentFeedback = !!feedbackSummary && feedbackSummary !== "No recent feedback";
  const lastSessionLabel = exercise.last_session_summary
    ? `Prev ${formatWeight(exercise.last_session_summary.last_weight)} lb, ${exercise.last_session_summary.avg_reps} avg reps, ${exercise.last_session_summary.set_count} sets, RIR ${exercise.last_session_summary.recommended_rir}`
    : null;

  return (
    <section className="rounded-2xl border border-white/8 bg-white/4 p-3 shadow-[0_12px_30px_rgba(0,0,0,0.2)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-zinc-100">{exercise.name}</h3>
            {exercise.is_finisher && (
              <span className="rounded-full border border-white/10 px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] text-zinc-400">
                Finisher
              </span>
            )}
          </div>
        </div>

        {!exercise.is_finisher && !disabled && !sorenessLocked ? (
          <SetCounter
            count={plannedCount}
            onChange={handleSetCountChange}
            min={1}
            max={10}
          />
        ) : (
          <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1.5 text-[11px] font-medium uppercase tracking-[0.16em] text-zinc-300">
            {plannedCount} sets
          </span>
        )}
      </div>

      {(hasRecentFeedback || lastSessionLabel) && (
        <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-zinc-300">
          {hasRecentFeedback && (
            <span className="rounded-full border border-white/8 bg-black/20 px-2.5 py-1">
              Recent: {feedbackSummary}
            </span>
          )}
          {lastSessionLabel && (
            <span className="rounded-full border border-white/8 bg-black/20 px-2.5 py-1">
              {lastSessionLabel}
            </span>
          )}
        </div>
      )}

      {logSet.isError && (
        <p className="mt-2 text-xs text-red-300">
          Failed to save. Tap Log again to retry.
        </p>
      )}

      {exercise.weight_recommendation && (
        <p className="mt-2 rounded-xl border border-amber-400/20 bg-amber-400/8 px-3 py-2 text-xs text-amber-200">
          {exercise.weight_recommendation.message}
          {exercise.weight_recommendation.context_note
            ? `. ${exercise.weight_recommendation.context_note}`
            : ""}
        </p>
      )}

      {!allLogged && activeSet && (
        <div className="mt-3">
          <SetRow
            setNumber={activeSet.set_number}
            weight={activeSet.weight}
            reps={activeSet.reps}
            logged={activeSet.logged}
            pending={savingSet === activeSet.set_number}
            saveError={!!activeSet.saveError}
            disabled={disabled}
            sorenessLocked={sorenessLocked}
            highlight
            onWeightChange={(value) => updateSet(activeSet.set_number, "weight", value)}
            onRepsChange={(value) => updateSet(activeSet.set_number, "reps", value)}
            onLog={() => handleLog(activeSet.set_number)}
          />
        </div>
      )}

      <div className="mt-3 flex items-center justify-end border-t border-white/8 pt-3">
        <button
          type="button"
          onClick={() => setShowAllSets((prev) => !prev)}
          className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-medium text-zinc-300 transition-colors hover:border-white/20 hover:text-white"
        >
          {showAllSets ? "Hide full session" : "Show full session"}
        </button>
      </div>

      {showAllSets && (
        <div className="mt-3 space-y-1.5 rounded-2xl border border-white/8 bg-black/15 p-2.5">
          {sets.map((setRow) => (
            <SetRow
              key={setRow.set_number}
              setNumber={setRow.set_number}
              weight={setRow.weight}
              reps={setRow.reps}
              logged={setRow.logged}
              pending={savingSet === setRow.set_number}
              saveError={!!setRow.saveError}
              disabled={disabled}
              sorenessLocked={sorenessLocked}
              highlight={!setRow.logged && setRow.set_number === activeSet?.set_number}
              onWeightChange={(value) => updateSet(setRow.set_number, "weight", value)}
              onRepsChange={(value) => updateSet(setRow.set_number, "reps", value)}
              onLog={() => handleLog(setRow.set_number)}
            />
          ))}
        </div>
      )}
    </section>
  );
}
