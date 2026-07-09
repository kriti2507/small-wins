import type { Topic, Entry, Block } from "../types";

async function json<T>(res: Response): Promise<T> {
  const data = await res.json();
  if (!res.ok) {
    throw new Error((data && data.error) || "Request failed");
  }
  return data as T;
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

export function saveEntryBody(
  slug: string,
  id: number,
  body: Block[],
): Promise<Entry> {
  return fetch(`/api/topics/${slug}/entries/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ body }),
  }).then((r) => json<Entry>(r));
}

export function setTopicLayout(slug: string, layout: string): Promise<Topic> {
  return fetch(`/api/topics/${slug}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ layout }),
  }).then((r) => json<Topic>(r));
}

export function uploadImage(file: File): Promise<{ url: string }> {
  const form = new FormData();
  form.append("file", file);
  return fetch("/api/uploads", { method: "POST", body: form }).then((r) =>
    json<{ url: string }>(r),
  );
}
