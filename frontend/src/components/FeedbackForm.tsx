"use client";
import { useState } from "react";
import { useFeedback } from "@/hooks/useFeedback";

type FeedbackValues = { soreness: number; pump: number; workload: number };

interface FeedbackFormProps {
  muscleGroup: string;
  sessionId: number;
  initialValues?: FeedbackValues;
  initialSoreness?: number;
  onSaved?: (values: FeedbackValues) => void;
  onCancel?: () => void;
}

const LABELS: Record<string, string[]> = {
  soreness: ["Never got sore", "Healed a while ago", "Healed right on time", "I'm still sore"],
  pump: ["None", "Slight", "Good", "Great", "Extreme"],
  workload: ["Easy", "Light", "Just Right", "Hard", "Too Much"],
};

function Slider({
  label,
  value,
  onChange,
  max = 5,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  max?: number;
}) {
  const key = label.toLowerCase();
  const descriptions = LABELS[key] ?? [];

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-3">
        <label className="text-sm font-medium text-zinc-200">{label}</label>
        <span className="text-sm text-zinc-400">{descriptions[value - 1] ?? value}</span>
      </div>
      <input
        type="range"
        min={1}
        max={max}
        step={1}
        value={value}
        onChange={(e) => onChange(parseInt(e.target.value))}
        className="h-3 w-full appearance-none rounded-lg bg-zinc-700 accent-red-500"
      />
    </div>
  );
}

function ChipSelect({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: string[];
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <p className="mb-2 text-sm font-medium text-zinc-200">{label}</p>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        {options.map((opt, i) => {
          const v = i + 1;
          const selected = value === v;
          return (
            <button
              key={opt}
              type="button"
              onClick={() => onChange(v)}
              className={`min-h-12 rounded-xl px-2 py-2 text-sm font-semibold transition-colors ${
                selected
                  ? "bg-red-600 text-white shadow-[0_0_0_2px_rgba(220,38,38,0.25)]"
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
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-red-400">Session feedback</p>
        <h4 className="mt-1 text-lg font-bold text-zinc-50">{muscleGroup}</h4>
      </div>
      <Slider label="Soreness" value={soreness} onChange={setSoreness} max={4} />
      <ChipSelect label="Pump" options={LABELS.pump} value={pump} onChange={setPump} />
      <ChipSelect label="Workload" options={LABELS.workload} value={workload} onChange={setWorkload} />
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
          className="h-12 flex-[2] rounded-xl bg-red-600 text-base font-bold text-white active:bg-red-500 disabled:opacity-50"
        >
          {feedback.isPending ? "Saving..." : initialValues ? "Save Changes" : "Submit Feedback"}
        </button>
      </div>
    </div>
  );
}
