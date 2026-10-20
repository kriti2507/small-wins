import type { Direction, Entry, FieldType, Topic } from "../types";

// One row of TopicForm's field list. `key` is set for fields the topic
// already has (their type is locked) and absent for rows added in the form.
export interface FieldRow {
  key?: string;
  label: string;
  type: FieldType;
  direction: Direction;
}

// What the API takes for one field: existing fields are named by key (the
// server keeps their type), new ones carry a type.
export type FieldPayload =
  | { key: string; label: string; direction: Direction }
  | { label: string; type: FieldType; direction: Direction };

export const emptyRow = (): FieldRow => ({ label: "", type: "number", direction: "higher" });

export function rowsFromTopic(topic: Topic): FieldRow[] {
  return topic.fields.map(({ key, label, type, direction }) => ({ key, label, type, direction }));
}

// Swap row i with its neighbour; the same list if that would leave the ends.
export function moveRow<T>(rows: T[], i: number, delta: -1 | 1): T[] {
  const j = i + delta;
  if (j < 0 || j >= rows.length) return rows;
  const next = [...rows];
  [next[i], next[j]] = [next[j], next[i]];
  return next;
}

// How many entries would lose a value if the field `key` were removed.
export function countWithValue(entries: Entry[], key: string): number {
  return entries.filter((e) => e[key] !== undefined && e[key] !== null && e[key] !== "").length;
}

// Blank new rows are dropped; a blank existing row is kept so the server can
// reject it rather than the field silently disappearing.
export function fieldsPayload(rows: FieldRow[]): FieldPayload[] {
  return rows
    .map((r) => ({ ...r, label: r.label.trim() }))
    .filter((r) => r.key !== undefined || r.label)
    .map((r) =>
      r.key !== undefined
        ? { key: r.key, label: r.label, direction: r.direction }
        : { label: r.label, type: r.type, direction: r.direction },
    );
}
