/**
 * localStorage draft persistence for in-progress soreness ratings.
 * Keyed by sessionId so stale drafts from previous sessions are ignored.
 */

interface SessionDraft {
  sessionId: number;
  soreness: Record<string, number>; // keyed by muscle_group
}

function key(sessionId: number): string {
  return `workout_draft_${sessionId}`;
}

export function getDraft(sessionId: number): SessionDraft | null {
  try {
    const raw = localStorage.getItem(key(sessionId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as SessionDraft;
    if (parsed.sessionId !== sessionId) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function saveDraftSoreness(
  sessionId: number,
  muscleGroup: string,
  soreness: number
): void {
  try {
    const draft = getDraft(sessionId) ?? { sessionId, soreness: {} };
    draft.soreness[muscleGroup] = soreness;
    localStorage.setItem(key(sessionId), JSON.stringify(draft));
  } catch {
    // fail silently
  }
}
