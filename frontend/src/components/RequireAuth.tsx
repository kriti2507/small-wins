import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth";
import { loginPath } from "../lib/authPaths";

// Everything in Small Wins is private: signed-out visitors go to /login,
// which brings them back here after Google.
export default function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return null;
  if (!user) return <Navigate to={loginPath(location.pathname, location.search)} replace />;
  return <>{children}</>;
}
