"use client";
import { useState } from "react";

const SORENESS_LABELS = ["None", "Mild", "Moderate", "High", "Severe"];

interface SorenessSelectorProps {
  value: number | null;
  onChange: (v: number) => void;
  disabled: boolean;
}

export function SorenessSelector({ value, onChange, disabled }: SorenessSelectorProps) {
  const [expanded, setExpanded] = useState(value === null);

  const handleSelect = (v: number) => {
    onChange(v);
    setExpanded(false);
  };

  if (!expanded && value !== null) {
    // Collapsed summary
    return (
      <div className="flex items-center gap-2 mb-2 text-xs">
        <span className="text-zinc-500">Soreness:</span>
        <span className="text-zinc-300 font-medium">
          {value} · {SORENESS_LABELS[value - 1]}
        </span>
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

  // Expanded chip selector
  return (
    <div className="flex items-center gap-2 mb-2 flex-wrap">
      <span className="text-xs text-zinc-500 shrink-0">Soreness:</span>
      <div className="flex gap-1">
        {SORENESS_LABELS.map((label, i) => {
          const v = i + 1;
          const isSelected = value === v;
          return (
            <button
              key={v}
              onClick={() => handleSelect(v)}
              disabled={disabled}
              title={label}
              className={`w-8 h-7 rounded text-xs font-medium transition-colors
                ${isSelected
                  ? "bg-yellow-600 text-black"
                  : "bg-zinc-700 text-zinc-300 active:bg-zinc-600 disabled:opacity-30"
                }`}
            >
              {v}
            </button>
          );
        })}
      </div>
      {value === null && (
        <span className="text-xs text-zinc-600 shrink-0">← select to begin</span>
      )}
    </div>
  );
}
