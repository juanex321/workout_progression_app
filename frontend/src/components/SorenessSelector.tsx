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

  // Collapsed summary after selection
  if (!expanded && isSelected) {
    const label = SORENESS_LABELS[internalValue - 1] ?? "";
    return (
      <div className="flex items-center gap-2 mb-3 text-xs">
        <span className="text-zinc-500">Recovery:</span>
        <span className="text-zinc-300 font-medium">{label}</span>
        {!disabled && (
          <button
            onClick={() => setExpanded(true)}
            className="text-zinc-500 hover:text-zinc-300 underline underline-offset-2"
          >
            edit
          </button>
        )}
      </div>
    );
  }

  // Prominent unset block
  const accentClass = isSelected ? "accent-yellow-500" : "accent-zinc-500";
  const currentLabel = isSelected ? SORENESS_LABELS[internalValue - 1] : null;

  return (
    <div className="rounded-lg bg-zinc-800/70 border border-zinc-700 p-3 mb-3">
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm font-medium text-zinc-200">
          How did {muscleGroup} recover?
        </p>
        {currentLabel && (
          <span className="text-xs text-yellow-400 font-medium">{currentLabel}</span>
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
        onChange={(e) => handleChange(parseInt(e.target.value))}
        className={`w-full h-2 rounded-lg appearance-none bg-zinc-700 ${accentClass} disabled:opacity-40`}
      />

      {/* Stop labels */}
      <div className="flex justify-between mt-1.5 px-0.5">
        {SORENESS_LABELS.map((label) => (
          <span
            key={label}
            className="text-[10px] text-zinc-500 text-center leading-tight"
            style={{ width: "25%" }}
          >
            {label}
          </span>
        ))}
      </div>

      {!isSelected && (
        <p className="text-[10px] text-zinc-600 mt-2 text-center">
          slide to begin logging sets
        </p>
      )}
    </div>
  );
}
