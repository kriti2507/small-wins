import { describe, expect, test } from "vitest";
import {
  PALETTES,
  rampFor,
  scoreToColor,
  buttonColorFor,
  paletteSwatches,
} from "./palette";
import type { Topic } from "../types";

const topic = (color: string): Topic => ({ slug: "t", name: "T", color, fields: [] });

describe("rampFor", () => {
  test("uses the topic's saved color when valid", () => {
    expect(rampFor(topic("blue"), 0)).toEqual(PALETTES.blue);
  });

  test("falls back to the position palette when color is invalid", () => {
    // "green" is the first palette; index 0 wraps to it.
    expect(rampFor(topic("nonsense"), 0)).toEqual(PALETTES.green);
  });

  test("wraps the position index past the number of palettes", () => {
    const n = Object.keys(PALETTES).length;
    expect(rampFor(topic("nonsense"), n)).toEqual(PALETTES.green);
  });
});

describe("scoreToColor", () => {
  const ramp = PALETTES.green; // 5 shades

  test("maps score 0 to the lightest shade", () => {
    expect(scoreToColor(0, ramp)).toBe(ramp[0]);
  });

  test("clamps score 1 to the darkest shade", () => {
    expect(scoreToColor(1, ramp)).toBe(ramp[ramp.length - 1]);
  });

  test("buckets a mid score", () => {
    expect(scoreToColor(0.5, ramp)).toBe(ramp[2]);
  });
});

describe("buttonColorFor", () => {
  test("returns the darkest shade of the topic's ramp", () => {
    expect(buttonColorFor(topic("blue"), 0)).toBe(PALETTES.blue[PALETTES.blue.length - 1]);
  });
});

describe("paletteSwatches", () => {
  test("returns one swatch per palette with id, capitalized name, and darkest color", () => {
    const swatches = paletteSwatches();
    expect(swatches.length).toBe(Object.keys(PALETTES).length);
    expect(swatches[0]).toEqual({
      id: "green",
      name: "Green",
      color: PALETTES.green[PALETTES.green.length - 1],
    });
  });
});
