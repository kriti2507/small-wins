import type { PostDoc, QuickAddDraft, Topic } from "../types";
import { formatPace, parsePace } from "./pace";

// Pure helpers for the Home page's quick-add bar (components/QuickAdd.tsx).

// Matches quick_add.MAX_TEXT_CHARS on the server.
export const MAX_TEXT = 500;

/** Form values (strings, as EntryFields edits them) for one topic's draft. */
export function draftValues(topic: Topic, draft: QuickAddDraft): Record<string, string> {
  const raw = draft.drafts[topic.slug] ?? {};
  const out: Record<string, string> = { date: draft.date };
  for (const f of topic.fields) {
    const v = raw[f.key];
    if (v == null || v === "") continue;
    out[f.key] = f.type === "pace" ? formatPace(Number(v)) : String(v);
  }
  return out;
}

/** Topics in chip order: the suggested ones first (most likely first), then
 *  the rest as listed. */
export function chipOrder(topics: Topic[], suggestions: string[]): Topic[] {
  const first = suggestions
    .map((s) => topics.find((t) => t.slug === s))
    .filter((t): t is Topic => t !== undefined);
  return [...first, ...topics.filter((t) => !first.includes(t))];
}

/** A one-paragraph post holding what the user typed. */
export function textDoc(text: string): PostDoc {
  return { type: "doc", content: [{ type: "paragraph", content: [{ type: "text", text }] }] };
}

/** The add-entry payload for form values, pace fields parsed to seconds; or
 *  a message for the first pace that can't be read. */
export function fieldPayload(
  topic: Topic,
  values: Record<string, string>,
): { data: Record<string, string | number> } | { error: string } {
  const data: Record<string, string | number> = { date: values.date || "" };
  for (const f of topic.fields) {
    const raw = values[f.key] ?? "";
    if (f.type === "pace" && raw) {
      const sec = parsePace(raw);
      if (isNaN(sec)) return { error: `${f.label}: use min'sec, e.g. 8'35" or 8:35` };
      data[f.key] = sec;
    } else {
      data[f.key] = raw;
    }
  }
  return { data };
}
