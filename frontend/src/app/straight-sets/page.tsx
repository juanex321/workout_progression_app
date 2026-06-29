"use client";
import { useState, useEffect } from "react";
import { useCurrentSession, useSessionData } from "@/hooks/useSessionData";
import { SessionHeader } from "@/components/SessionHeader";
import { MuscleGroupCard } from "@/components/MuscleGroupCard";
import { FinishButton } from "@/components/FinishButton";

export default function StraightSetsPage() {
  const [sessionNumber, setSessionNumber] = useState<number | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);

  const {
    data: currentSession,
    isLoading: loadingSession,
    error: currentSessionError,
  } = useCurrentSession();

  // Set initial session from current (syncing React Query data → local state is intentional here)
  useEffect(() => {
    if (currentSession && sessionNumber === null) {
      /* eslint-disable react-hooks/set-state-in-effect */
      setSessionNumber(currentSession.session_number);
      setSessionId(currentSession.session_id);
      /* eslint-enable react-hooks/set-state-in-effect */
    }
  }, [currentSession, sessionNumber]);

  const { data: workoutData, isLoading: loadingData, error: workoutDataError } =
    useSessionData(sessionId);

  // Update session ID when navigating by number (syncing query result → local state is intentional)
  useEffect(() => {
    if (
      workoutData &&
      workoutData.session_number === sessionNumber &&
      workoutData.session_id !== sessionId
    ) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSessionId(workoutData.session_id);
    }
  }, [workoutData, sessionNumber, sessionId]);

  const handleNavigate = async (newNumber: number) => {
    if (newNumber < 1) return;
    setSessionNumber(newNumber);
    // Fetch session by number to get the ID
    try {
      const res = await fetch(`/api/sessions/${newNumber}`);
      if (res.ok) {
        const sess = await res.json();
        setSessionId(sess.session_id);
      }
    } catch {
      // Session doesn't exist yet
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
      <div className="flex justify-end mb-3">
        <a
          href="/myo-reps"
          className="text-xs text-zinc-400 border border-zinc-700 rounded-lg px-3 py-1.5 hover:border-yellow-600 hover:text-yellow-500 transition-colors"
        >
          Myo Reps
        </a>
      </div>
      <SessionHeader
        sessionNumber={sessionNumber ?? 1}
        completed={workoutData?.completed ?? 0}
        maxSession={currentSession?.session_number ?? 1}
        onNavigate={handleNavigate}
      />

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
