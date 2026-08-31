import { startRtsp, stopRtsp, rtspStatus } from "./sourcesApi";

test("startRtsp poste l'URL", async () => {
  let url = ""; let init: RequestInit | undefined;
  const fetchFn = (async (u: string, i?: RequestInit) => {
    url = u; init = i;
    return { ok: true, status: 200, json: async () => ({ running: true, url: "rtsp://x", frames: 0 }) } as Response;
  }) as typeof fetch;
  const st = await startRtsp("rtsp://x", fetchFn);
  expect(url).toContain("/sources/rtsp");
  expect(init?.method).toBe("POST");
  expect(JSON.parse(init?.body as string)).toEqual({ url: "rtsp://x" });
  expect(st.running).toBe(true);
});

test("stopRtsp fait un DELETE", async () => {
  let method = "";
  const fetchFn = (async (_u: string, i?: RequestInit) => {
    method = i?.method ?? "GET";
    return { ok: true, status: 200, json: async () => ({}) } as Response;
  }) as typeof fetch;
  await stopRtsp(fetchFn);
  expect(method).toBe("DELETE");
});

test("rtspStatus parse le statut", async () => {
  const fetchFn = (async () => ({ ok: true, status: 200, json: async () => ({ running: false }) }) as Response) as typeof fetch;
  expect((await rtspStatus(fetchFn)).running).toBe(false);
});
