import { getEvents, snapshotUrl } from "./eventsApi";

test("getEvents renvoie la liste et passe les filtres", async () => {
  let url = "";
  const fetchFn = (async (u: string) => {
    url = u;
    return { ok: true, status: 200, json: async () => ({
      events: [{ id: 1, ts: "t", stream_ts: 0, camera: "c", zone: "Z",
                 track_id: 3, missing: ["helmet"], snapshot: "a.jpg" }],
    }) } as Response;
  }) as typeof fetch;
  const ev = await getEvents({ ppe: "helmet", limit: 50 }, fetchFn);
  expect(ev).toHaveLength(1);
  expect(ev[0].snapshot).toBe("a.jpg");
  expect(url).toContain("ppe=helmet");
  expect(url).toContain("limit=50");
});

test("snapshotUrl construit l'URL du snapshot", () => {
  expect(snapshotUrl(7)).toContain("/events/7/snapshot");
});
