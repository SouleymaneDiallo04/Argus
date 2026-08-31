import { API } from "./http";

export type RtspStatus = {
  running: boolean; url?: string; frames?: number; error?: string | null;
};

export async function startRtsp(url: string, fetchFn: typeof fetch = fetch): Promise<RtspStatus> {
  const res = await fetchFn(`${API}/sources/rtsp`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) throw new Error(`POST /sources/rtsp -> ${res.status}`);
  return (await res.json()) as RtspStatus;
}

export async function stopRtsp(fetchFn: typeof fetch = fetch): Promise<void> {
  const res = await fetchFn(`${API}/sources/rtsp`, { method: "DELETE" });
  if (!res.ok) throw new Error(`DELETE /sources/rtsp -> ${res.status}`);
}

export async function rtspStatus(fetchFn: typeof fetch = fetch): Promise<RtspStatus> {
  const res = await fetchFn(`${API}/sources/rtsp`);
  if (!res.ok) throw new Error(`GET /sources/rtsp -> ${res.status}`);
  return (await res.json()) as RtspStatus;
}
