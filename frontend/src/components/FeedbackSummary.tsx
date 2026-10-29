"use client";
import { useState } from "react";
import { FeedbackForm } from "./FeedbackForm";
import { PUMP_LABELS, SORENESS_LABELS, WORKLOAD_LABELS } from "@/lib/feedbackLabels";

type FeedbackValues = { soreness: number; pump: number; workload: number };

interface FeedbackSummaryProps {
  muscleGroup: string;
  values: FeedbackValues | null;
  sessionId: number;
  disabled?: boolean;
  onSaved?: (values: FeedbackValues) => void;
}

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

  const items = [
    { label: "Recovery", value: SORENESS_LABELS[currentValues.soreness - 1] },
    { label: "Pump", value: PUMP_LABELS[currentValues.pump - 1] },
    { label: "Workload", value: WORKLOAD_LABELS[currentValues.workload - 1] },
  ];

  return (
    <div className="rounded-2xl border border-emerald-400/25 bg-emerald-500/10 p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-300">
          Feedback saved
        </p>
        <button
          type="button"
          onClick={() => setEditing(true)}
          aria-label={`Edit ${muscleGroup} feedback`}
          className="min-h-11 shrink-0 rounded-xl border border-white/15 bg-zinc-800 px-4 text-sm font-semibold text-zinc-200 active:bg-zinc-700"
        >
          Edit
        </button>
      </div>

      <dl className="mt-3 grid gap-2 sm:grid-cols-3">
        {items.map((item) => (
          <div key={item.label} className="rounded-xl border border-white/10 bg-black/30 px-3 py-3">
            <dt className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">{item.label}</dt>
            <dd className="mt-1 text-sm font-semibold text-zinc-100">{item.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
