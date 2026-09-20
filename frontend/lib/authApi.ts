import { API, authFetch } from "./http";

export type AuthUser = { username: string; role: string };

export async function login(
  username: string, password: string, fetchFn: typeof fetch = fetch,
): Promise<{ access_token: string; role: string }> {
  const res = await fetchFn(`${API}/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error(`login -> ${res.status}`);
  return (await res.json()) as { access_token: string; role: string };
}

export async function me(fetchFn: typeof fetch = authFetch): Promise<AuthUser> {
  const res = await fetchFn(`${API}/auth/me`);
  if (!res.ok) throw new Error(`me -> ${res.status}`);
  return (await res.json()) as AuthUser;
}
