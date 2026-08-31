import { getEvents, setEventStatus, snapshotUrl } from "./eventsApi";

test("setEventStatus poste le statut", async () => {
  let url = "";
  let init: RequestInit | undefined;
  const fetchFn = (async (u: string, i?: RequestInit) => {
    url = u; init = i;
    return { ok: true, status: 200, json: async () => ({}) } as Response;
  }) as typeof fetch;
  await setEventStatus(1, "ack", fetchFn);
  expect(url).toContain("/events/1/status");
  expect(init?.method).toBe("POST");
  expect(JSON.parse(init?.body as string)).toEqual({ status: "ack" });
});

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
