"use client";

interface SetCounterProps {
  count: number;
  onChange: (count: number) => void;
  min: number;
  max: number;
}

export function SetCounter({ count, onChange, min, max }: SetCounterProps) {
  return (
    <div className="flex items-center gap-1 rounded-full border border-white/10 bg-black/20 p-1">
      <button
        type="button"
        onClick={() => onChange(Math.max(min, count - 1))}
        disabled={count <= min}
        className="h-8 w-8 rounded-full bg-white/8 text-sm font-bold text-zinc-300
                   active:bg-white/12 disabled:opacity-30"
      >
        -
      </button>
      <span className="min-w-[64px] px-2 text-center text-[11px] font-medium uppercase tracking-[0.16em] text-zinc-300">
        {count} sets
      </span>
      <button
        type="button"
        onClick={() => onChange(Math.min(max, count + 1))}
        disabled={count >= max}
        className="h-8 w-8 rounded-full bg-white/8 text-sm font-bold text-zinc-300
                   active:bg-white/12 disabled:opacity-30"
      >
        +
      </button>
    </div>
  );
}
