import type { Topic, Entry, PostDoc } from "../types";
import { prepareImage } from "../lib/image";

/** A readable message for a response that carried no JSON error of its own. */
export function httpErrorMessage(status: number, statusText = ""): string {
  if (status === 413) return "That file is too large to upload.";
  if (status === 401 || status === 403) return "Sign in as admin to make changes.";
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

const json = readJson;

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

/** Upload an image and return the URL it will be served from.
 *
 * The bytes go from the browser straight to Supabase Storage. Routing them
 * through our own API instead would 413 at Vercel's edge, which caps a
 * function's request body at 4.5 MB — below an ordinary phone photo.
 */
export async function uploadImage(file: File): Promise<{ url: string }> {
  const { blob, ext } = await prepareImage(file);

  const { upload_url, url } = await fetch("/api/uploads/sign", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ext }),
  }).then((r) => json<{ upload_url: string; url: string }>(r));

  const res = await fetch(upload_url, {
    method: "PUT",
    headers: { "Content-Type": blob.type || "application/octet-stream" },
    body: blob,
  });
  if (!res.ok) {
    throw new Error(httpErrorMessage(res.status, res.statusText));
  }

  return { url };
}

export interface AuthState {
  is_admin: boolean;
}

export function getMe(): Promise<AuthState> {
  return fetch("/api/auth/me").then((r) => json<AuthState>(r));
}

export function login(password: string): Promise<AuthState> {
  return fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  }).then((r) => json<AuthState>(r));
}

export function logout(): Promise<AuthState> {
  return fetch("/api/auth/logout", { method: "POST" }).then((r) =>
    json<AuthState>(r),
  );
}
