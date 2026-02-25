"use client";
import { useRef } from "react";

interface SetRowProps {
  setNumber: number;
  weight: number;
  reps: number;
  logged: boolean;
  disabled: boolean;
  sorenessLocked?: boolean;
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
        className="w-9 h-11 rounded-l-lg bg-zinc-700 text-zinc-300 text-lg font-bold
                   active:bg-zinc-600 disabled:opacity-30 shrink-0"
      >
        −
      </button>
      <div
        className="relative flex-1 h-11 bg-zinc-800 border-y border-zinc-700 cursor-text"
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
          className="w-full h-full bg-transparent text-center text-base font-medium
                     focus:outline-none disabled:opacity-50"
        />
        {suffix && (
          <span className="absolute right-1.5 top-1/2 -translate-y-1/2 text-[10px] text-zinc-500">
            {suffix}
          </span>
        )}
      </div>
      <button
        type="button"
        onClick={() => onChange(value + step)}
        disabled={disabled}
        className="w-9 h-11 rounded-r-lg bg-zinc-700 text-zinc-300 text-lg font-bold
                   active:bg-zinc-600 disabled:opacity-30 shrink-0"
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
  disabled,
  sorenessLocked,
  onWeightChange,
  onRepsChange,
  onLog,
}: SetRowProps) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-zinc-500 w-4 text-right shrink-0">
        {setNumber}
      </span>

      <Stepper
        value={weight}
        onChange={onWeightChange}
        step={2.5}
        min={0}
        inputMode="decimal"
        disabled={disabled}
      />

      <Stepper
        value={reps}
        onChange={onRepsChange}
        step={1}
        min={1}
        inputMode="numeric"
        disabled={disabled}
      />

      <button
        onClick={onLog}
        disabled={disabled || !!sorenessLocked || !weight || !reps}
        className={`h-11 px-3 rounded-lg font-medium text-sm transition-colors shrink-0
          ${
            logged
              ? "bg-green-600/20 text-green-400 border border-green-600/30"
              : "bg-zinc-700 text-zinc-200 active:bg-zinc-600 disabled:opacity-30"
          }`}
      >
        {logged ? "✓" : "Log"}
      </button>
    </div>
  );
}
