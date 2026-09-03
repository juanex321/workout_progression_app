"use client";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { SaveDraftRequest } from "@/lib/types";

/**
 * Background autosave for in-progress (not yet logged) set values. Fire and
 * forget - localStorage is still the fast path for the same browser, this
 * just gives unlogged edits a server-side backup for a cleared browser or a
 * different device.
 */
export function useSaveDraft() {
  return useMutation({
    mutationFn: (data: SaveDraftRequest) => api.saveDraft(data),
  });
}
