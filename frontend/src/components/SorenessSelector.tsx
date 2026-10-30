"use client";
import { useState } from "react";
import { SORENESS_LABELS } from "@/lib/feedbackLabels";

// "Healed a while ago" is the one answer whose meaning stretches with the gap
// since the last session, so it asks how many days the soreness lasted.
const HEALED_EARLY = 2;
const MAX_DAY_OPTION = 4;

interface SorenessSelectorProps {
  muscleGroup: string;
  value: number | null;
  recoveryDays?: number | null;
  daysSinceLastTrained?: number | null;
  onChange: (v: number, recoveryDays?: number) => void;
  disabled: boolean;
  highlight?: boolean;
}

function recoveryDayOptions(daysSinceLastTrained: number | null | undefined): number[] {
  const latest =
    daysSinceLastTrained == null
      ? MAX_DAY_OPTION
      : Math.max(1, Math.min(daysSinceLastTrained - 1, MAX_DAY_OPTION));
  return Array.from({ length: latest }, (_, index) => index + 1);
}

function dayLabel(days: number, isLast: boolean, daysSinceLastTrained: number | null | undefined): string {
  const openEnded =
    isLast && days === MAX_DAY_OPTION && (daysSinceLastTrained == null || daysSinceLastTrained - 1 > MAX_DAY_OPTION);
  return `${days}${openEnded ? "+" : ""} ${days === 1 && !openEnded ? "day" : "days"}`;
}

export function SorenessSelector({
  muscleGroup,
  value,
  recoveryDays,
  daysSinceLastTrained,
  onChange,
  disabled,
  highlight,
}: SorenessSelectorProps) {
  const [internalValue, setInternalValue] = useState(value ?? 2);
  const [isSelected, setIsSelected] = useState(value !== null);
  const [expanded, setExpanded] = useState(value === null);
  const [days, setDays] = useState<number | null>(recoveryDays ?? null);
  const [awaitingDays, setAwaitingDays] = useState(false);

  const dayOptions = recoveryDayOptions(daysSinceLastTrained);

  const handleSelect = (v: number) => {
    setInternalValue(v);
    if (v === HEALED_EARLY) {
      setAwaitingDays(true);
      return;
    }
    setAwaitingDays(false);
    setDays(null);
    setIsSelected(true);
    onChange(v);
    setExpanded(false);
  };

  const handleDays = (d: number) => {
    setDays(d);
    setAwaitingDays(false);
    setIsSelected(true);
    onChange(HEALED_EARLY, d);
    setExpanded(false);
  };

  if (!expanded && isSelected) {
    const label = SORENESS_LABELS[internalValue - 1] ?? "";
    const showDays = internalValue === HEALED_EARLY && days !== null;
    return (
      <div className="mb-3 flex items-center gap-2 rounded-2xl border border-white/8 bg-black/20 px-3 py-2.5 text-xs">
        <span className="text-zinc-500">Recovery:</span>
        <span className="font-medium text-zinc-200">
          {label}
          {showDays && (
            <span className="text-zinc-400">
              {" "}· cleared in{" "}
              {dayLabel(days, days === dayOptions[dayOptions.length - 1], daysSinceLastTrained)}
            </span>
          )}
        </span>
        {!disabled && (
          <>
            <span className="ml-auto rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-emerald-200">
              logged
            </span>
          <button
            onClick={() => setExpanded(true)}
            className="text-zinc-500 underline underline-offset-2 hover:text-zinc-300"
          >
            edit
          </button>
          </>
        )}
      </div>
    );
  }

  return (
    <div
      className={`mb-3 rounded-2xl border p-3 transition-colors ${
        highlight
          ? "border-blue-500/70 bg-blue-500/10 ring-2 ring-blue-500/40"
          : "border-white/8 bg-black/20"
      }`}
    >
      <div className="mb-2 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-zinc-200">
            How did {muscleGroup} recover?
          </p>
          {daysSinceLastTrained != null && daysSinceLastTrained > 0 && (
            <p className="mt-0.5 text-xs text-zinc-500">
              Last trained {daysSinceLastTrained} {daysSinceLastTrained === 1 ? "day" : "days"} ago
            </p>
          )}
        </div>
        <span className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">
          pick one
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {SORENESS_LABELS.map((label, index) => {
          const optionValue = index + 1;
          const selected = optionValue === internalValue && (isSelected || awaitingDays);
          return (
            <button
              key={label}
              type="button"
              disabled={disabled}
              onClick={() => handleSelect(optionValue)}
              className={`rounded-xl border px-3 py-2.5 text-left text-xs transition-colors disabled:opacity-40 ${
                selected
                  ? "border-blue-500/60 bg-blue-600/40 text-blue-100"
                  : "border-white/20 bg-zinc-800 text-zinc-200 hover:border-white/30 hover:bg-zinc-700"
              }`}
            >
              {label}
            </button>
          );
        })}
      </div>

      {awaitingDays && (
        <div className="mt-3 rounded-xl border border-white/10 bg-zinc-900/80 p-3">
          <p className="mb-2 text-xs font-medium text-zinc-200">
            How many days until the soreness cleared?
          </p>
          <div className="flex flex-wrap gap-2">
            {dayOptions.map((d, index) => (
              <button
                key={d}
                type="button"
                disabled={disabled}
                onClick={() => handleDays(d)}
                className={`min-w-[4.5rem] rounded-xl border px-3 py-2.5 text-xs transition-colors disabled:opacity-40 ${
                  d === days
                    ? "border-blue-500/60 bg-blue-600/40 text-blue-100"
                    : "border-white/20 bg-zinc-800 text-zinc-200 hover:border-white/30 hover:bg-zinc-700"
                }`}
              >
                {dayLabel(d, index === dayOptions.length - 1, daysSinceLastTrained)}
              </button>
            ))}
          </div>
        </div>
      )}

      {!isSelected && !awaitingDays && (
        <p className="mt-2 text-center text-xs font-medium text-zinc-400">
          Pick one to start logging sets
        </p>
      )}
    </div>
  );
}
