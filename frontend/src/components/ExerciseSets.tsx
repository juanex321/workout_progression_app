"use client";
import { useState, useCallback, useEffect } from "react";
import type { ExerciseData } from "@/lib/types";
import { SetRow } from "./SetRow";
import { SetCounter } from "./SetCounter";
import { useLogSet } from "@/hooks/useLogSet";

interface DraftSet {
  set_number: number;
  weight: number;
  reps: number;
  logged: boolean;
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
  // Initialize draft from existing sets or recommendations
  const initSets = (): DraftSet[] => {
    if (exercise.existing_sets.length > 0) {
      return exercise.existing_sets.map((s) => ({
        set_number: s.set_number,
        weight: s.weight ?? 0,
        reps: s.reps ?? 0,
        logged: true,
      }));
    }
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
      setSets((prev) =>
        prev.map((s) =>
          s.set_number === setNumber ? { ...s, logged: true } : s
        )
      );

      // Get the current sets including the newly logged one
      const updatedSets = sets.map((s) =>
        s.set_number === setNumber ? { ...s, logged: true } : s
      );

      // Save all logged sets to DB
      logSet.mutate({
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
      });
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

  const suggestIncrease = exercise.recommendations[0]?.suggest_weight_increase;

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

      {suggestIncrease && (
        <p className="text-xs text-yellow-400 mb-1">
          Consider increasing weight
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
