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
    // Storage full or unavailable — ignore
  }
}

function clearDraft(sessionId: number, weId: number): void {
  try {
    localStorage.removeItem(draftStorageKey(sessionId, weId));
  } catch {
    // Ignore
  }
}

interface ExerciseSetsProps {
  exercise: ExerciseData;
  sessionId: number;
  targetRir: number;
  disabled: boolean;
  sorenessLocked?: boolean;
  onAllLogged?: (allLogged: boolean) => void;
}

export function ExerciseSets({
  exercise,
  sessionId,
  targetRir,
  disabled,
  sorenessLocked,
  onAllLogged,
}: ExerciseSetsProps) {
  const formatWeight = (value: number): string =>
    Number.isInteger(value) ? `${value}` : value.toFixed(1);

  // Initialize draft from localStorage, existing sets, or recommendations
  const initSets = (): DraftSet[] => {
    // If sets already saved to server, use those (source of truth)
    if (exercise.existing_sets.length > 0) {
      clearDraft(sessionId, exercise.we_id);
      return exercise.existing_sets.map((s) => ({
        set_number: s.set_number,
        weight: s.weight ?? 0,
        reps: s.reps ?? 0,
        logged: true,
      }));
    }
    // Restore unsaved draft from localStorage
    const cached = loadDraft(sessionId, exercise.we_id);
    if (cached && cached.length > 0) return cached;
    // Fall back to recommendations
    return exercise.recommendations.map((r) => ({
      set_number: r.set_number,
      weight: r.weight,
      reps: r.reps,
      logged: false,
    }));
  };

  const [sets, setSets] = useState<DraftSet[]>(initSets);
  const [plannedCount, setPlannedCount] = useState(
    sets.length || exercise.target_sets
  );
  const [savingSet, setSavingSet] = useState<number | null>(null);

  // Persist draft to localStorage whenever sets change
  const isInitialMount = useRef(true);
  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }
    // Only save drafts with unlogged sets; clear when all are logged
    if (sets.every((s) => s.logged)) {
      clearDraft(sessionId, exercise.we_id);
    } else {
      saveDraft(sessionId, exercise.we_id, sets);
    }
  }, [sets, sessionId, exercise.we_id]);

  const logSet = useLogSet();

  useEffect(() => {
    onAllLogged?.(sets.length > 0 && sets.every((s) => s.logged));
  }, [sets, onAllLogged]);

  const updateSet = useCallback(
    (setNumber: number, field: "weight" | "reps", value: number) => {
      setSets((prev) =>
        prev.map((s) =>
          s.set_number === setNumber
            ? { ...s, [field]: value, logged: false }
            : s
        )
      );
    },
    []
  );

  const handleLog = useCallback(
    (setNumber: number) => {
      // Clear any previous error for this set, begin saving
      setSets((prev) =>
        prev.map((s) =>
          s.set_number === setNumber ? { ...s, saveError: false } : s
        )
      );
      setSavingSet(setNumber);

      // Compute the rows to send (treat this set as logged, keep others as-is)
      const updatedSets = sets.map((s) =>
        s.set_number === setNumber ? { ...s, logged: true } : s
      );

      logSet.mutate(
        {
          session_id: sessionId,
          workout_exercise_id: exercise.we_id,
          rows: updatedSets
            .filter((s) => s.logged)
            .map((s) => ({
              set_number: s.set_number,
              weight: s.weight,
              reps: s.reps,
              done: true,
              rir: targetRir,
            })),
        },
        {
          onSuccess: () => {
            setSets((prev) =>
              prev.map((s) =>
                s.set_number === setNumber
                  ? { ...s, logged: true, saveError: false }
                  : s
              )
            );
            setSavingSet(null);
          },
          onError: () => {
            setSets((prev) =>
              prev.map((s) =>
                s.set_number === setNumber
                  ? { ...s, logged: false, saveError: true }
                  : s
              )
            );
            setSavingSet(null);
          },
        }
      );
    },
    [sets, sessionId, exercise.we_id, targetRir, logSet]
  );

  const handleSetCountChange = useCallback(
    (newCount: number) => {
      setPlannedCount(newCount);
      setSets((prev) => {
        if (newCount > prev.length) {
          // Add sets
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
        // Remove sets (only unlogged ones from the end)
        return prev.slice(0, newCount);
      });
    },
    []
  );

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-sm">
          {exercise.name}
          {exercise.is_finisher && (
            <span className="ml-1.5 text-xs text-zinc-500">(finisher)</span>
          )}
        </h3>
        {!exercise.is_finisher && !disabled && !sorenessLocked && (
          <SetCounter
            count={plannedCount}
            onChange={handleSetCountChange}
            min={1}
            max={10}
          />
        )}
      </div>

      {exercise.last_session_summary && (
        <p className="text-xs text-zinc-400 mb-1.5">
          Last time: {formatWeight(exercise.last_session_summary.last_weight)} lb
          {" · "}avg {exercise.last_session_summary.avg_reps} reps{" · "}RIR{" "}
          {exercise.last_session_summary.recommended_rir}
        </p>
      )}

      {logSet.isError && (
        <p className="text-xs text-red-400 mb-1">
          Failed to save — tap Log again to retry
        </p>
      )}

      {exercise.weight_recommendation && (
        <p className="text-xs text-yellow-400 mb-1">
          {exercise.weight_recommendation.message}
          {exercise.weight_recommendation.context_note
            ? `. ${exercise.weight_recommendation.context_note}`
            : ""}
        </p>
      )}

      <div className="space-y-1.5">
        {sets.map((set) => (
          <SetRow
            key={set.set_number}
            setNumber={set.set_number}
            weight={set.weight}
            reps={set.reps}
            logged={set.logged}
            pending={savingSet === set.set_number}
            saveError={!!set.saveError}
            disabled={disabled}
            sorenessLocked={sorenessLocked}
            onWeightChange={(v) => updateSet(set.set_number, "weight", v)}
            onRepsChange={(v) => updateSet(set.set_number, "reps", v)}
            onLog={() => handleLog(set.set_number)}
          />
        ))}
      </div>
    </div>
  );
}
