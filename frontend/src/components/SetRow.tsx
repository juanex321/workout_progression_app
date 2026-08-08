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
    <div className="flex h-12 min-w-0 items-stretch overflow-hidden rounded-xl border border-white/15 bg-zinc-950">
      <button
        type="button"
        onClick={() => onChange(Math.max(min, value - step))}
        disabled={disabled || value <= min}
        className="w-7 shrink-0 border-r border-white/15 bg-zinc-700 text-lg font-bold text-zinc-50 transition-colors active:bg-zinc-600 disabled:opacity-30 sm:w-10"
        aria-label={`Decrease ${suffix ?? "value"}`}
      >
        −
      </button>
      <div
        className="relative min-w-0 flex-1 cursor-text"
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
            const parsed =
              inputMode === "decimal"
                ? parseFloat(e.target.value) || 0
                : parseInt(e.target.value) || 0;
            onChange(Math.max(min, parsed));
          }}
          disabled={disabled}
          aria-label={suffix}
          className="h-full w-full min-w-0 bg-transparent px-0.5 text-center text-base font-bold text-zinc-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-red-500 disabled:opacity-50 sm:px-2 sm:text-lg"
        />
      </div>
      <button
        type="button"
        onClick={() => onChange(value + step)}
        disabled={disabled}
        className="w-7 shrink-0 border-l border-white/15 bg-zinc-700 text-lg font-bold text-zinc-50 transition-colors active:bg-zinc-600 disabled:opacity-30 sm:w-10"
        aria-label={`Increase ${suffix ?? "value"}`}
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
    ? "border border-emerald-500/50 bg-emerald-500/25 text-emerald-100"
    : saveError
      ? "border border-red-500/30 bg-red-500/15 text-red-200 active:bg-red-500/25"
      : "bg-red-600 text-white active:bg-red-500 disabled:opacity-30";

  const logButtonLabel = pending ? "Saving..." : logged ? "Done" : saveError ? "Retry" : "Log Set";

  return (
    <div
      className={`grid grid-cols-[1.75rem_minmax(0,1.15fr)_minmax(0,0.85fr)_2.75rem] items-center gap-1.5 rounded-2xl p-1.5 sm:grid-cols-[2.5rem_minmax(0,1fr)_minmax(0,1fr)_6rem] sm:gap-2 ${
        highlight
          ? "border-2 border-red-500/45 bg-red-500/8 shadow-[0_10px_24px_rgba(0,0,0,0.32)]"
          : logged
            ? "border border-emerald-400/10 bg-emerald-500/5 opacity-75"
            : "border border-white/5 bg-black/10"
      }`}
    >
      <span
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
          highlight
            ? "bg-red-600 text-white"
            : logged
              ? "bg-emerald-500/15 text-emerald-200"
              : "bg-white/5 text-zinc-400"
        }`}
      >
        {setNumber}
      </span>

      <div className="min-w-0">
        <Stepper
          value={weight}
          onChange={onWeightChange}
          step={2.5}
          min={0}
          inputMode="decimal"
          disabled={disabled || !!pending}
          suffix="lb"
        />
      </div>

      <div className="min-w-0">
        <Stepper
          value={reps}
          onChange={onRepsChange}
          step={1}
          min={1}
          inputMode="numeric"
          disabled={disabled || !!pending}
          suffix="reps"
        />
      </div>

      <button
        type="button"
        onClick={onLog}
        disabled={disabled || !!sorenessLocked || !weight || !reps || !!pending}
        aria-label={`${logButtonLabel}, set ${setNumber}`}
        className={`flex h-12 min-w-0 items-center justify-center rounded-xl px-1 text-sm font-bold transition-colors sm:px-3 ${logButtonClass}`}
      >
        <span className="sm:hidden" aria-hidden="true">
          {pending ? "…" : logged ? "✓" : saveError ? "↻" : "Log"}
        </span>
        <span className="hidden sm:inline">{logButtonLabel}</span>
      </button>
    </div>
  );
}
