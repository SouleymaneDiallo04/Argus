import { getToken, setToken, clearToken, authFetch } from "./http";

test("token helpers persistent en localStorage", () => {
  clearToken();
  expect(getToken()).toBeNull();
  setToken("abc");
  expect(getToken()).toBe("abc");
  clearToken();
  expect(getToken()).toBeNull();
});

test("authFetch ajoute le header Bearer si token présent", async () => {
  setToken("tok");
  let seen: Headers | undefined;
  const orig = global.fetch;
  global.fetch = (async (_u: string, i?: RequestInit) => {
    seen = new Headers(i?.headers); return { ok: true } as Response;
  }) as typeof fetch;
  await authFetch("http://x");
  expect(seen?.get("authorization")).toBe("Bearer tok");
  global.fetch = orig;
  clearToken();
});
