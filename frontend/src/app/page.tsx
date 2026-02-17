"use client";
import { useState, useEffect } from "react";
import { useCurrentSession, useSessionData } from "@/hooks/useSessionData";
import { SessionHeader } from "@/components/SessionHeader";
import { MuscleGroupCard } from "@/components/MuscleGroupCard";
import { FinishButton } from "@/components/FinishButton";

export default function HomePage() {
  const [sessionNumber, setSessionNumber] = useState<number | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);

  const { data: currentSession, isLoading: loadingSession } =
    useCurrentSession();

  // Set initial session from current
  useEffect(() => {
    if (currentSession && sessionNumber === null) {
      setSessionNumber(currentSession.session_number);
      setSessionId(currentSession.session_id);
    }
  }, [currentSession, sessionNumber]);

  const { data: workoutData, isLoading: loadingData } =
    useSessionData(sessionId);

  // Update session ID when navigating by number
  useEffect(() => {
    if (
      workoutData &&
      workoutData.session_number === sessionNumber &&
      workoutData.session_id !== sessionId
    ) {
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

  return (
    <main className="mx-auto max-w-lg px-3 pb-24 pt-4">
      <SessionHeader
        sessionNumber={sessionNumber ?? 1}
        completed={workoutData?.completed ?? 0}
        maxSession={currentSession?.session_number ?? 1}
        onNavigate={handleNavigate}
      />

      {loadingData ? (
        <p className="text-center text-zinc-400 mt-8">Loading workout...</p>
      ) : workoutData ? (
        <>
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
        </>
      ) : null}
    </main>
  );
}
