"use client";
import { useState, useEffect } from "react";
import { useCurrentSession, useSessionData } from "@/hooks/useSessionData";
import { api } from "@/lib/api";
import { SessionHeader } from "@/components/SessionHeader";
import { MuscleGroupCard } from "@/components/MuscleGroupCard";
import { FinishButton } from "@/components/FinishButton";

const SLOW_LOAD_MS = 3000;

// The free-tier backend can take 30s+ to wake up. Flags when a load has been
// running long enough that a plain "Loading..." would look like a hang.
function useSlowLoad(loading: boolean): boolean {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (!loading) return;
    const timeout = setTimeout(() => setSlow(true), SLOW_LOAD_MS);
    return () => clearTimeout(timeout);
  }, [loading]);
  return loading && slow;
}

function LoadingMessage({ label, slow }: { label: string; slow: boolean }) {
  return (
    <div className="text-center" role="status">
      <p className="text-lg text-zinc-400">{label}</p>
      {slow && (
        <p className="mt-2 text-sm text-zinc-500">
          Waking up the server. This can take up to 30 seconds.
        </p>
      )}
    </div>
  );
}

function LoadError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="text-center">
      <p className="text-sm text-red-400">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-4 h-12 rounded-xl border border-white/15 bg-zinc-800 px-6 text-sm font-semibold text-zinc-100 active:bg-zinc-700"
      >
        Try again
      </button>
    </div>
  );
}

export default function StraightSetsPage() {
  const [sessionNumber, setSessionNumber] = useState<number | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [isNavigating, setIsNavigating] = useState(false);
  const [navigationError, setNavigationError] = useState<string | null>(null);

  const {
    data: currentSession,
    isLoading: loadingSession,
    error: currentSessionError,
    refetch: refetchCurrentSession,
  } = useCurrentSession();

  // Set initial session from current (syncing React Query data → local state is intentional here)
  useEffect(() => {
    if (currentSession && sessionNumber === null) {
      setSessionNumber(currentSession.session_number);
      setSessionId(currentSession.session_id);
    }
  }, [currentSession, sessionNumber]);

  const {
    data: workoutData,
    isLoading: loadingData,
    error: workoutDataError,
    refetch: refetchWorkoutData,
  } = useSessionData(sessionId);

  const slowSession = useSlowLoad(loadingSession);
  const slowData = useSlowLoad(loadingData && !workoutData);

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
      <div className="flex items-center justify-center min-h-screen px-4">
        <LoadingMessage label="Loading..." slow={slowSession} />
      </div>
    );
  }

  if (currentSessionError && !currentSession) {
    return (
      <div className="flex items-center justify-center min-h-screen px-4">
        <LoadError
          message="Couldn't load your current session. Check your connection and try again."
          onRetry={() => refetchCurrentSession()}
        />
      </div>
    );
  }

  return (
    <main className="mx-auto max-w-2xl px-3 pb-24 pt-4">
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
        <div className="mt-8">
          <LoadError
            message="Couldn't load this workout. Check your connection and try again."
            onRetry={() => refetchWorkoutData()}
          />
        </div>
      ) : loadingData && !workoutData ? (
        <div className="mt-8">
          <LoadingMessage label="Loading workout..." slow={slowData} />
        </div>
      ) : workoutData ? (
        <div className="space-y-4">
          {Object.entries(workoutData.muscle_groups).map(([mg, data]) => (
            <MuscleGroupCard
              key={mg}
              muscleGroup={mg}
              data={data}
              sessionId={workoutData.session_id}
              sessionCompleted={workoutData.completed === 1}
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
