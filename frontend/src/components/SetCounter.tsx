"use client";

interface SetCounterProps {
  count: number;
  onChange: (count: number) => void;
  min: number;
  max: number;
}

export function SetCounter({ count, onChange, min, max }: SetCounterProps) {
  return (
    <div className="flex items-center gap-1">
      <button
        onClick={() => onChange(Math.max(min, count - 1))}
        disabled={count <= min}
        className="w-7 h-7 rounded bg-zinc-800 text-zinc-400 text-sm font-bold
                   active:bg-zinc-700 disabled:opacity-30"
      >
        -
      </button>
      <span className="w-6 text-center text-xs text-zinc-400">
        {count}s
      </span>
      <button
        onClick={() => onChange(Math.min(max, count + 1))}
        disabled={count >= max}
        className="w-7 h-7 rounded bg-zinc-800 text-zinc-400 text-sm font-bold
                   active:bg-zinc-700 disabled:opacity-30"
      >
        +
      </button>
    </div>
  );
}
