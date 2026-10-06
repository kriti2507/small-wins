import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import * as api from "./api/client";
import type { User } from "./api/client";

interface Auth {
  user: User | null;
  // True until the initial /api/auth/me check resolves; RequireAuth renders
  // nothing meanwhile, so a signed-in user never flashes the login page.
  loading: boolean;
  logout: () => Promise<void>;
}

const AuthContext = createContext<Auth>({
  user: null,
  loading: true,
  logout: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  async function logout() {
    // Always sign the UI out, even if the API call fails; a surviving cookie
    // is reconciled by the next /api/auth/me check.
    await api.logout().catch(() => {});
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
