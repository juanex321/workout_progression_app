"use client";
import { useState, useEffect } from "react";
import { useCurrentSession, useSessionData } from "@/hooks/useSessionData";
import { api } from "@/lib/api";
import { SessionHeader } from "@/components/SessionHeader";
import { MuscleGroupCard } from "@/components/MuscleGroupCard";
import { FinishButton } from "@/components/FinishButton";

export default function StraightSetsPage() {
  const [sessionNumber, setSessionNumber] = useState<number | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [isNavigating, setIsNavigating] = useState(false);
  const [navigationError, setNavigationError] = useState<string | null>(null);

  const {
    data: currentSession,
    isLoading: loadingSession,
    error: currentSessionError,
  } = useCurrentSession();

  // Set initial session from current (syncing React Query data → local state is intentional here)
  useEffect(() => {
    if (currentSession && sessionNumber === null) {
      setSessionNumber(currentSession.session_number);
      setSessionId(currentSession.session_id);
    }
  }, [currentSession, sessionNumber]);

  const { data: workoutData, isLoading: loadingData, error: workoutDataError } =
    useSessionData(sessionId);

  const handleNavigate = async (newNumber: number) => {
    if (
      isNavigating ||
      newNumber < 1 ||
      newNumber > (currentSession?.session_number ?? 1)
    ) return;

    setIsNavigating(true);
    setNavigationError(null);
    try {
      const session = await api.getSessionByNumber(newNumber);
      setSessionNumber(session.session_number);
      setSessionId(session.session_id);
    } catch {
      setNavigationError(`Unable to load session ${newNumber}. Please try again.`);
    } finally {
      setIsNavigating(false);
    }
  };

  if (loadingSession) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-lg text-zinc-400">Loading...</p>
      </div>
    );
  }

  if (currentSessionError && !currentSession) {
    return (
      <div className="flex items-center justify-center min-h-screen px-4">
        <p className="text-sm text-red-400">
          Failed to load current session. {(currentSessionError as Error).message}
        </p>
      </div>
    );
  }

  return (
    <main className="mx-auto max-w-xl px-3 pb-24 pt-4">
      <SessionHeader
        sessionNumber={sessionNumber ?? 1}
        completed={workoutData?.completed ?? 0}
        maxSession={currentSession?.session_number ?? 1}
        isNavigating={isNavigating}
        showForward={(sessionNumber ?? 1) < (currentSession?.session_number ?? 1)}
        onNavigate={handleNavigate}
      />

      {navigationError && (
        <p className="mb-4 text-center text-sm text-red-400">{navigationError}</p>
      )}

      {workoutDataError && !workoutData ? (
        <p className="text-center text-red-400 mt-8">
          Failed to load workout data. {(workoutDataError as Error).message}
        </p>
      ) : loadingData && !workoutData ? (
        <p className="text-center text-zinc-400 mt-8">Loading workout...</p>
      ) : workoutData ? (
        <div className="space-y-4">
          {Object.entries(workoutData.muscle_groups).map(([mg, data]) => (
            <MuscleGroupCard
              key={mg}
              muscleGroup={mg}
              data={data}
              sessionId={workoutData.session_id}
              sessionCompleted={workoutData.completed === 1}
              targetRir={data.target_rir}
            />
          ))}

          {workoutData.completed === 0 && (
            <FinishButton
              sessionId={workoutData.session_id}
              muscleGroups={workoutData.muscle_groups}
              onFinished={(nextSession) => {
                setSessionNumber(nextSession.session_number);
                setSessionId(nextSession.session_id);
              }}
            />
          )}
        </div>
      ) : null}
    </main>
  );
}
