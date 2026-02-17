"use client";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { SaveSetsRequest } from "@/lib/types";

export function useLogSet() {
  return useMutation({
    mutationFn: (data: SaveSetsRequest) => api.saveSets(data),
  });
}
