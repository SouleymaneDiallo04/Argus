import { login, me } from "./authApi";

test("login poste les identifiants", async () => {
  let url = ""; let init: RequestInit | undefined;
  const f = (async (u: string, i?: RequestInit) => {
    url = u; init = i;
    return { ok: true, status: 200, json: async () => ({ access_token: "t", role: "admin" }) } as Response;
  }) as typeof fetch;
  const r = await login("a", "b", f);
  expect(url).toContain("/auth/login");
  expect(init?.method).toBe("POST");
  expect(JSON.parse(init?.body as string)).toEqual({ username: "a", password: "b" });
  expect(r.role).toBe("admin");
});

test("me lit /auth/me", async () => {
  const f = (async () => ({ ok: true, status: 200, json: async () => ({ username: "a", role: "hse" }) }) as Response) as typeof fetch;
  expect((await me(f)).role).toBe("hse");
});
