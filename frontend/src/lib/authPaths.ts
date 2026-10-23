/** Where to send someone who has to sign in, remembering where they were. */
export function loginPath(pathname: string, search = ""): string {
  return `/login?next=${encodeURIComponent(pathname + search)}`;
}

/** A path on this site to go to after sign-in; anything else becomes "/".
 * Mirrors safe_next in backend/auth.py. */
export function safeNext(next: string | null): string {
  if (
    !next ||
    !next.startsWith("/") ||
    next.startsWith("//") ||
    next.includes("\\") ||
    /[\x00-\x1f\x7f]/.test(next)
  ) {
    return "/";
  }
  return next;
}

/** The backend route that starts Google sign-in. A full page navigation,
 * not fetch: Google's sign-in has to happen in the browser window. `source`
 * is where they first came from (lib/source.ts), kept if this is a sign-up. */
export function googleSignInHref(next: string, source: string | null = null): string {
  const href = `/api/auth/google?next=${encodeURIComponent(safeNext(next))}`;
  return source ? `${href}&src=${encodeURIComponent(source)}` : href;
}

/** The message for /login?error=..., set by the backend's Google callback. */
export function loginErrorMessage(code: string | null): string | null {
  switch (code) {
    case "unverified":
      return "This Google account's email isn't verified.";
    case "failed":
      return "Sign-in didn't finish. Try again.";
    default:
      return null;
  }
}
