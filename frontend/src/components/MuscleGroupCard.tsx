"use client";
import { useState, useCallback } from "react";
import type { MuscleGroupData } from "@/lib/types";
import { ExerciseSets } from "./ExerciseSets";
import { FeedbackForm } from "./FeedbackForm";
import { FeedbackSummary } from "./FeedbackSummary";

const RIR_COLORS: Record<number, string> = {
  0: "border-red-500",
  1: "border-orange-500",
  2: "border-yellow-500",
  3: "border-green-500",
  4: "border-blue-500",
};

const RIR_BG: Record<number, string> = {
  0: "bg-red-500/5",
  1: "bg-orange-500/5",
  2: "bg-yellow-500/5",
  3: "bg-green-500/5",
  4: "bg-blue-500/5",
};

const RIR_EMOJI: Record<number, string> = {
  0: "\uD83D\uDD34",
  1: "\uD83D\uDFE0",
  2: "\uD83D\uDFE1",
  3: "\uD83D\uDFE2",
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

  const handleAllLogged = useCallback((weId: number, allLogged: boolean) => {
    setLoggedMap((prev) => (prev[weId] === allLogged ? prev : { ...prev, [weId]: allLogged }));
  }, []);

  const allSetsLogged = Object.values(loggedMap).every(Boolean);
  const showFeedback = allSetsLogged || data.feedback_exists || sessionCompleted;

  return (
    <div className={`rounded-xl border-2 ${borderColor} ${bgColor} mb-4 overflow-hidden`}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-zinc-800">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold">
            {emoji} {muscleGroup}
          </h2>
          <span className="text-sm text-zinc-400">RIR {targetRir}</span>
        </div>
        <p className="text-xs text-zinc-500 mt-0.5">{data.phase}</p>
        {data.feedback_summary && data.feedback_summary !== "No recent feedback" && (
          <p className="text-xs text-zinc-500">Recent: {data.feedback_summary}</p>
        )}
      </div>

      {/* Exercises */}
      <div className="px-4 py-3 space-y-4">
        {data.exercises.map((exercise) => (
          <ExerciseSets
            key={exercise.we_id}
            exercise={exercise}
            sessionId={sessionId}
            targetRir={targetRir}
            disabled={sessionCompleted}
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
            />
          ) : null}
        </div>
      )}
    </div>
  );
}
