"use client";
import { useRef, useState } from "react";

interface SetRowProps {
  setNumber: number;
  weight: number;
  reps: number;
  logged: boolean;
  pending?: boolean;
  saveError?: boolean;
  disabled: boolean;
  sorenessLocked?: boolean;
  onLockedLogAttempt?: () => void;
  highlight?: boolean;
  repsFromLastSession?: boolean;
  lastReps?: number;
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
  readOnly,
  suffix,
  muted,
}: {
  value: number;
  onChange: (v: number) => void;
  step: number;
  min: number;
  inputMode: "decimal" | "numeric";
  disabled: boolean;
  readOnly?: boolean;
  suffix?: string;
  muted?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  if (readOnly) {
    return (
      <div
        className="flex h-12 min-w-0 items-center justify-center rounded-xl border border-white/5 bg-black/20 text-base font-bold text-zinc-200 sm:text-lg"
        aria-label={`${value} ${suffix ?? ""}`.trim()}
      >
        {value}
      </div>
    );
  }

  return (
    <div className={`flex h-12 min-w-0 items-stretch overflow-hidden rounded-xl border bg-zinc-950 ${muted ? "border-white/8 opacity-65" : "border-white/15"}`}>
      <button
        type="button"
        onClick={() => onChange(Math.max(min, value - step))}
        disabled={disabled || value <= min}
        className="w-10 shrink-0 border-r border-white/15 bg-zinc-700 text-xl font-bold text-zinc-50 transition-colors active:bg-zinc-600 disabled:opacity-30 sm:text-lg"
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
          aria-label={muted ? `${suffix} from last session` : suffix}
          className={`h-full w-full min-w-0 bg-transparent px-0.5 text-center text-base font-bold focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500 disabled:opacity-50 sm:px-2 sm:text-lg ${muted ? "text-zinc-400" : "text-zinc-50"}`}
        />
      </div>
      <button
        type="button"
        onClick={() => onChange(value + step)}
        disabled={disabled}
        className="w-10 shrink-0 border-l border-white/15 bg-zinc-700 text-xl font-bold text-zinc-50 transition-colors active:bg-zinc-600 disabled:opacity-30 sm:text-lg"
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
  onLockedLogAttempt,
  highlight,
  repsFromLastSession,
  lastReps,
  onWeightChange,
  onRepsChange,
  onLog,
}: SetRowProps) {
  // Logged sets stay read-only until the user explicitly taps Edit, so a stray
  // tap on a stepper can't silently un-log a finished set.
  const [editing, setEditing] = useState(false);
  const [prevLogged, setPrevLogged] = useState(logged);
  if (logged !== prevLogged) {
    setPrevLogged(logged);
    if (logged) setEditing(false);
  }

  const readOnly = disabled || (logged && !editing);
  const locked = !logged && !!sorenessLocked;

  let buttonLabel: string;
  let buttonClass: string;
  let handleClick: () => void;
  if (logged && !editing) {
    buttonLabel = disabled ? "Done" : "Edit";
    buttonClass =
      "border border-emerald-500/40 bg-emerald-500/15 text-emerald-100 active:bg-emerald-500/25";
    handleClick = () => setEditing(true);
  } else if (logged) {
    buttonLabel = "Done";
    buttonClass = "border border-white/15 bg-zinc-700 text-zinc-100 active:bg-zinc-600";
    handleClick = () => setEditing(false);
  } else if (saveError) {
    buttonLabel = pending ? "Saving..." : "Retry";
    buttonClass = "border border-red-500/30 bg-red-500/15 text-red-200 active:bg-red-500/25";
    handleClick = onLog;
  } else {
    buttonLabel = pending ? "Saving..." : "Log set";
    buttonClass = locked
      ? "bg-blue-600/35 text-white/70"
      : "bg-blue-600 text-white active:bg-blue-500 disabled:opacity-30";
    handleClick = locked ? () => onLockedLogAttempt?.() : onLog;
  }

  const buttonDisabled =
    disabled || !!pending || (!logged && !locked && (!weight || !reps));

  return (
    <div
      className={`grid grid-cols-2 gap-1.5 rounded-2xl p-1.5 sm:grid-cols-[2.5rem_minmax(0,1fr)_minmax(0,1fr)_6rem] sm:items-center sm:gap-2 ${
        highlight
          ? "border-2 border-blue-500/45 bg-blue-500/8 shadow-[0_10px_24px_rgba(0,0,0,0.32)]"
          : logged
            ? "border border-emerald-400/10 bg-emerald-500/5"
            : "border border-white/5 bg-black/10"
      }`}
    >
      <div className="order-1 min-w-0 sm:order-2">
        <Stepper
          value={weight}
          onChange={onWeightChange}
          step={2.5}
          min={0}
          inputMode="decimal"
          disabled={disabled || !!pending}
          readOnly={readOnly}
          suffix="lb"
        />
      </div>

      <div className="order-2 min-w-0 sm:order-3">
        <Stepper
          value={reps}
          onChange={onRepsChange}
          step={1}
          min={1}
          inputMode="numeric"
          disabled={disabled || !!pending}
          readOnly={readOnly}
          suffix="reps"
          muted={repsFromLastSession}
        />
        {lastReps !== undefined && (
          <p className="mt-0.5 text-center text-[11px] text-zinc-500">
            last: {lastReps}
          </p>
        )}
      </div>

      <div className="order-3 col-span-2 flex items-center gap-2 sm:contents">
        <span
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold sm:order-1 sm:h-7 sm:w-7 sm:justify-self-center ${
            highlight
              ? "bg-blue-600 text-white"
              : logged
                ? "bg-emerald-500/15 text-emerald-200"
                : "bg-white/5 text-zinc-400"
          }`}
          aria-label={`Set ${setNumber}${logged ? ", logged" : ""}`}
        >
          {setNumber}
        </span>

        <button
          type="button"
          onClick={handleClick}
          disabled={buttonDisabled}
          aria-label={`${buttonLabel}, set ${setNumber}`}
          className={`flex h-11 min-w-0 flex-1 items-center justify-center rounded-xl px-3 text-sm font-bold transition-colors sm:order-4 sm:h-12 ${buttonClass}`}
        >
          {buttonLabel}
        </button>
      </div>
    </div>
  );
}
