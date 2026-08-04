import { getStats } from "./statsApi";

test("getStats parse la réponse et passe les filtres en query", async () => {
  let url = "";
  const fetchFn = (async (u: string) => {
    url = u;
    return { ok: true, status: 200, json: async () => ({
      global: { person_frames: 10, compliant_frames: 8, rate: 0.8 },
      by_zone: [], over_time: [], violations: { total: 0, by_zone: {} },
    }) } as Response;
  }) as typeof fetch;
  const s = await getStats({ zone: "Fonderie" }, fetchFn);
  expect(s.global.rate).toBe(0.8);
  expect(url).toContain("/stats?");
  expect(url).toContain("zone=Fonderie");
});
