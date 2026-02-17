"use client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { FeedbackRequest } from "@/lib/types";

export function useFeedback(sessionId: number | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: FeedbackRequest) => api.submitFeedback(data),
    onSuccess: () => {
      // Refresh workout data after feedback submission
      queryClient.invalidateQueries({ queryKey: ["workout-data", sessionId] });
    },
  });
}
