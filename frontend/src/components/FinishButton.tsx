"use client";
import type { MuscleGroupData, SessionResponse } from "@/lib/types";
import { useFinishWorkout } from "@/hooks/useFinishWorkout";
import { muscleGroupAnchorId } from "./MuscleGroupCard";

interface FinishButtonProps {
  sessionId: number;
  muscleGroups: Record<string, MuscleGroupData>;
  onFinished: (nextSession: SessionResponse) => void;
}

function scrollToMuscleGroup(muscleGroup: string) {
  document
    .getElementById(muscleGroupAnchorId(muscleGroup))
    ?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export function FinishButton({
  sessionId,
  muscleGroups,
  onFinished,
}: FinishButtonProps) {
  const finishWorkout = useFinishWorkout();

  const missingFeedback = Object.entries(muscleGroups)
    .filter(([, mg]) => !mg.feedback_exists)
    .map(([name]) => name);

  if (missingFeedback.length > 0) {
    return (
      <div className="mt-6 rounded-2xl border border-white/10 bg-white/5 p-4">
        <p className="text-sm font-semibold text-zinc-200">
          Feedback needed before finishing
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {missingFeedback.map((name) => (
            <button
              key={name}
              type="button"
              onClick={() => scrollToMuscleGroup(name)}
              className="min-h-11 rounded-xl border border-white/15 bg-zinc-800 px-4 text-sm font-semibold text-zinc-100 active:bg-zinc-700"
            >
              {name} &rarr;
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mt-6">
      {finishWorkout.isError && (
        <p className="mb-2 text-center text-sm text-red-300">
          Couldn&apos;t finish the session. Check your connection and try again.
        </p>
      )}
      <button
        type="button"
        onClick={() =>
          finishWorkout.mutate(sessionId, {
            onSuccess: (nextSession) => onFinished(nextSession),
          })
        }
        disabled={finishWorkout.isPending}
        className="h-[52px] w-full rounded-2xl border border-emerald-400/30 bg-emerald-500 text-base font-bold text-zinc-950 transition-colors active:bg-emerald-400 disabled:opacity-50"
      >
        {finishWorkout.isPending
          ? "Finishing..."
          : finishWorkout.isError
            ? "Try again"
            : "Finish Session"}
      </button>
    </div>
  );
}
