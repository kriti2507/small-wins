/** Where to send someone who has to sign in, remembering where they were. */
export function loginPath(pathname: string, search = ""): string {
  return `/login?next=${encodeURIComponent(pathname + search)}`;
}

/** A path on this site to go to after sign-in; anything else becomes "/".
 * Mirrors safe_next in backend/auth.py. */
export function safeNext(next: string | null): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.includes("\\")) {
    return "/";
  }
  return next;
}

/** The backend route that starts Google sign-in. A full page navigation,
 * not fetch: Google's sign-in has to happen in the browser window. */
export function googleSignInHref(next: string): string {
  return `/api/auth/google?next=${encodeURIComponent(safeNext(next))}`;
}

/** The message for /login?error=..., set by the backend's Google callback. */
export function loginErrorMessage(code: string | null): string | null {
  switch (code) {
    case "not_invited":
      return "This Google account isn't invited to Small Wins.";
    case "failed":
      return "Sign-in didn't finish. Try again.";
    default:
      return null;
  }
}
