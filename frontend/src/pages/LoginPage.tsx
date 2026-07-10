import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

// Hidden admin login page — not linked from anywhere; the admin types /login.
export default function LoginPage() {
  const { isAdmin, login, logout } = useAuth();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    document.title = "Admin — Small Wins";
  }, []);

  function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    login(password)
      .then(() => navigate("/"))
      .catch((err) => setError(err.message || "Login failed."))
      .finally(() => setBusy(false));
  }

  if (isAdmin) {
    return (
      <>
        <Link className="back" to="/">
          ← Back
        </Link>
        <h1>Admin</h1>
        <p>You're logged in.</p>
        <button className="primary" onClick={() => logout()}>
          Log out
        </button>
      </>
    );
  }

  return (
    <>
      <Link className="back" to="/">
        ← Back
      </Link>
      <h1>Admin login</h1>
      <form className="login-form" onSubmit={submit}>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          autoFocus
        />
        <button className="primary" type="submit" disabled={busy || !password}>
          Log in
        </button>
        {error && <p className="login-error">{error}</p>}
      </form>
    </>
  );
}
