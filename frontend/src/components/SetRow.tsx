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
    <div className="flex min-w-0 flex-1 items-center">
      <button
        type="button"
        onClick={() => onChange(Math.max(min, value - step))}
        disabled={disabled || value <= min}
        className="h-14 w-12 shrink-0 rounded-l-2xl border border-white/20 bg-zinc-600 text-2xl font-bold text-zinc-50 transition-colors active:bg-zinc-500 disabled:opacity-30"
        aria-label={`Decrease ${suffix ?? "value"}`}
      >
        −
      </button>
      <div
        className="relative h-14 flex-1 cursor-text border-y border-white/15 bg-zinc-950"
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
          className="h-full w-full bg-transparent px-2 text-center text-xl font-bold text-zinc-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-red-500 disabled:opacity-50"
        />
      </div>
      <button
        type="button"
        onClick={() => onChange(value + step)}
        disabled={disabled}
        className="h-14 w-12 shrink-0 rounded-r-2xl border border-white/20 bg-zinc-600 text-2xl font-bold text-zinc-50 transition-colors active:bg-zinc-500 disabled:opacity-30"
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
      className={`grid grid-cols-[auto_minmax(0,1fr)] items-center gap-3 sm:grid-cols-[auto_minmax(0,1fr)_minmax(0,1fr)_auto] ${
        highlight
          ? "rounded-3xl border-2 border-red-500/45 bg-red-500/8 p-4 shadow-[0_18px_45px_rgba(0,0,0,0.4)]"
          : logged
            ? "rounded-2xl border border-emerald-400/10 bg-emerald-500/5 p-2 opacity-75"
            : ""
      }`}
    >
      <span
        className={`shrink-0 text-right font-bold ${
          highlight
            ? "flex h-10 w-10 items-center justify-center rounded-full bg-red-600 text-base text-white"
            : "w-5 text-sm text-zinc-500"
        }`}
      >
        {setNumber}
      </span>

      <div className="min-w-0 sm:hidden">
        <button
          type="button"
          onClick={onLog}
          disabled={disabled || !!sorenessLocked || !weight || !reps || !!pending}
          className={`h-14 w-full rounded-2xl px-4 text-base font-bold transition-colors ${logButtonClass}`}
        >
          {logButtonLabel}
        </button>
      </div>

      <div className="col-span-2 min-w-0 sm:col-span-1">
        <p className="mb-1 text-xs font-semibold uppercase tracking-[0.14em] text-zinc-500">Weight</p>
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

      <div className="col-span-2 min-w-0 sm:col-span-1">
        <p className="mb-1 text-xs font-semibold uppercase tracking-[0.14em] text-zinc-500">Reps</p>
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
        className={`hidden h-14 shrink-0 rounded-2xl px-5 text-base font-bold transition-colors sm:block ${logButtonClass}`}
      >
        {logButtonLabel}
      </button>
    </div>
  );
}
