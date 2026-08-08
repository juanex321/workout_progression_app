"use client";

interface SetCounterProps {
  count: number;
  onChange: (count: number) => void;
  min: number;
  max?: number | null;
}

export function SetCounter({ count, onChange, min, max }: SetCounterProps) {
  return (
    <div
      className="grid w-full grid-cols-[minmax(0,1fr)_5rem_minmax(0,1fr)] items-center gap-2"
      role="group"
      aria-label="Adjust sets"
    >
      <button
        type="button"
        onClick={() => onChange(Math.max(min, count - 1))}
        disabled={count <= min}
        aria-label="Remove one set"
        className="h-11 w-full rounded-xl border border-white/10 bg-white/8 text-xl font-bold text-zinc-200
                   active:bg-white/15 disabled:opacity-30"
      >
        −
      </button>
      <span
        className="text-center text-[11px] font-semibold uppercase tracking-[0.16em] text-zinc-300"
        aria-live="polite"
      >
        {count} sets
      </span>
      <button
        type="button"
        onClick={() => onChange(max == null ? count + 1 : Math.min(max, count + 1))}
        disabled={max != null && count >= max}
        aria-label="Add one set"
        className="h-11 w-full rounded-xl border border-white/10 bg-white/8 text-xl font-bold text-zinc-200
                   active:bg-white/15 disabled:opacity-30"
      >
        +
      </button>
    </div>
  );
}
