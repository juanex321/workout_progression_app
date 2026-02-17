import type {
  SessionResponse,
  WorkoutDataResponse,
  SaveSetsRequest,
  FeedbackRequest,
} from "./types";

const BASE = "/api";

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

export const api = {
  getCurrentSession(): Promise<SessionResponse> {
    return fetchJSON(`${BASE}/sessions/current`);
  },

  getSessionByNumber(sessionNumber: number): Promise<SessionResponse> {
    return fetchJSON(`${BASE}/sessions/${sessionNumber}`);
  },

  getWorkoutData(sessionId: number): Promise<WorkoutDataResponse> {
    return fetchJSON(`${BASE}/workout-data?session_id=${sessionId}`);
  },

  getWorkoutDataByNumber(sessionNumber: number): Promise<WorkoutDataResponse> {
    return fetchJSON(`${BASE}/workout-data?session_number=${sessionNumber}`);
  },

  saveSets(req: SaveSetsRequest): Promise<{ status: string }> {
    return fetchJSON(`${BASE}/sets/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
  },

  submitFeedback(req: FeedbackRequest): Promise<{ status: string }> {
    return fetchJSON(`${BASE}/feedback/muscle-group`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
  },

  completeSession(sessionId: number): Promise<SessionResponse> {
    return fetchJSON(`${BASE}/sessions/${sessionId}/complete`, {
      method: "POST",
    });
  },
};
