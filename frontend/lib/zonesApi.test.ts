import { getZones, putZones } from "./zonesApi";
import { getZoneRisk, setZoneRisk } from "./zoneRiskStore";

function mockFetch(body: unknown, ok = true, status = 200) {
  return async () => ({ ok, status, json: async () => body }) as Response;
}

test("getZones renvoie la liste de zones", async () => {
  const zones = await getZones(
    mockFetch({ zones: [{ name: "z", polygon: [[0, 0], [10, 0], [10, 10]], required_ppe: ["helmet"] }] }) as typeof fetch
  );
  expect(zones).toHaveLength(1);
  expect(zones[0].name).toBe("z");
});

test("putZones envoie un PUT et rejette sur erreur HTTP", async () => {
  let captured: RequestInit | undefined;
  const fetchFn = (async (_url: string, init?: RequestInit) => {
    captured = init;
    return { ok: true, status: 200, json: async () => ({}) } as Response;
  }) as typeof fetch;
  await putZones([{ name: "z", polygon: [[0, 0], [10, 0], [10, 10]], required_ppe: ["helmet"] }], fetchFn);
  expect(captured?.method).toBe("PUT");
  expect(JSON.parse(captured?.body as string)).toEqual({
    zones: [{ name: "z", polygon: [[0, 0], [10, 0], [10, 10]], required_ppe: ["helmet"] }],
  });
  await expect(putZones([], mockFetch({}, false, 422) as typeof fetch)).rejects.toThrow();
});

test("zoneRiskStore persiste le risque par nom", () => {
  setZoneRisk("Fonderie", "high");
  expect(getZoneRisk("Fonderie")).toBe("high");
  expect(getZoneRisk("Inconnue")).toBeUndefined();
});
