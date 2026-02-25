"use client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { SorenessRequest } from "@/lib/types";

export function useSoreness(sessionId: number | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: SorenessRequest) => api.saveSoreness(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workout-data", sessionId] });
    },
  });
}
