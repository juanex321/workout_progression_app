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
    <div className="mb-5 rounded-[24px] border border-white/8 bg-black/35 px-3 py-3 backdrop-blur">
      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={() => onNavigate(sessionNumber - 1)}
          disabled={sessionNumber <= 1}
          className="h-12 w-12 rounded-2xl border border-white/10 bg-white/5 text-lg font-bold text-zinc-200 transition-colors active:bg-white/10 disabled:opacity-30"
        >
          &larr;
        </button>

        <div className="text-center">
          <p className="text-[11px] uppercase tracking-[0.2em] text-zinc-500">Workout session</p>
          <h1 className="text-2xl font-bold tracking-tight">Session {sessionNumber}</h1>
          {completed === 1 && (
            <span className="text-xs font-medium text-emerald-300">Completed</span>
          )}
        </div>

        <button
          type="button"
          onClick={() => onNavigate(sessionNumber + 1)}
          disabled={sessionNumber >= maxSession}
          className="h-12 w-12 rounded-2xl border border-white/10 bg-white/5 text-lg font-bold text-zinc-200 transition-colors active:bg-white/10 disabled:opacity-30"
        >
          &rarr;
        </button>
      </div>
    </div>
  );
}
