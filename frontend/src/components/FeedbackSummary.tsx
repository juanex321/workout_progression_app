"use client";
import { useState } from "react";
import { FeedbackForm } from "./FeedbackForm";

type FeedbackValues = { soreness: number; pump: number; workload: number };

interface FeedbackSummaryProps {
  muscleGroup: string;
  values: FeedbackValues | null;
  sessionId: number;
  disabled: boolean;
  onSaved?: (values: FeedbackValues) => void;
}

const SORENESS_LABELS = ["Never sore", "Healed early", "Healed on time", "Still sore"];
const PUMP_LABELS = ["None", "Slight", "Good", "Great", "Extreme"];
const WORKLOAD_LABELS = ["Easy", "Light", "Just right", "Hard", "Too much"];

export function FeedbackSummary({
  muscleGroup,
  values,
  sessionId,
  disabled,
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
    <div className="rounded-2xl border border-emerald-400/20 bg-emerald-500/8 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-300">Feedback logged</p>
          <p className="mt-1 text-sm text-zinc-300">Tap edit if anything was selected by mistake.</p>
        </div>
        {!disabled && (
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="min-h-10 rounded-xl border border-yellow-400/30 bg-yellow-500/10 px-4 text-sm font-bold text-yellow-300 active:bg-yellow-500/20"
          >
            Edit
          </button>
        )}
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        <div className="rounded-xl bg-black/25 px-3 py-2">
          <p className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Soreness</p>
          <p className="mt-1 text-sm font-semibold text-zinc-100">
            {currentValues.soreness}/4 · {SORENESS_LABELS[currentValues.soreness - 1]}
          </p>
        </div>
        <div className="rounded-xl bg-black/25 px-3 py-2">
          <p className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Pump</p>
          <p className="mt-1 text-sm font-semibold text-zinc-100">
            {currentValues.pump}/5 · {PUMP_LABELS[currentValues.pump - 1]}
          </p>
        </div>
        <div className="rounded-xl bg-black/25 px-3 py-2">
          <p className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Workload</p>
          <p className="mt-1 text-sm font-semibold text-zinc-100">
            {currentValues.workload}/5 · {WORKLOAD_LABELS[currentValues.workload - 1]}
          </p>
        </div>
      </div>
    </div>
  );
}
