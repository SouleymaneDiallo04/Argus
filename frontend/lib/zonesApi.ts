export type ApiZone = { name: string; polygon: [number, number][]; required_ppe: string[] };
type ZonesConfig = { zones: ApiZone[] };

const API = process.env.NEXT_PUBLIC_ARGUS_API ?? "http://localhost:8000";

export async function getZones(fetchFn: typeof fetch = fetch): Promise<ApiZone[]> {
  const res = await fetchFn(`${API}/zones`);
  if (!res.ok) throw new Error(`GET /zones -> ${res.status}`);
  const data = (await res.json()) as ZonesConfig;
  return data.zones ?? [];
}

export async function putZones(zones: ApiZone[], fetchFn: typeof fetch = fetch): Promise<void> {
  const res = await fetchFn(`${API}/zones`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ zones }),
  });
  if (!res.ok) throw new Error(`PUT /zones -> ${res.status}`);
}
