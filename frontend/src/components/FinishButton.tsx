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
        className={`w-full h-12 rounded-xl font-bold text-base transition-colors
          ${
            allFeedbackDone
              ? "bg-green-600 text-white active:bg-green-500"
              : "bg-zinc-700 text-zinc-400"
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
