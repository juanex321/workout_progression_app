"use client";
import { useState, useCallback } from "react";
import type { MuscleGroupData } from "@/lib/types";
import { ExerciseSets } from "./ExerciseSets";
import { FeedbackForm } from "./FeedbackForm";
import { FeedbackSummary } from "./FeedbackSummary";
import { SorenessSelector } from "./SorenessSelector";
import { useSoreness } from "@/hooks/useSoreness";
import { getDraft, saveDraftSoreness } from "@/lib/draft";

const RIR_COLORS: Record<number, string> = {
  0: "border-red-500",
  1: "border-yellow-500",
  2: "border-green-500",
  3: "border-zinc-500",
  4: "border-blue-500",
};

const RIR_BG: Record<number, string> = {
  0: "bg-red-500/8",
  1: "bg-yellow-500/8",
  2: "bg-emerald-500/8",
  3: "bg-zinc-500/8",
  4: "bg-blue-500/8",
};

const RIR_EMOJI: Record<number, string> = {
  0: "\uD83D\uDD34",
  1: "\uD83D\uDFE1",
  2: "\uD83D\uDFE2",
  3: "\u26AA",
  4: "\uD83D\uDD35",
};

interface MuscleGroupCardProps {
  muscleGroup: string;
  data: MuscleGroupData;
  sessionId: number;
  sessionCompleted: boolean;
  targetRir: number;
}

export function MuscleGroupCard({
  muscleGroup,
  data,
  sessionId,
  sessionCompleted,
  targetRir,
}: MuscleGroupCardProps) {
  const borderColor = RIR_COLORS[targetRir] ?? "border-zinc-600";
  const bgColor = RIR_BG[targetRir] ?? "";
  const emoji = RIR_EMOJI[targetRir] ?? "";

  // Track which exercises have all sets logged
  const [loggedMap, setLoggedMap] = useState<Record<number, boolean>>(() => {
    const initial: Record<number, boolean> = {};
    for (const ex of data.exercises) {
      initial[ex.we_id] = ex.existing_sets.length > 0;
    }
    return initial;
  });

  // Local soreness state — restore from draft if available, otherwise null until user picks
  const [localSoreness, setLocalSoreness] = useState<number | null>(() => {
    if (data.soreness_value !== null && data.soreness_value !== undefined) return null;
    const draft = getDraft(sessionId);
    return draft?.soreness[muscleGroup] ?? null;
  });
  const saveSoreness = useSoreness(sessionId);

  // Effective soreness: local pick takes priority over server-persisted value
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

  const allSetsLogged = Object.values(loggedMap).every(Boolean);
  const showFeedback = allSetsLogged || data.feedback_exists || sessionCompleted;

  // Sets are locked until soreness is selected (unless session is already completed
  // or full feedback already exists — in those cases everything is read-only anyway)
  const sorenessLocked = effectiveSoreness === null && !sessionCompleted && !data.feedback_exists;

  return (
    <section
      className={`mb-4 overflow-hidden rounded-[28px] border ${borderColor} ${bgColor} bg-zinc-950/85 shadow-[0_18px_50px_rgba(0,0,0,0.35)] backdrop-blur`}
    >
      {/* Header */}
      <div className="border-b border-white/8 px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold tracking-tight">
              {emoji} {muscleGroup}
            </h2>
          </div>
          <span className="rounded-full border border-white/10 bg-black/25 px-3.5 py-1.5 text-sm font-semibold text-zinc-100">
            RIR {targetRir}
          </span>
        </div>
        {sorenessLocked && (
          <p className="mt-2 text-xs text-zinc-400">
            Log recovery to unlock set tracking.
          </p>
        )}
      </div>

      {/* Exercises */}
      <div className="space-y-4 px-4 py-4">
        {/* Soreness selector — always shown before full feedback is submitted */}
        {!data.feedback_exists && (
          <div>
            <SorenessSelector
              muscleGroup={muscleGroup}
              value={effectiveSoreness}
              onChange={handleSorenessChange}
              disabled={sessionCompleted}
            />
            {saveSoreness.isError && (
              <p className="mt-1 text-xs text-red-300">
                Soreness save failed — tap again to retry
              </p>
            )}
          </div>
        )}

        {data.exercises.map((exercise) => (
          <ExerciseSets
            key={exercise.we_id}
            exercise={exercise}
            sessionId={sessionId}
            targetRir={targetRir}
            disabled={sessionCompleted}
            sorenessLocked={sorenessLocked}
            feedbackSummary={data.feedback_summary}
            onAllLogged={(allLogged) => handleAllLogged(exercise.we_id, allLogged)}
          />
        ))}
      </div>

      {/* Feedback - only shown after all sets are logged */}
      {showFeedback && (
        <div className="px-4 pb-4">
          {data.feedback_exists ? (
            <FeedbackSummary
              muscleGroup={muscleGroup}
              values={data.feedback_values}
              sessionId={sessionId}
              disabled={sessionCompleted}
            />
          ) : !sessionCompleted ? (
            <FeedbackForm
              muscleGroup={muscleGroup}
              sessionId={sessionId}
              initialSoreness={effectiveSoreness ?? undefined}
            />
          ) : null}
        </div>
      )}
    </section>
  );
}
