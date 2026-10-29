"use client";
import { useState } from "react";
import { useFeedback } from "@/hooks/useFeedback";
import { PUMP_LABELS, SORENESS_LABELS, WORKLOAD_LABELS } from "@/lib/feedbackLabels";

type FeedbackValues = { soreness: number; pump: number; workload: number };

interface FeedbackFormProps {
  muscleGroup: string;
  sessionId: number;
  initialValues?: FeedbackValues;
  initialSoreness?: number;
  onSaved?: (values: FeedbackValues) => void;
  onCancel?: () => void;
}

function ChipSelect({
  label,
  options,
  value,
  onChange,
  columns = "sm:grid-cols-5",
}: {
  label: string;
  options: string[];
  value: number;
  onChange: (v: number) => void;
  columns?: string;
}) {
  return (
    <div>
      <p className="mb-2 text-sm font-medium text-zinc-200">{label}</p>
      <div className={`grid grid-cols-2 gap-2 ${columns}`}>
        {options.map((opt, i) => {
          const v = i + 1;
          const selected = value === v;
          return (
            <button
              key={opt}
              type="button"
              onClick={() => onChange(v)}
              aria-pressed={selected}
              className={`min-h-12 rounded-xl px-2 py-2 text-sm font-semibold transition-colors ${
                selected
                  ? "bg-blue-600 text-white shadow-[0_0_0_2px_rgba(37,99,235,0.25)]"
                  : "border border-white/10 bg-zinc-700 text-zinc-200 active:bg-zinc-600"
              }`}
            >
              {opt}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function FeedbackForm({
  muscleGroup,
  sessionId,
  initialValues,
  initialSoreness,
  onSaved,
  onCancel,
}: FeedbackFormProps) {
  const [soreness, setSoreness] = useState(
    Math.min(initialValues?.soreness ?? initialSoreness ?? 3, 4)
  );
  const [pump, setPump] = useState(initialValues?.pump ?? 3);
  const [workload, setWorkload] = useState(initialValues?.workload ?? 3);
  const feedback = useFeedback(sessionId);

  // Recovery is already answered at the top of the card before logging, so
  // only ask again when editing saved feedback (where that picker is hidden).
  const showSoreness = !!initialValues || initialSoreness === undefined;

  const handleSubmit = () => {
    const values = { soreness, pump, workload };
    feedback.mutate(
      {
        session_id: sessionId,
        muscle_group: muscleGroup,
        ...values,
      },
      { onSuccess: () => onSaved?.(values) }
    );
  };

  return (
    <div className="space-y-5 rounded-2xl border border-white/10 bg-zinc-900/95 p-4 shadow-[0_16px_35px_rgba(0,0,0,0.3)]">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-400">Session feedback</p>
        <h4 className="mt-1 text-lg font-bold text-zinc-50">{muscleGroup}</h4>
      </div>
      {showSoreness && (
        <ChipSelect
          label="Recovery"
          options={SORENESS_LABELS}
          value={soreness}
          onChange={setSoreness}
          columns="sm:grid-cols-4"
        />
      )}
      <ChipSelect label="Pump" options={PUMP_LABELS} value={pump} onChange={setPump} />
      <ChipSelect label="Workload" options={WORKLOAD_LABELS} value={workload} onChange={setWorkload} />
      {feedback.isError && (
        <p className="text-sm text-red-300">Save failed. Review the selections and try again.</p>
      )}
      <div className="flex gap-2">
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            disabled={feedback.isPending}
            className="h-12 flex-1 rounded-xl border border-white/15 bg-zinc-800 text-sm font-semibold text-zinc-200 disabled:opacity-50"
          >
            Cancel
          </button>
        )}
        <button
          type="button"
          onClick={handleSubmit}
          disabled={feedback.isPending}
          className="h-12 flex-[2] rounded-xl bg-blue-600 text-base font-bold text-white active:bg-blue-500 disabled:opacity-50"
        >
          {feedback.isPending ? "Saving..." : initialValues ? "Save Changes" : "Submit Feedback"}
        </button>
      </div>
    </div>
  );
}
