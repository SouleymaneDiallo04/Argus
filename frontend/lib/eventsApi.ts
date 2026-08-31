import { API, qs } from "./http";
import type { AlertStatus } from "@/components/ui/StatusBadge";

export type ApiEvent = {
  id: number; ts: string; stream_ts: number; camera: string;
  zone: string | null; track_id: number; missing: string[]; snapshot: string | null;
  status: AlertStatus;
};

export async function getEvents(
  params: { zone?: string; ppe?: string; since?: string; until?: string;
            status?: string; limit?: number } = {},
  fetchFn: typeof fetch = fetch,
): Promise<ApiEvent[]> {
  const res = await fetchFn(`${API}/events${qs(params)}`);
  if (!res.ok) throw new Error(`GET /events -> ${res.status}`);
  const data = (await res.json()) as { events: ApiEvent[] };
  return data.events ?? [];
}

export async function setEventStatus(
  id: number, status: AlertStatus, fetchFn: typeof fetch = fetch,
): Promise<void> {
  const res = await fetchFn(`${API}/events/${id}/status`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error(`POST /events/${id}/status -> ${res.status}`);
}

export function snapshotUrl(id: number): string {
  return `${API}/events/${id}/snapshot`;
}
