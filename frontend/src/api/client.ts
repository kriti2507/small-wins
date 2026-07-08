import type { Topic, Entry } from "../types";

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
