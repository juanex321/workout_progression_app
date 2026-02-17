"use client";

interface SessionHeaderProps {
  sessionNumber: number;
  completed: number;
  maxSession: number;
  onNavigate: (sessionNumber: number) => void;
}

export function SessionHeader({
  sessionNumber,
  completed,
  maxSession,
  onNavigate,
}: SessionHeaderProps) {
  return (
    <div className="flex items-center justify-between mb-6">
      <button
        onClick={() => onNavigate(sessionNumber - 1)}
        disabled={sessionNumber <= 1}
        className="px-4 py-2 rounded-lg bg-zinc-800 text-zinc-300 disabled:opacity-30 active:bg-zinc-700 text-lg font-bold"
      >
        &larr;
      </button>

      <div className="text-center">
        <h1 className="text-xl font-bold">Session {sessionNumber}</h1>
        {completed === 1 && (
          <span className="text-xs text-green-400 font-medium">Completed</span>
        )}
      </div>

      <button
        onClick={() => onNavigate(sessionNumber + 1)}
        disabled={sessionNumber >= maxSession}
        className="px-4 py-2 rounded-lg bg-zinc-800 text-zinc-300 disabled:opacity-30 active:bg-zinc-700 text-lg font-bold"
      >
        &rarr;
      </button>
    </div>
  );
}
