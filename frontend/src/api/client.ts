import type { Topic, Entry, PostDoc, Grant } from "../types";
import { prepareImage } from "../lib/image";
import { loginPath } from "../lib/authPaths";

/** A readable message for a response that carried no JSON error of its own. */
export function httpErrorMessage(status: number, statusText = ""): string {
  if (status === 413) return "That file is too large to upload.";
  if (status === 401) return "Your session has ended. Sign in again.";
  if (status === 0) return "Could not reach the server.";
  return `Request failed (${status}${statusText ? ` ${statusText}` : ""}).`;
}

/** Parse a JSON response, tolerating replies that aren't JSON at all.
 *
 * Errors raised before our own code runs — Vercel's plain-text 413, a proxy's
 * HTML 502 — used to reach the user as a JSON parser message. Anything
 * unparseable is reported by status instead.
 */
export async function readJson<T>(res: {
  ok: boolean;
  status: number;
  statusText?: string;
  text: () => Promise<string>;
}): Promise<T> {
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }
  if (!res.ok) {
    const fromApi = (data as { error?: string } | null)?.error;
    throw new Error(fromApi || httpErrorMessage(res.status, res.statusText));
  }
  return data as T;
}

/** A signed-out reply mid-session (cookie expired, signed out in another
 * tab) sends the whole page to sign-in, then back here afterwards. */
function redirectToLogin() {
  if (window.location.pathname === "/login") return;
  window.location.assign(loginPath(window.location.pathname, window.location.search));
}

function json<T>(res: Response): Promise<T> {
  if (res.status === 401) redirectToLogin();
  return readJson<T>(res);
}

export function getTopics(): Promise<Topic[]> {
  return fetch("/api/topics").then((r) => json<Topic[]>(r));
}

export function addTopic(payload: {
  name: string;
  color: string | null;
  layout: string;
  fields: { label: string; type: string; direction: string }[];
}): Promise<Topic> {
  return fetch("/api/topics", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then((r) => json<Topic>(r));
}

export function getEntries(slug: string): Promise<Entry[]> {
  return fetch(`/api/topics/${slug}/entries`).then((r) => json<Entry[]>(r));
}

export function addEntry(
  slug: string,
  payload: Record<string, string | number>,
): Promise<Entry> {
  return fetch(`/api/topics/${slug}/entries`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then((r) => json<Entry>(r));
}

export function getEntry(slug: string, id: number): Promise<Entry> {
  return fetch(`/api/topics/${slug}/entries/${id}`).then((r) => json<Entry>(r));
}

export interface EntryUpdate {
  date?: string;
  image?: string | null;
  body?: PostDoc;
  [fieldKey: string]: string | number | null | PostDoc | undefined;
}

export function updateEntry(
  slug: string,
  id: number,
  payload: EntryUpdate,
): Promise<Entry> {
  return fetch(`/api/topics/${slug}/entries/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then((r) => json<Entry>(r));
}

export function deleteEntry(slug: string, id: number): Promise<{ ok: boolean }> {
  return fetch(`/api/topics/${slug}/entries/${id}`, {
    method: "DELETE",
  }).then((r) => json<{ ok: boolean }>(r));
}

export function setTopicLayout(slug: string, layout: string): Promise<Topic> {
  return fetch(`/api/topics/${slug}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ layout }),
  }).then((r) => json<Topic>(r));
}

export function listGrants(): Promise<Grant[]> {
  return fetch("/api/mcp/grants").then((r) => json<Grant[]>(r));
}

export function revokeGrant(id: number): Promise<void> {
  return fetch(`/api/mcp/grants/${id}`, { method: "DELETE" })
    .then((r) => json<null>(r))
    .then(() => undefined);
}

// Upload keys are random and never reused, so the bytes behind one never
// change and browsers may keep them for a year.
const IMMUTABLE = "max-age=31536000";

function putBlob(url: string, blob: Blob): Promise<Response> {
  return fetch(url, {
    method: "PUT",
    headers: {
      "Content-Type": blob.type || "application/octet-stream",
      "cache-control": IMMUTABLE,
    },
    body: blob,
  });
}

/** Upload an image (and its thumbnail) and return the path it is served at.
 *
 * The bytes go from the browser straight to Supabase Storage. Routing them
 * through our own API instead would 413 at Vercel's edge, which caps a
 * function's request body at 4.5 MB — below an ordinary phone photo.
 */
export async function uploadImage(file: File): Promise<{ url: string }> {
  const { blob, ext, thumb } = await prepareImage(file);

  const { upload_url, thumb_upload_url, url } = await fetch("/api/uploads/sign", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ext, thumb: thumb !== null }),
  }).then((r) => json<{ upload_url: string; thumb_upload_url?: string; url: string }>(r));

  // A missing thumbnail only costs speed (the server falls back to the full
  // image), so its failure never fails the upload.
  const thumbDone =
    thumb && thumb_upload_url
      ? putBlob(thumb_upload_url, thumb).catch(() => undefined)
      : Promise.resolve(undefined);

  const res = await putBlob(upload_url, blob);
  await thumbDone;
  if (!res.ok) {
    throw new Error(httpErrorMessage(res.status, res.statusText));
  }

  return { url };
}

export interface User {
  id: number;
  email: string;
  name: string | null;
  avatar_url: string | null;
}

/** The signed-in user, or null when signed out. Never redirects: the
 * caller (AuthProvider) decides what signed-out means. */
export async function getMe(): Promise<User | null> {
  const res = await fetch("/api/auth/me");
  if (res.status === 401) return null;
  return (await readJson<{ user: User }>(res)).user;
}

export function logout(): Promise<{ ok: boolean }> {
  return fetch("/api/auth/logout", { method: "POST" }).then((r) =>
    readJson<{ ok: boolean }>(r),
  );
}
