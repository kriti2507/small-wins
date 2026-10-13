import { useEffect } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth";
import { googleSignInHref, loginErrorMessage, safeNext } from "../lib/authPaths";

// The front door: everything else needs a signed-in user.
export default function LoginPage() {
  const { user, loading } = useAuth();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const error = loginErrorMessage(params.get("error"));

  useEffect(() => {
    document.title = "Sign in — Small Wins";
  }, []);

  if (loading) return null;
  if (user) return <Navigate to={next} replace />;

  return (
    <div className="login">
      <h1>Small Wins</h1>
      <p className="intro">A little diary for the good things.</p>
      <a className="btn primary" href={googleSignInHref(next)}>
        Sign in with Google
      </a>
      {error && <p className="login-error">{error}</p>}
    </div>
  );
}
