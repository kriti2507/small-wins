import { describe, expect, test } from "vitest";
import { scoreEntries } from "./scoring";
import type { Topic, Entry } from "../types";

const topic = (fields: Topic["fields"]): Topic => ({
  slug: "t",
  name: "T",
  color: "green",
  layout: "thumbnail",
  fields,
});

describe("scoreEntries", () => {
  test('normalizes a "higher is better" field to 0..1', () => {
    const t = topic([{ key: "d", label: "D", type: "number", direction: "higher" }]);
    const entries: Entry[] = [
      { id: 1, date: "2026-01-01", d: 0 },
      { id: 2, date: "2026-01-02", d: 5 },
      { id: 3, date: "2026-01-03", d: 10 },
    ];
    expect(scoreEntries(t, entries)).toEqual([0, 0.5, 1]);
  });

  test('reverses a "lower is better" field', () => {
    const t = topic([{ key: "p", label: "P", type: "pace", direction: "lower" }]);
    const entries: Entry[] = [
      { id: 1, date: "2026-01-01", p: 0 },
      { id: 2, date: "2026-01-02", p: 10 },
    ];
    expect(scoreEntries(t, entries)).toEqual([1, 0]);
  });

  test('ignores "none" direction fields', () => {
    const t = topic([
      { key: "n", label: "N", type: "number", direction: "none" },
      { key: "d", label: "D", type: "number", direction: "higher" },
    ]);
    const entries: Entry[] = [
      { id: 1, date: "2026-01-01", n: 999, d: 0 },
      { id: 2, date: "2026-01-02", n: 1, d: 10 },
    ];
    expect(scoreEntries(t, entries)).toEqual([0, 1]);
  });

  test("averages multiple scored fields per entry", () => {
    const t = topic([
      { key: "a", label: "A", type: "number", direction: "higher" },
      { key: "b", label: "B", type: "number", direction: "higher" },
    ]);
    const entries: Entry[] = [
      { id: 1, date: "2026-01-01", a: 0, b: 10 }, // (0 + 1) / 2
      { id: 2, date: "2026-01-02", a: 10, b: 0 }, // (1 + 0) / 2
    ];
    expect(scoreEntries(t, entries)).toEqual([0.5, 0.5]);
  });

  test("returns 0.5 when all values of a field are equal (max === min)", () => {
    const t = topic([{ key: "d", label: "D", type: "number", direction: "higher" }]);
    const entries: Entry[] = [
      { id: 1, date: "2026-01-01", d: 5 },
      { id: 2, date: "2026-01-02", d: 5 },
    ];
    expect(scoreEntries(t, entries)).toEqual([0.5, 0.5]);
  });

  test("returns 0.5 for an entry with no scorable values", () => {
    const t = topic([{ key: "d", label: "D", type: "number", direction: "higher" }]);
    const entries: Entry[] = [
      { id: 1, date: "2026-01-01", d: 0 },
      { id: 2, date: "2026-01-02", d: null },
      { id: 3, date: "2026-01-03", d: 10 },
    ];
    expect(scoreEntries(t, entries)).toEqual([0, 0.5, 1]);
  });

  test("returns 0.5 for every entry when the topic has no scored fields", () => {
    const t = topic([{ key: "title", label: "Title", type: "text", direction: "none" }]);
    const entries: Entry[] = [
      { id: 1, date: "2026-01-01", title: "a" },
      { id: 2, date: "2026-01-02", title: "b" },
    ];
    expect(scoreEntries(t, entries)).toEqual([0.5, 0.5]);
  });

  test("returns [] for no entries", () => {
    const t = topic([{ key: "d", label: "D", type: "number", direction: "higher" }]);
    expect(scoreEntries(t, [])).toEqual([]);
  });
});
