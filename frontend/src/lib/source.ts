// Where someone first came from, for analytics: remembered on their first
// visit and sent along with Google sign-in, which stores it on their account
// when it's created (backend/auth.py).

const KEY = "small-wins-source";

/** utm_source, else ?ref=, else the referring site, else "direct". */
export function visitSource(search: string, referrer: string, host: string): string {
  const params = new URLSearchParams(search);
  const tagged = (params.get("utm_source") || params.get("ref") || "").trim();
  if (tagged) return tagged;
  try {
    const from = new URL(referrer).hostname.replace(/^www\./, "");
    if (from && from !== host) return from;
  } catch {
    // no referrer, or not a URL
  }
  return "direct";
}

/** localStorage, or null where the browser blocks it (even touching it can
 * throw). Analytics must never break the app. */
export function browserStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

/** Save this visit's source unless an earlier visit already did. */
export function rememberSource(storage: Storage | null, search: string, referrer: string, host: string) {
  try {
    if (storage && storage.getItem(KEY) === null) {
      storage.setItem(KEY, visitSource(search, referrer, host));
    }
  } catch {
    // storage full or blocked
  }
}

export function savedSource(storage: Storage | null): string | null {
  try {
    return storage ? storage.getItem(KEY) : null;
  } catch {
    return null;
  }
}
