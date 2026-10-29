"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useSessionData(sessionId: number | null) {
  return useQuery({
    queryKey: ["workout-data-v2", sessionId],
    queryFn: () => api.getWorkoutData(sessionId!),
    enabled: !!sessionId,
    staleTime: Infinity, // Load once and hold locally during a session
    // The bootstrap request already populates this cache. Do not fetch it twice.
    refetchOnMount: true,
    gcTime: 10 * 60 * 1000,
  });
}

export function useCurrentSession() {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: ["current-session"],
    queryFn: async () => {
      const workout = await api.getCurrentWorkout();
      queryClient.setQueryData(["workout-data-v2", workout.session_id], workout);
      return workout;
    },
    staleTime: 30_000,
  });
}
