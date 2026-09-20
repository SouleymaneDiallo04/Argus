"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { login as apiLogin, me as apiMe, type AuthUser } from "@/lib/authApi";
import { setToken, clearToken } from "@/lib/http";

type AuthCtx = {
  user: AuthUser | null; ready: boolean;
  login: (u: string, p: string) => Promise<void>; logout: () => void;
};

const Ctx = createContext<AuthCtx>({
  user: null, ready: true, login: async () => {}, logout: () => {},
});

export function useAuth(): AuthCtx {
  return useContext(Ctx);
}

export function AuthProvider({
  children, loadMe = apiMe, doLogin = apiLogin,
}: {
  children: React.ReactNode; loadMe?: typeof apiMe; doLogin?: typeof apiLogin;
}) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);

  const refresh = useCallback(async () => {
    try { setUser(await loadMe()); } catch { setUser(null); } finally { setReady(true); }
  }, [loadMe]);

  useEffect(() => { refresh(); }, [refresh]);

  const login = useCallback(async (u: string, p: string) => {
    const { access_token } = await doLogin(u, p);
    setToken(access_token);
    await refresh();
  }, [doLogin, refresh]);

  const logout = useCallback(() => { clearToken(); setUser(null); }, []);

  return <Ctx.Provider value={{ user, ready, login, logout }}>{children}</Ctx.Provider>;
}
