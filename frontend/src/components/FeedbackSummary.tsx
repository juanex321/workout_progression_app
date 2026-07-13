"use client";
import { useState } from "react";
import { FeedbackForm } from "./FeedbackForm";

type FeedbackValues = { soreness: number; pump: number; workload: number };

interface FeedbackSummaryProps {
  muscleGroup: string;
  values: FeedbackValues | null;
  sessionId: number;
  disabled?: boolean;
  onSaved?: (values: FeedbackValues) => void;
}

const SORENESS_LABELS = ["Never sore", "Healed early", "Healed on time", "Still sore"];
const PUMP_LABELS = ["None", "Slight", "Good", "Great", "Extreme"];
const WORKLOAD_LABELS = ["Easy", "Light", "Just right", "Hard", "Too much"];

export function FeedbackSummary({
  muscleGroup,
  values,
  sessionId,
  onSaved,
}: FeedbackSummaryProps) {
  const [editing, setEditing] = useState(false);
  const [currentValues, setCurrentValues] = useState(values);

  if (!currentValues) return null;

  if (editing) {
    return (
      <FeedbackForm
        muscleGroup={muscleGroup}
        sessionId={sessionId}
        initialValues={currentValues}
        onCancel={() => setEditing(false)}
        onSaved={(nextValues) => {
          setCurrentValues(nextValues);
          setEditing(false);
          onSaved?.(nextValues);
        }}
      />
    );
  }

  return (
    <div className="rounded-2xl border border-emerald-400/25 bg-emerald-500/10 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-300">
            Feedback logged
          </p>
          <p className="mt-1 text-sm text-zinc-200">
            Pump and workload can be changed at any time.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="min-h-11 shrink-0 rounded-xl border border-yellow-300/50 bg-yellow-400 px-4 text-sm font-extrabold text-zinc-950 shadow-lg shadow-yellow-500/10 active:bg-yellow-300"
        >
          Edit feedback
        </button>
      </div>

      <button
        type="button"
        onClick={() => setEditing(true)}
        className="mt-3 grid w-full gap-2 text-left sm:grid-cols-3"
        aria-label={`Edit ${muscleGroup} feedback`}
      >
        <span className="rounded-xl border border-white/10 bg-black/30 px-3 py-3">
          <span className="block text-[10px] uppercase tracking-[0.16em] text-zinc-500">Soreness</span>
          <span className="mt-1 block text-sm font-semibold text-zinc-100">
            {currentValues.soreness}/4 · {SORENESS_LABELS[currentValues.soreness - 1]}
          </span>
        </span>
        <span className="rounded-xl border border-yellow-400/20 bg-black/30 px-3 py-3">
          <span className="block text-[10px] uppercase tracking-[0.16em] text-zinc-500">Pump</span>
          <span className="mt-1 block text-sm font-semibold text-zinc-100">
            {currentValues.pump}/5 · {PUMP_LABELS[currentValues.pump - 1]}
          </span>
        </span>
        <span className="rounded-xl border border-yellow-400/20 bg-black/30 px-3 py-3">
          <span className="block text-[10px] uppercase tracking-[0.16em] text-zinc-500">Workload</span>
          <span className="mt-1 block text-sm font-semibold text-zinc-100">
            {currentValues.workload}/5 · {WORKLOAD_LABELS[currentValues.workload - 1]}
          </span>
        </span>
      </button>
      <p className="mt-2 text-center text-xs font-medium text-yellow-300">
        Tap Edit feedback or any saved value to change it
      </p>
    </div>
  );
}
