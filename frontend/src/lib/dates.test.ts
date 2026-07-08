import { describe, expect, test } from "vitest";
import { enumerateDays, weekdayIndex, addDays, isoDate } from "./dates";

describe("enumerateDays", () => {
  test("is inclusive of both start and end", () => {
    expect(enumerateDays("2026-01-01", "2026-01-03")).toEqual([
      "2026-01-01",
      "2026-01-02",
      "2026-01-03",
    ]);
  });

  test("returns a single day when start equals end", () => {
    expect(enumerateDays("2026-01-01", "2026-01-01")).toEqual(["2026-01-01"]);
  });

  test("crosses month boundaries", () => {
    expect(enumerateDays("2026-01-30", "2026-02-01")).toEqual([
      "2026-01-30",
      "2026-01-31",
      "2026-02-01",
    ]);
  });

  test("returns [] for a reversed range", () => {
    expect(enumerateDays("2026-01-03", "2026-01-01")).toEqual([]);
  });

  test("returns [] when start or end is missing", () => {
    expect(enumerateDays("", "2026-01-01")).toEqual([]);
    expect(enumerateDays("2026-01-01", "")).toEqual([]);
  });
});

describe("weekdayIndex", () => {
  test("Monday is 0", () => {
    // 2026-01-05 is a Monday.
    expect(weekdayIndex("2026-01-05")).toBe(0);
  });

  test("Sunday is 6", () => {
    // 2026-01-04 is a Sunday.
    expect(weekdayIndex("2026-01-04")).toBe(6);
  });
});

describe("addDays", () => {
  test("adds days forward", () => {
    expect(addDays("2026-01-01", 5)).toBe("2026-01-06");
  });

  test("subtracts days with a negative delta", () => {
    expect(addDays("2026-01-01", -1)).toBe("2025-12-31");
  });
});

describe("isoDate", () => {
  test("formats a Date as local YYYY-MM-DD with zero padding", () => {
    expect(isoDate(new Date(2026, 0, 5))).toBe("2026-01-05");
  });
});
