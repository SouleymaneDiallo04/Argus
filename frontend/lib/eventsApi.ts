import { API, qs } from "./http";

export type ApiEvent = {
  id: number; ts: string; stream_ts: number; camera: string;
  zone: string | null; track_id: number; missing: string[]; snapshot: string | null;
};

export async function getEvents(
  params: { zone?: string; ppe?: string; since?: string; until?: string; limit?: number } = {},
  fetchFn: typeof fetch = fetch,
): Promise<ApiEvent[]> {
  const res = await fetchFn(`${API}/events${qs(params)}`);
  if (!res.ok) throw new Error(`GET /events -> ${res.status}`);
  const data = (await res.json()) as { events: ApiEvent[] };
  return data.events ?? [];
}

export function snapshotUrl(id: number): string {
  return `${API}/events/${id}/snapshot`;
}
