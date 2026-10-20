import { describe, it, expect } from "vitest";
import { countWithValue, emptyRow, fieldsPayload, moveRow, rowsFromTopic } from "./fieldRows";
import type { Entry, Topic } from "../types";

const topic: Topic = {
  slug: "workout",
  name: "Workout",
  color: "green",
  layout: "photo-top",
  fields: [
    { key: "title", label: "Title", type: "text", direction: "none" },
    { key: "duration", label: "Duration", type: "number", direction: "higher" },
  ],
};

describe("rowsFromTopic", () => {
  it("copies the topic's fields, keys included", () => {
    const rows = rowsFromTopic(topic);
    expect(rows.map(({ id: _id, ...rest }) => rest)).toEqual(topic.fields);
  });

  it("gives each row a distinct id", () => {
    const rows = rowsFromTopic(topic);
    expect(new Set(rows.map((r) => r.id)).size).toBe(rows.length);
  });
});

describe("moveRow", () => {
  it("swaps a row with its neighbour", () => {
    expect(moveRow(["a", "b", "c"], 0, 1)).toEqual(["b", "a", "c"]);
    expect(moveRow(["a", "b", "c"], 2, -1)).toEqual(["a", "c", "b"]);
  });

  it("leaves the list alone at the ends", () => {
    const rows = ["a", "b"];
    expect(moveRow(rows, 0, -1)).toBe(rows);
    expect(moveRow(rows, 1, 1)).toBe(rows);
  });
});

describe("countWithValue", () => {
  it("counts entries with a non-empty value for the key", () => {
    const entries: Entry[] = [
      { id: 1, date: "", duration: 30 },
      { id: 2, date: "", duration: 0 },
      { id: 3, date: "", duration: null },
      { id: 4, date: "", duration: "" },
      { id: 5, date: "" },
    ];
    expect(countWithValue(entries, "duration")).toBe(2);
  });
});

describe("fieldsPayload", () => {
  it("sends keys for existing rows, types for new ones, and drops blank new rows", () => {
    const rows = [
      {
        id: 1,
        key: "duration",
        label: " Time ",
        type: "number" as const,
        direction: "lower" as const,
      },
      { id: 2, label: "Sets", type: "number" as const, direction: "higher" as const },
      emptyRow(),
      { id: 4, key: "title", label: "", type: "text" as const, direction: "none" as const },
    ];
    expect(fieldsPayload(rows)).toEqual([
      { key: "duration", label: "Time", direction: "lower" },
      { label: "Sets", type: "number", direction: "higher" },
      { key: "title", label: "", direction: "none" },
    ]);
  });
});
