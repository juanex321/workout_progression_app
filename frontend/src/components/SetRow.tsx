"use client";
import { useRef } from "react";

interface SetRowProps {
  setNumber: number;
  weight: number;
  reps: number;
  logged: boolean;
  pending?: boolean;
  saveError?: boolean;
  disabled: boolean;
  sorenessLocked?: boolean;
  highlight?: boolean;
  onWeightChange: (value: number) => void;
  onRepsChange: (value: number) => void;
  onLog: () => void;
}

function Stepper({
  value,
  onChange,
  step,
  min,
  inputMode,
  disabled,
  suffix,
}: {
  value: number;
  onChange: (v: number) => void;
  step: number;
  min: number;
  inputMode: "decimal" | "numeric";
  disabled: boolean;
  suffix?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="flex items-center flex-1 min-w-0">
      <button
        type="button"
        onClick={() => onChange(Math.max(min, value - step))}
        disabled={disabled || value <= min}
        className="h-11 w-10 shrink-0 rounded-l-xl border border-white/10 bg-zinc-700/80 text-lg font-bold text-zinc-200
                   transition-colors active:bg-zinc-600 disabled:opacity-30"
      >
        −
      </button>
      <div
        className="relative h-11 flex-1 cursor-text border-y border-white/10 bg-zinc-900/80"
        onClick={() => {
          inputRef.current?.focus();
          inputRef.current?.select();
        }}
      >
        <input
          ref={inputRef}
          type="number"
          inputMode={inputMode}
          value={value || ""}
          onChange={(e) => {
            const parsed = inputMode === "decimal"
              ? parseFloat(e.target.value) || 0
              : parseInt(e.target.value) || 0;
            onChange(Math.max(min, parsed));
          }}
          disabled={disabled}
          className="h-full w-full bg-transparent px-5 text-center text-base font-semibold text-zinc-100
                     focus:outline-none disabled:opacity-50"
        />
        {suffix && (
          <span className="absolute right-1.5 top-1/2 -translate-y-1/2 text-[10px] uppercase tracking-[0.18em] text-zinc-500">
            {suffix}
          </span>
        )}
      </div>
      <button
        type="button"
        onClick={() => onChange(value + step)}
        disabled={disabled}
        className="h-11 w-10 shrink-0 rounded-r-xl border border-white/10 bg-zinc-700/80 text-lg font-bold text-zinc-200
                   transition-colors active:bg-zinc-600 disabled:opacity-30"
      >
        +
      </button>
    </div>
  );
}

export function SetRow({
  setNumber,
  weight,
  reps,
  logged,
  pending,
  saveError,
  disabled,
  sorenessLocked,
  highlight,
  onWeightChange,
  onRepsChange,
  onLog,
}: SetRowProps) {
  const logButtonClass = logged
    ? "border border-emerald-500/30 bg-emerald-500/15 text-emerald-300"
    : saveError
    ? "border border-red-500/30 bg-red-500/15 text-red-300 active:bg-red-500/25"
    : "bg-zinc-200 text-zinc-950 active:bg-white disabled:opacity-30";

  const logButtonLabel = pending ? "…" : logged ? "✓" : saveError ? "✗ Retry" : "Log";

  return (
    <div
      className={`flex items-center gap-2 ${highlight ? "rounded-2xl border border-white/10 bg-white/5 p-2.5" : ""}`}
    >
      <span
        className={`shrink-0 text-right text-xs ${
          highlight
            ? "flex h-8 w-8 items-center justify-center rounded-full bg-zinc-800 text-zinc-200"
            : "w-4 text-zinc-500"
        }`}
      >
        {setNumber}
      </span>

      <Stepper
        value={weight}
        onChange={onWeightChange}
        step={2.5}
        min={0}
        inputMode="decimal"
        disabled={disabled || !!pending}
        suffix="lb"
      />

      <Stepper
        value={reps}
        onChange={onRepsChange}
        step={1}
        min={1}
        inputMode="numeric"
        disabled={disabled || !!pending}
        suffix="reps"
      />

      <button
        type="button"
        onClick={onLog}
        disabled={disabled || !!sorenessLocked || !weight || !reps || !!pending}
        className={`h-11 shrink-0 rounded-xl px-3 text-sm font-semibold transition-colors
          ${logButtonClass}`}
      >
        {logButtonLabel}
      </button>
    </div>
  );
}
