import { describe, expect, test } from "vitest";
import { tileModel } from "./tile";
import type { Topic, Entry } from "../types";

const topic: Topic = {
  slug: "hikes",
  name: "Hikes",
  color: "blue",
  layout: "photo-top",
  fields: [
    { key: "title", label: "Title", type: "text", direction: "none" },
    { key: "height", label: "Height (m)", type: "number", direction: "higher" },
  ],
};

describe("tileModel", () => {
  test("heading comes from the first text field", () => {
    const e: Entry = { id: 1, date: "2026-07-04", title: "Tsukubasan", height: 877 };
    expect(tileModel(topic, e).heading).toBe("Tsukubasan");
  });

  test("meta lists non-title fields then the date", () => {
    const e: Entry = { id: 1, date: "2026-07-04", title: "Tsukubasan", height: 877 };
    expect(tileModel(topic, e).meta).toBe("Height (m): 877 · Date: 2026-07-04");
  });

  test("initial is the uppercased first char of the heading", () => {
    const e: Entry = { id: 1, date: "2026-07-04", title: "tsukubasan", height: 877 };
    expect(tileModel(topic, e).initial).toBe("T");
  });

  test("falls back to the date as heading when no text field has a value", () => {
    const noText: Topic = { ...topic, fields: [topic.fields[1]] };
    const e: Entry = { id: 2, date: "2026-07-05", height: 500 };
    const m = tileModel(noText, e);
    expect(m.heading).toBe("2026-07-05");
    expect(m.initial).toBe("2");
  });

  test("image passes through, null when absent", () => {
    const withImg: Entry = { id: 1, date: "2026-07-04", title: "X", height: 1, image: "/api/uploads/a.jpg" };
    const noImg: Entry = { id: 1, date: "2026-07-04", title: "X", height: 1 };
    expect(tileModel(topic, withImg).image).toBe("/api/uploads/a.jpg");
    expect(tileModel(topic, noImg).image).toBeNull();
  });
});
