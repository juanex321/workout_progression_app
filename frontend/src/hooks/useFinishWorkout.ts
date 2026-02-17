"use client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useFinishWorkout() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (sessionId: number) => api.completeSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["current-session"] });
      queryClient.invalidateQueries({ queryKey: ["workout-data"] });
    },
  });
}
