import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import * as api from "./api/client";

interface Auth {
  isAdmin: boolean;
  // True until the initial /api/auth/me check resolves; gates render
  // disabled-without-tooltip during this window to avoid a flicker.
  loading: boolean;
  login: (password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<Auth>({
  isAdmin: false,
  loading: true,
  login: async () => {},
  logout: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAdmin, setIsAdmin] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getMe()
      .then((r) => setIsAdmin(r.is_admin))
      .catch(() => setIsAdmin(false))
      .finally(() => setLoading(false));
  }, []);

  async function login(password: string) {
    const r = await api.login(password);
    setIsAdmin(r.is_admin);
  }

  async function logout() {
    // Always lock the UI, even if the API call fails; the cookie (if it
    // survived) is reconciled by the next /api/auth/me check.
    await api.logout().catch(() => {});
    setIsAdmin(false);
  }

  return (
    <AuthContext.Provider value={{ isAdmin, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
