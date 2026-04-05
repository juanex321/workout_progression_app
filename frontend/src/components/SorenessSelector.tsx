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
  // internalValue drives the slider position visually; defaults to 2 so the thumb
  // sits at a visible, non-extreme position before the user interacts.
  const [internalValue, setInternalValue] = useState(value ?? 2);
  const [isSelected, setIsSelected] = useState(value !== null);
  const [expanded, setExpanded] = useState(value === null);

  const handlePointerDown = () => {
    if (!isSelected) {
      setIsSelected(true);
      onChange(internalValue);
    }
  };

  const handleChange = (v: number) => {
    setInternalValue(v);
    if (!isSelected) setIsSelected(true);
    onChange(v);
  };

  // Collapse to compact summary once the user releases the slider
  const handlePointerUp = () => {
    setExpanded(false);
  };

  // Collapsed summary after selection
  if (!expanded && isSelected) {
    const label = SORENESS_LABELS[internalValue - 1] ?? "";
    return (
      <div className="mb-3 flex items-center gap-2 rounded-full border border-white/8 bg-black/20 px-3 py-2 text-xs">
        <span className="text-zinc-500">Recovery:</span>
        <span className="font-medium text-zinc-200">{label}</span>
        {!disabled && (
          <button
            onClick={() => setExpanded(true)}
            className="text-zinc-500 underline underline-offset-2 hover:text-zinc-300"
          >
            edit
          </button>
        )}
      </div>
    );
  }

  // Prominent unset block
  const accentClass = isSelected ? "accent-amber-400" : "accent-zinc-500";
  const currentLabel = isSelected ? SORENESS_LABELS[internalValue - 1] : null;

  return (
    <div className="mb-3 rounded-2xl border border-white/8 bg-black/20 p-3">
      <div className="mb-2 flex items-center justify-between gap-3">
        <p className="text-sm font-medium text-zinc-200">
          How did {muscleGroup} recover?
        </p>
        {currentLabel && (
          <span className="text-xs font-medium text-amber-300">{currentLabel}</span>
        )}
      </div>

      <input
        type="range"
        min={1}
        max={4}
        step={1}
        value={internalValue}
        disabled={disabled}
        onPointerDown={handlePointerDown}
        onPointerUp={handlePointerUp}
        onChange={(e) => handleChange(parseInt(e.target.value))}
        className={`h-2 w-full appearance-none rounded-lg bg-zinc-700 ${accentClass} disabled:opacity-40`}
      />

      {/* Stop labels */}
      <div className="mt-2 grid grid-cols-4 gap-2">
        {SORENESS_LABELS.map((label) => (
          <span
            key={label}
            className="text-center text-[10px] leading-tight text-zinc-500"
          >
            {label}
          </span>
        ))}
      </div>

      {!isSelected && (
        <p className="mt-2 text-center text-[10px] uppercase tracking-[0.16em] text-zinc-600">
          slide to begin logging sets
        </p>
      )}
    </div>
  );
}
