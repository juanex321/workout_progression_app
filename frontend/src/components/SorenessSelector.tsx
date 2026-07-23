"use client";
import { useState } from "react";

const SORENESS_LABELS = [
  "Never got sore",
  "Healed a while ago",
  "Healed right on time",
  "I'm still sore",
];

interface SorenessSelectorProps {
  muscleGroup: string;
  value: number | null;
  onChange: (v: number) => void;
  disabled: boolean;
}

export function SorenessSelector({
  muscleGroup,
  value,
  onChange,
  disabled,
}: SorenessSelectorProps) {
  const [internalValue, setInternalValue] = useState(value ?? 2);
  const [isSelected, setIsSelected] = useState(value !== null);
  const [expanded, setExpanded] = useState(value === null);

  const handleSelect = (v: number) => {
    setInternalValue(v);
    setIsSelected(true);
    onChange(v);
    setExpanded(false);
  };

  if (!expanded && isSelected) {
    const label = SORENESS_LABELS[internalValue - 1] ?? "";
    return (
      <div className="mb-3 flex items-center gap-2 rounded-2xl border border-white/8 bg-black/20 px-3 py-2.5 text-xs">
        <span className="text-zinc-500">Recovery:</span>
        <span className="font-medium text-zinc-200">{label}</span>
        {!disabled && (
          <>
            <span className="ml-auto rounded-full border border-red-400/20 bg-red-400/10 px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-red-200">
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
    <div className="mb-3 rounded-2xl border border-white/8 bg-black/20 p-3">
      <div className="mb-2 flex items-center justify-between gap-3">
        <p className="text-sm font-medium text-zinc-200">
          How did {muscleGroup} recover?
        </p>
        <span className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">
          pick one
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {SORENESS_LABELS.map((label, index) => {
          const optionValue = index + 1;
          const selected = optionValue === internalValue && isSelected;
          return (
            <button
              key={label}
              type="button"
              disabled={disabled}
              onClick={() => handleSelect(optionValue)}
              className={`rounded-xl border px-3 py-2.5 text-left text-xs transition-colors disabled:opacity-40 ${
                selected
                  ? "border-red-500/60 bg-red-600/40 text-red-100"
                  : "border-white/20 bg-zinc-800 text-zinc-200 hover:border-white/30 hover:bg-zinc-700"
              }`}
            >
              {label}
            </button>
          );
        })}
      </div>

      {!isSelected && (
        <p className="mt-2 text-center text-[10px] uppercase tracking-[0.16em] text-zinc-600">
          choose recovery to begin logging sets
        </p>
      )}
    </div>
  );
}
