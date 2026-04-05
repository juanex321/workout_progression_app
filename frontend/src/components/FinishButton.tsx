"use client";
import type { MuscleGroupData, SessionResponse } from "@/lib/types";
import { useFinishWorkout } from "@/hooks/useFinishWorkout";

interface FinishButtonProps {
  sessionId: number;
  muscleGroups: Record<string, MuscleGroupData>;
  onFinished: (nextSession: SessionResponse) => void;
}

export function FinishButton({
  sessionId,
  muscleGroups,
  onFinished,
}: FinishButtonProps) {
  const finishWorkout = useFinishWorkout();

  // Check if all muscle groups have feedback
  const allFeedbackDone = Object.values(muscleGroups).every(
    (mg) => mg.feedback_exists
  );

  const handleFinish = () => {
    if (!allFeedbackDone) {
      alert("Please submit feedback for all muscle groups before finishing.");
      return;
    }

    finishWorkout.mutate(sessionId, {
      onSuccess: (nextSession) => onFinished(nextSession),
    });
  };

  return (
    <div className="mt-6">
      <button
        onClick={handleFinish}
        disabled={finishWorkout.isPending}
        className={`h-[52px] w-full rounded-2xl border font-bold text-base transition-colors
          ${
            allFeedbackDone
              ? "border-emerald-400/30 bg-emerald-500 text-zinc-950 active:bg-emerald-400"
              : "border-white/10 bg-white/5 text-zinc-400"
          }
          disabled:opacity-50`}
      >
        {finishWorkout.isPending
          ? "Finishing..."
          : allFeedbackDone
            ? "Finish Session"
            : "Submit All Feedback First"}
      </button>
    </div>
  );
}
