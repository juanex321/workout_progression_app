"use client";
import { useState } from "react";
import { useFeedback } from "@/hooks/useFeedback";

interface FeedbackFormProps {
  muscleGroup: string;
  sessionId: number;
  initialValues?: { soreness: number; pump: number; workload: number };
  initialSoreness?: number;
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
      <div className="flex justify-between items-center mb-1">
        <label className="text-xs text-zinc-400">{label}</label>
        <span className="text-xs text-zinc-500">
          {descriptions[value - 1] ?? value}
        </span>
      </div>
      <input
        type="range"
        min={1}
        max={max}
        step={1}
        value={value}
        onChange={(e) => onChange(parseInt(e.target.value))}
        className="w-full h-2 rounded-lg appearance-none bg-zinc-700 accent-yellow-500"
      />
    </div>
  );
}

export function FeedbackForm({
  muscleGroup,
  sessionId,
  initialValues,
  initialSoreness,
}: FeedbackFormProps) {
  // Clamp to 4 since the soreness scale is now 1–4
  const [soreness, setSoreness] = useState(Math.min(initialValues?.soreness ?? initialSoreness ?? 3, 4));
  const [pump, setPump] = useState(initialValues?.pump ?? 3);
  const [workload, setWorkload] = useState(initialValues?.workload ?? 3);
  const [submitted, setSubmitted] = useState(false);

  const feedback = useFeedback(sessionId);

  const handleSubmit = () => {
    feedback.mutate(
      {
        session_id: sessionId,
        muscle_group: muscleGroup,
        soreness,
        pump,
        workload,
      },
      { onSuccess: () => setSubmitted(true) }
    );
  };

  if (submitted) {
    return (
      <div className="rounded-lg bg-green-500/10 border border-green-500/20 p-3 text-center">
        <p className="text-sm text-green-400">Feedback submitted</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg bg-zinc-800/50 p-3 space-y-3">
      <h4 className="text-sm font-medium text-zinc-300">
        {muscleGroup} Feedback
      </h4>
      <Slider label="Soreness" value={soreness} onChange={setSoreness} max={4} />
      <Slider label="Pump" value={pump} onChange={setPump} />
      <Slider label="Workload" value={workload} onChange={setWorkload} />
      <button
        onClick={handleSubmit}
        disabled={feedback.isPending}
        className="w-full h-10 rounded-lg bg-yellow-600 text-black font-medium text-sm
                   active:bg-yellow-500 disabled:opacity-50"
      >
        {feedback.isPending ? "Saving..." : "Submit Feedback"}
      </button>
    </div>
  );
}
