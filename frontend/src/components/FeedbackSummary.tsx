"use client";
import { useState } from "react";
import { FeedbackForm } from "./FeedbackForm";

interface FeedbackSummaryProps {
  muscleGroup: string;
  values: { soreness: number; pump: number; workload: number } | null;
  sessionId: number;
  disabled: boolean;
}

export function FeedbackSummary({
  muscleGroup,
  values,
  sessionId,
  disabled,
}: FeedbackSummaryProps) {
  const [editing, setEditing] = useState(false);

  if (!values) return null;

  if (editing) {
    return (
      <FeedbackForm
        muscleGroup={muscleGroup}
        sessionId={sessionId}
        initialValues={values}
      />
    );
  }

  return (
    <div className="rounded-lg bg-zinc-800/50 p-3 flex items-center justify-between">
      <div className="text-xs text-zinc-400 space-x-3">
        <span>Soreness: {values.soreness}</span>
        <span>Pump: {values.pump}</span>
        <span>Workload: {values.workload}</span>
      </div>
      {!disabled && (
        <button
          onClick={() => setEditing(true)}
          className="text-xs text-yellow-500 hover:text-yellow-400"
        >
          Edit
        </button>
      )}
    </div>
  );
}
