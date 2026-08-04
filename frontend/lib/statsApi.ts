import { API, qs } from "./http";

export type Rate = { person_frames: number; compliant_frames: number; rate: number | null };
export type ZoneStat = Rate & { zone: string };
export type Bucket = Rate & { bucket: string };
export type Stats = {
  global: Rate;
  by_zone: ZoneStat[];
  over_time: Bucket[];
  violations: { total: number; by_zone: Record<string, number> };
};

export async function getStats(
  params: { since?: string; until?: string; zone?: string } = {},
  fetchFn: typeof fetch = fetch,
): Promise<Stats> {
  const res = await fetchFn(`${API}/stats${qs(params)}`);
  if (!res.ok) throw new Error(`GET /stats -> ${res.status}`);
  return (await res.json()) as Stats;
}
