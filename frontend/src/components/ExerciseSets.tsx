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
    const cached = loadDraft(sessionId, exercise.we_id);
    const existingMap = new Map(
      exercise.existing_sets.map((setRow) => [
        setRow.set_number,
        {
          set_number: setRow.set_number,
          weight: setRow.weight ?? 0,
          reps: setRow.reps ?? 0,
          logged: true,
        } satisfies DraftSet,
      ])
    );

    const mergedRecommendations = exercise.recommendations.map((recommendation) => {
      const existing = existingMap.get(recommendation.set_number);
      return (
        existing ?? {
          set_number: recommendation.set_number,
          weight: recommendation.weight,
          reps: recommendation.reps,
          logged: false,
        }
      );
    });

    const recommendationNumbers = new Set(
      exercise.recommendations.map((recommendation) => recommendation.set_number)
    );
    const extraLoggedSets = exercise.existing_sets
      .filter((setRow) => !recommendationNumbers.has(setRow.set_number))
      .map((setRow) => ({
        set_number: setRow.set_number,
        weight: setRow.weight ?? 0,
        reps: setRow.reps ?? 0,
        logged: true,
      }));

    const baseSets =
      mergedRecommendations.length > 0
        ? [...mergedRecommendations, ...extraLoggedSets].sort(
            (a, b) => a.set_number - b.set_number
          )
        : exercise.existing_sets.length > 0
          ? exercise.existing_sets.map((setRow) => ({
              set_number: setRow.set_number,
              weight: setRow.weight ?? 0,
              reps: setRow.reps ?? 0,
              logged: true,
            }))
          : exercise.recommendations.map((recommendation) => ({
              set_number: recommendation.set_number,
              weight: recommendation.weight,
              reps: recommendation.reps,
              logged: false,
            }));

    if (!cached || cached.length === 0) {
      return baseSets;
    }

    const cachedMap = new Map(cached.map((setRow) => [setRow.set_number, setRow]));
    const mergedWithDraft = baseSets.map((setRow) => {
      const draftSet = cachedMap.get(setRow.set_number);
      if (!draftSet || setRow.logged) return setRow;
      return {
        ...setRow,
        weight: draftSet.weight,
        reps: draftSet.reps,
        saveError: draftSet.saveError,
      };
    });

    const existingNumbers = new Set(mergedWithDraft.map((setRow) => setRow.set_number));
    const extraDraftSets = cached.filter((setRow) => !existingNumbers.has(setRow.set_number));

    return [...mergedWithDraft, ...extraDraftSets].sort(
      (a, b) => a.set_number - b.set_number
    );
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

      // Capture the logged set's values before the mutation so we can propagate them
      const loggedSet = sets.find((s) => s.set_number === setNumber);
      const loggedWeight = loggedSet?.weight ?? 0;
      const loggedReps = loggedSet?.reps ?? 0;

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
            setSets((prev) => {
              const marked = prev.map((setRow) =>
                setRow.set_number === setNumber
                  ? { ...setRow, logged: true, saveError: false }
                  : setRow
              );
              // Propagate weight and recalculate reps for all subsequent unlogged sets
              return marked.map((setRow) => {
                if (!setRow.logged && setRow.set_number > setNumber) {
                  return {
                    ...setRow,
                    weight: loggedWeight,
                    reps: Math.max(5, loggedReps - (setRow.set_number - setNumber)),
                  };
                }
                return setRow;
              });
            });
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
    const loggedCount = sets.filter((setRow) => setRow.logged).length;
    const cappedCount = Math.max(
      loggedCount,
      Math.min(Math.max(newCount, exercise.min_sets), exercise.max_sets)
    );
    setPlannedCount(cappedCount);
    setSets((prev) => {
      if (cappedCount > prev.length) {
        const lastSet = prev[prev.length - 1];
        const newSets = [...prev];
        for (let i = prev.length + 1; i <= cappedCount; i++) {
          newSets.push({
            set_number: i,
            weight: lastSet?.weight ?? 0,
            reps: Math.max((lastSet?.reps ?? 10) - 1, 5),
            logged: false,
          });
        }
        return newSets;
      }

      return prev.slice(0, cappedCount);
    });
  }, [sets, exercise.min_sets, exercise.max_sets]);

  const allLogged = sets.length > 0 && sets.every((setRow) => setRow.logged);
  const activeSet = sets.find((setRow) => !setRow.logged) ?? sets[sets.length - 1] ?? null;
  const hasRecentFeedback = !!feedbackSummary && feedbackSummary !== "No recent feedback";
  const lastSessionLabel = exercise.last_session_summary
    ? [
        `Last ${formatWeight(exercise.last_session_summary.last_weight)} lb`,
        `${exercise.last_session_summary.avg_reps} avg reps`,
        typeof exercise.last_session_summary.set_count === "number"
          ? `${exercise.last_session_summary.set_count} sets`
          : null,
        `RIR ${exercise.last_session_summary.recommended_rir}`,
      ]
        .filter(Boolean)
        .join(", ")
    : null;

  return (
    <section className="rounded-2xl border border-white/12 bg-zinc-900/70 p-3 shadow-[0_12px_30px_rgba(0,0,0,0.2)]">
      <div className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-3">
        <div className="min-w-0 flex items-center self-center">
          <div className="flex min-w-0 items-center gap-2">
            <h3 className="text-sm font-semibold text-zinc-100">{exercise.name}</h3>
            {exercise.is_finisher && (
              <span className="rounded-full border border-white/10 px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] text-zinc-400">
                Finisher
              </span>
            )}
          </div>
        </div>

        <button
          type="button"
          onClick={() => setShowAllSets((prev) => !prev)}
          className={`justify-self-center rounded-full border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] transition-colors ${
            showAllSets
              ? "border-zinc-400/40 bg-zinc-600 text-zinc-100 active:bg-zinc-500"
              : "border-white/20 bg-zinc-700/70 text-zinc-300 hover:border-white/30 hover:bg-zinc-600/80 hover:text-zinc-100 active:bg-zinc-600"
          }`}
        >
          {showAllSets ? "▲ Hide" : "▼ All sets"}
        </button>

        {!exercise.is_finisher && !disabled && !sorenessLocked ? (
          <SetCounter
            count={plannedCount}
            onChange={handleSetCountChange}
            min={exercise.min_sets}
            max={Math.max(exercise.max_sets, sets.filter((setRow) => setRow.logged).length)}
          />
        ) : (
          <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1.5 text-[11px] font-medium uppercase tracking-[0.16em] text-zinc-300">
            {plannedCount} sets
          </span>
        )}
      </div>

      {(hasRecentFeedback || lastSessionLabel) && (
        <div className="mt-2 grid gap-2 [grid-template-columns:repeat(auto-fit,minmax(220px,1fr))]">
          {hasRecentFeedback && (
            <div className="rounded-xl border border-white/8 bg-black/20 px-3 py-2">
              <p className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">
                Recent feedback
              </p>
              <p className="mt-1 text-[11px] text-zinc-200">
                {feedbackSummary}
              </p>
            </div>
          )}
          {lastSessionLabel && (
            <div className="rounded-xl border border-white/8 bg-black/20 px-3 py-2">
              <p className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">
                Last session
              </p>
              <p className="mt-1 text-[11px] text-zinc-200">
                {lastSessionLabel}
              </p>
            </div>
          )}
        </div>
      )}

      {logSet.isError && (
        <p className="mt-2 text-xs text-red-300">
          Failed to save. Tap Log again to retry.
        </p>
      )}

      {exercise.weight_recommendation && (() => {
        const rec = exercise.weight_recommendation;
        const styles =
          rec.level === "apply"
            ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-200"
            : rec.level === "strong"
            ? "border-amber-400/30 bg-amber-500/10 text-amber-200"
            : rec.level === "hold"
            ? "border-zinc-400/20 bg-zinc-500/8 text-zinc-300"
            : "border-amber-400/20 bg-amber-400/8 text-amber-200";
        return (
          <p className={`mt-2 rounded-xl border px-3 py-2 text-xs ${styles}`}>
            {rec.message}
            {rec.context_note ? `. ${rec.context_note}` : ""}
          </p>
        );
      })()}

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
