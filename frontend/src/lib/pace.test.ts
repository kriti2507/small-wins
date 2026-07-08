import { describe, expect, test } from "vitest";
import { parsePace, formatPace, formatValue } from "./pace";
import type { Field } from "../types";

describe("parsePace", () => {
  test('parses "8\'35\"" as minutes and seconds', () => {
    expect(parsePace("8'35\"")).toBe(8 * 60 + 35);
  });

  test('parses colon form "8:35"', () => {
    expect(parsePace("8:35")).toBe(8 * 60 + 35);
  });

  test('parses a plain decimal number of minutes "8.5"', () => {
    expect(parsePace("8.5")).toBe(Math.round(8.5 * 60));
  });

  test("tolerates surrounding whitespace", () => {
    expect(parsePace("  8'35\"  ")).toBe(8 * 60 + 35);
  });

  test("returns NaN for null", () => {
    expect(parsePace(null)).toBeNaN();
  });

  test("returns NaN for garbage", () => {
    expect(parsePace("not a pace")).toBeNaN();
  });
});

describe("formatPace", () => {
  test('formats seconds as min\'sec" with zero-padded seconds', () => {
    expect(formatPace(8 * 60 + 35)).toBe("8'35\"");
  });

  test("pads single-digit seconds", () => {
    expect(formatPace(8 * 60 + 5)).toBe("8'05\"");
  });

  test("round-trips with parsePace", () => {
    expect(formatPace(parsePace("8'35\""))).toBe("8'35\"");
  });

  test('returns "—" for null or NaN', () => {
    expect(formatPace(null)).toBe("—");
    expect(formatPace(NaN)).toBe("—");
  });
});

describe("formatValue", () => {
  const paceField: Field = { key: "pace", label: "Pace", type: "pace", direction: "lower" };
  const numberField: Field = { key: "d", label: "Distance", type: "number", direction: "higher" };

  test("formats a pace field via formatPace", () => {
    expect(formatValue(paceField, 8 * 60 + 35)).toBe("8'35\"");
  });

  test("returns non-pace values unchanged", () => {
    expect(formatValue(numberField, 3.06)).toBe(3.06);
  });

  test('returns "—" for null or empty string', () => {
    expect(formatValue(numberField, null)).toBe("—");
    expect(formatValue(numberField, "")).toBe("—");
  });
});
