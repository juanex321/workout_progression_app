/**
 * localStorage draft persistence for in-progress workout sets and soreness.
 * Keyed by sessionId so stale drafts from previous sessions are ignored.
 */

interface DraftSet {
  set_number: number;
  weight: number;
  reps: number;
}

interface ExerciseDraft {
  sets: DraftSet[];
}

interface SessionDraft {
  sessionId: number;
  exercises: Record<number, ExerciseDraft>; // keyed by workout_exercise_id
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

export function saveDraftSets(
  sessionId: number,
  weId: number,
  sets: DraftSet[]
): void {
  try {
    const draft = getDraft(sessionId) ?? {
      sessionId,
      exercises: {},
      soreness: {},
    };
    draft.exercises[weId] = { sets };
    localStorage.setItem(key(sessionId), JSON.stringify(draft));
  } catch {
    // localStorage can be unavailable (private browsing quotas, etc.) — fail silently
  }
}

export function saveDraftSoreness(
  sessionId: number,
  muscleGroup: string,
  soreness: number
): void {
  try {
    const draft = getDraft(sessionId) ?? {
      sessionId,
      exercises: {},
      soreness: {},
    };
    draft.soreness[muscleGroup] = soreness;
    localStorage.setItem(key(sessionId), JSON.stringify(draft));
  } catch {
    // fail silently
  }
}

export function clearDraftExercise(sessionId: number, weId: number): void {
  try {
    const draft = getDraft(sessionId);
    if (!draft) return;
    delete draft.exercises[weId];
    localStorage.setItem(key(sessionId), JSON.stringify(draft));
  } catch {
    // fail silently
  }
}

export function clearDraft(sessionId: number): void {
  try {
    localStorage.removeItem(key(sessionId));
  } catch {
    // fail silently
  }
}
