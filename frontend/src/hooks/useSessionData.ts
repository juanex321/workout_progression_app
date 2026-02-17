"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useSessionData(sessionId: number | null) {
  return useQuery({
    queryKey: ["workout-data", sessionId],
    queryFn: () => api.getWorkoutData(sessionId!),
    enabled: !!sessionId,
    staleTime: Infinity, // "Load once, hold locally" — matches Streamlit pattern
    gcTime: 10 * 60 * 1000,
  });
}

export function useCurrentSession() {
  return useQuery({
    queryKey: ["current-session"],
    queryFn: () => api.getCurrentSession(),
    staleTime: 30_000,
  });
}
