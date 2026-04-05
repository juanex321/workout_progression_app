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

const RIR_PILL: Record<number, string> = {
  0: "border-red-400/30 bg-red-500/12 text-red-100",
  1: "border-yellow-400/30 bg-yellow-500/12 text-yellow-100",
  2: "border-emerald-400/30 bg-emerald-500/12 text-emerald-100",
  3: "border-zinc-400/20 bg-zinc-500/10 text-zinc-200",
  4: "border-blue-400/30 bg-blue-500/12 text-blue-100",
};

const PHASE_LABELS: Record<number, string> = {
  0: "Max effort",
  1: "Overreach",
  2: "Calibration",
  4: "Deload",
};

const PHASE_SESSION_TOTALS: Partial<Record<number, number>> = {
  0: 2,
  1: 3,
  2: 4,
  4: 1,
};

function getCompactPhaseLabel(phase: string, targetRir: number): string {
  const baseLabel = PHASE_LABELS[targetRir] ?? phase;
  const sessionMatch = phase.match(/Session\s+(\d+)(?:\/(\d+))?/i);

  if (sessionMatch) {
    const current = sessionMatch[1];
    const total = sessionMatch[2] ?? PHASE_SESSION_TOTALS[targetRir];
    return total ? `${baseLabel} · S${current}/${total}` : `${baseLabel} · S${current}`;
  }

  if (/starting fresh/i.test(phase)) {
    const total = PHASE_SESSION_TOTALS[targetRir];
    return total ? `${baseLabel} · S1/${total}` : baseLabel;
  }

  return baseLabel;
}

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
  const rirPill = RIR_PILL[targetRir] ?? "border-white/10 bg-black/25 text-zinc-100";
  const compactPhase = getCompactPhaseLabel(data.phase, targetRir);
  const emoji = RIR_EMOJI[targetRir] ?? "";
  const regularExercises = data.exercises.filter((exercise) => !exercise.is_finisher);
  const finisherExercises = data.exercises.filter((exercise) => exercise.is_finisher);

  // Track which exercises have all sets logged
  const [loggedMap, setLoggedMap] = useState<Record<number, boolean>>(() => {
    const initial: Record<number, boolean> = {};
    for (const ex of data.exercises) {
      initial[ex.we_id] =
        ex.existing_sets.length > 0 &&
        ex.existing_sets.length >= Math.max(ex.recommendations.length, 1);
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
  const regularExercisesComplete =
    regularExercises.length === 0 || regularExercises.every((exercise) => loggedMap[exercise.we_id]);
  const visibleExercises = [
    ...regularExercises,
    ...finisherExercises.filter(
      (exercise) => regularExercisesComplete || loggedMap[exercise.we_id] || sessionCompleted
    ),
  ];
  const showFeedback = allSetsLogged || data.feedback_exists || sessionCompleted;

  // Sets are locked until soreness is selected (unless session is already completed
  // or full feedback already exists — in those cases everything is read-only anyway)
  const sorenessLocked = effectiveSoreness === null && !sessionCompleted && !data.feedback_exists;

  return (
    <section
      className={`mb-4 overflow-hidden rounded-[28px] border ${borderColor} ${bgColor} bg-zinc-950/85 shadow-[0_18px_50px_rgba(0,0,0,0.35)] backdrop-blur`}
    >
      {/* Header */}
      <div className="px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold tracking-tight text-zinc-50">
                {emoji} {muscleGroup}
              </h2>
              <span className="truncate text-sm text-zinc-400">
                {compactPhase}
              </span>
            </div>
          </div>
          <span className={`rounded-full border px-3.5 py-1.5 text-sm font-semibold ${rirPill}`}>
            RIR {targetRir}
          </span>
        </div>
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

        {visibleExercises.map((exercise) => (
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
