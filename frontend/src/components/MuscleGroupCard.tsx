"use client";
import { useState, useCallback } from "react";
import type { MuscleGroupData } from "@/lib/types";
import { ExerciseSets } from "./ExerciseSets";
import { FeedbackForm } from "./FeedbackForm";
import { FeedbackSummary } from "./FeedbackSummary";
import { SorenessSelector } from "./SorenessSelector";
import { useSoreness } from "@/hooks/useSoreness";
import { getDraft, saveDraftSoreness } from "@/lib/draft";

type FeedbackValues = { soreness: number; pump: number; workload: number };

interface MuscleGroupCardProps {
  muscleGroup: string;
  data: MuscleGroupData;
  sessionId: number;
  sessionCompleted: boolean;
}

export function MuscleGroupCard({
  muscleGroup,
  data,
  sessionId,
  sessionCompleted,
}: MuscleGroupCardProps) {
  const regularExercises = data.exercises.filter((exercise) => !exercise.is_finisher);
  const finisherExercises = data.exercises.filter((exercise) => exercise.is_finisher);

  const [loggedMap, setLoggedMap] = useState<Record<number, boolean>>(() => {
    const initial: Record<number, boolean> = {};
    for (const ex of data.exercises) {
      initial[ex.we_id] =
        ex.existing_sets.length > 0 &&
        ex.existing_sets.length >= Math.max(ex.recommendations.length, 1);
    }
    return initial;
  });

  const [localSoreness, setLocalSoreness] = useState<number | null>(() => {
    if (data.soreness_value !== null && data.soreness_value !== undefined) return null;
    const draft = getDraft(sessionId);
    return draft?.soreness[muscleGroup] ?? null;
  });
  const [feedbackValues, setFeedbackValues] = useState<FeedbackValues | null>(
    data.feedback_values
  );
  const [feedbackComplete, setFeedbackComplete] = useState(data.feedback_exists);
  const [collapsed, setCollapsed] = useState(sessionCompleted || data.feedback_exists);
  const saveSoreness = useSoreness(sessionId);

  const effectiveSoreness = localSoreness ?? data.soreness_value;

  const handleSorenessChange = useCallback(
    (v: number) => {
      setLocalSoreness(v);
      saveDraftSoreness(sessionId, muscleGroup, v);
      saveSoreness.mutate({ session_id: sessionId, muscle_group: muscleGroup, soreness: v });
    },
    [sessionId, muscleGroup, saveSoreness]
  );

  const handleAllLogged = useCallback((weId: number, allLogged: boolean) => {
    setLoggedMap((prev) => (prev[weId] === allLogged ? prev : { ...prev, [weId]: allLogged }));
  }, []);

  const handleFeedbackSaved = useCallback((values: FeedbackValues) => {
    setFeedbackValues(values);
    setFeedbackComplete(true);
    setCollapsed(true);
  }, [setCollapsed]);

  const allSetsLogged =
    data.exercises.length > 0 && Object.values(loggedMap).every(Boolean);
  const regularExercisesComplete =
    regularExercises.length === 0 || regularExercises.every((exercise) => loggedMap[exercise.we_id]);
  const visibleExercises = [
    ...regularExercises,
    ...finisherExercises.filter(
      (exercise) => regularExercisesComplete || loggedMap[exercise.we_id] || sessionCompleted
    ),
  ];
  const showFeedback = allSetsLogged || feedbackComplete || sessionCompleted;
  const sorenessLocked = effectiveSoreness === null && !sessionCompleted && !feedbackComplete;
  const canCollapse = feedbackComplete || sessionCompleted;
  const loggedExerciseCount = Object.values(loggedMap).filter(Boolean).length;

  return (
    <section className="mb-5 overflow-hidden rounded-[28px] border border-zinc-700 bg-zinc-950/90 shadow-[0_18px_50px_rgba(0,0,0,0.38)] backdrop-blur transition-all">

      <button
        type="button"
        onClick={() => canCollapse && setCollapsed((prev) => !prev)}
        className={`w-full px-5 py-4 text-left ${canCollapse ? "cursor-pointer" : "cursor-default"}`}
        aria-expanded={!collapsed}
      >
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-2xl font-bold tracking-tight text-zinc-50">
                {muscleGroup}
              </h2>
            </div>
            <p className="mt-1 text-sm text-zinc-500">
              {feedbackComplete || sessionCompleted
                ? `${loggedExerciseCount}/${data.exercises.length} exercises complete · feedback saved`
                : allSetsLogged
                  ? "All sets complete · feedback ready"
                  : `${loggedExerciseCount}/${data.exercises.length} exercises complete`}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {canCollapse && (
              <span className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-black/25 text-lg text-zinc-300">
                {collapsed ? "+" : "−"}
              </span>
            )}
          </div>
        </div>
      </button>

      {collapsed && feedbackValues ? (
        <div className="border-t border-white/8 px-4 pb-4 pt-3">
          <FeedbackSummary
            muscleGroup={muscleGroup}
            values={feedbackValues}
            sessionId={sessionId}
            disabled={sessionCompleted}
            onSaved={handleFeedbackSaved}
          />
        </div>
      ) : (
        <>
          <div className="space-y-5 border-t border-white/8 px-4 py-5">
            {!feedbackComplete && (
              <div>
                <SorenessSelector
                  muscleGroup={muscleGroup}
                  value={effectiveSoreness}
                  onChange={handleSorenessChange}
                  disabled={sessionCompleted}
                />
                {saveSoreness.isError && (
                  <p className="mt-1 text-xs text-red-300">Soreness save failed — tap again to retry</p>
                )}
              </div>
            )}

            {visibleExercises.map((exercise) => (
              <ExerciseSets
                key={exercise.we_id}
                exercise={exercise}
                sessionId={sessionId}
                disabled={sessionCompleted}
                sorenessLocked={sorenessLocked}
                feedbackSummary={data.feedback_summary}
                onAllLogged={(allLogged) => handleAllLogged(exercise.we_id, allLogged)}
              />
            ))}
          </div>

          {showFeedback && (
            <div className="px-4 pb-4">
              {feedbackComplete && feedbackValues ? (
                <FeedbackSummary
                  muscleGroup={muscleGroup}
                  values={feedbackValues}
                  sessionId={sessionId}
                  disabled={sessionCompleted}
                  onSaved={handleFeedbackSaved}
                />
              ) : !sessionCompleted ? (
                <FeedbackForm
                  muscleGroup={muscleGroup}
                  sessionId={sessionId}
                  initialSoreness={effectiveSoreness ?? undefined}
                  onSaved={handleFeedbackSaved}
                />
              ) : null}
            </div>
          )}
        </>
      )}
    </section>
  );
}
