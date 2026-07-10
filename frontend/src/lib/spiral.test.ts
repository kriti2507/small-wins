import { describe, expect, test } from "vitest";
import { spiralCoords, spiralSpan, cellSizeFor, revealDelayMs } from "./spiral";

describe("spiralCoords", () => {
  test("n<=0 returns empty", () => {
    expect(spiralCoords(0)).toEqual([]);
    expect(spiralCoords(-3)).toEqual([]);
  });
  test("n=1 is just the center", () => {
    expect(spiralCoords(1)).toEqual([[0, 0]]);
  });
  test("starts at the center and winds outward", () => {
    expect(spiralCoords(5)).toEqual([
      [0, 0],
      [1, 0],
      [1, -1],
      [0, -1],
      [-1, -1],
    ]);
  });
  test("n=9 fills a 3x3 block with no duplicates", () => {
    const pts = spiralCoords(9);
    expect(pts.length).toBe(9);
    const keys = new Set(pts.map(([x, y]) => `${x},${y}`));
    expect(keys.size).toBe(9);
    for (const [x, y] of pts) {
      expect(Math.abs(x)).toBeLessThanOrEqual(1);
      expect(Math.abs(y)).toBeLessThanOrEqual(1);
    }
  });
});

describe("spiralSpan", () => {
  test("grows with the ring count", () => {
    expect(spiralSpan(0)).toBe(0);
    expect(spiralSpan(1)).toBe(1);
    expect(spiralSpan(2)).toBe(2);
    expect(spiralSpan(9)).toBe(3);
  });
});

describe("cellSizeFor", () => {
  test("clamps up to max for small spans", () => {
    expect(cellSizeFor(3, 220, 3, 4, 16)).toBe(16);
  });
  test("scales down to fit wider spirals", () => {
    // (220 - 19*3) / 20 = 163 / 20 = 8.15 -> 8
    expect(cellSizeFor(20, 220, 3, 4, 16)).toBe(8);
  });
  test("never drops below min", () => {
    expect(cellSizeFor(60, 100, 2, 4, 16)).toBe(4);
  });
  test("span<=0 returns min", () => {
    expect(cellSizeFor(0, 220, 3, 4, 16)).toBe(4);
  });
});

describe("revealDelayMs", () => {
  test("slow for few entries (clamped to max)", () => {
    expect(revealDelayMs(5, 2500, 8, 110)).toBe(110);
  });
  test("keeps total draw ~constant for many entries", () => {
    // 2500 / 150 = 16.67 -> 17
    expect(revealDelayMs(150, 2500, 8, 110)).toBe(17);
  });
  test("never below min", () => {
    expect(revealDelayMs(1000, 2500, 8, 110)).toBe(8);
  });
});
