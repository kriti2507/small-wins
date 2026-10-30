import { describe, it, expect } from "vitest";
import type { QuickAddDraft, Topic } from "../types";
import { chipOrder, draftValues, fieldPayload, savePayload, textDoc, titleOf } from "./quickAdd";

const run: Topic = {
  slug: "run",
  name: "Run",
  color: "green",
  layout: "photo-top",
  fields: [
    { key: "title", label: "Title", type: "text", direction: "none" },
    { key: "distance", label: "Distance (km)", type: "number", direction: "higher" },
    { key: "pace", label: "Pace", type: "pace", direction: "lower" },
  ],
};
const journal: Topic = { ...run, slug: "journal", name: "Journal", fields: [run.fields[0]] };
const sleep: Topic = { ...run, slug: "sleep", name: "Sleep", fields: [] };

const draft: QuickAddDraft = {
  topic: "run",
  clear: true,
  suggestions: ["run"],
  date: "2026-10-28",
  drafts: { run: { title: "easy 5k", distance: 5, pace: 515 }, journal: { title: "easy 5k" }, sleep: {} },
};

describe("draftValues", () => {
  it("turns a topic's draft into form strings, pace as min'sec", () => {
    expect(draftValues(run, draft)).toEqual({
      date: "2026-10-28",
      title: "easy 5k",
      distance: "5",
      pace: "8'35\"",
    });
  });

  it("leaves out fields the draft didn't fill", () => {
    expect(draftValues(sleep, draft)).toEqual({ date: "2026-10-28" });
    expect(draftValues({ ...run, slug: "missing" }, draft)).toEqual({ date: "2026-10-28" });
  });
});

describe("chipOrder", () => {
  it("puts suggested topics first, most likely first, then the rest in order", () => {
    expect(chipOrder([run, journal, sleep], ["sleep", "journal"]).map((t) => t.slug)).toEqual([
      "sleep",
      "journal",
      "run",
    ]);
  });

  it("ignores suggestions that aren't topics", () => {
    expect(chipOrder([run, journal], ["gone"]).map((t) => t.slug)).toEqual(["run", "journal"]);
  });
});

describe("textDoc", () => {
  it("wraps the typed text in a one-paragraph post", () => {
    expect(textDoc("easy 5k")).toEqual({
      type: "doc",
      content: [{ type: "paragraph", content: [{ type: "text", text: "easy 5k" }] }],
    });
  });
});

describe("fieldPayload", () => {
  it("passes values through with pace parsed to seconds", () => {
    expect(fieldPayload(run, { date: "2026-10-28", title: "easy", distance: "5", pace: "8:35" })).toEqual({
      data: { date: "2026-10-28", title: "easy", distance: "5", pace: 515 },
    });
  });

  it("sends empty strings for blank fields", () => {
    expect(fieldPayload(run, {})).toEqual({ data: { date: "", title: "", distance: "", pace: "" } });
  });

  it("reports a pace it can't read", () => {
    expect(fieldPayload(run, { pace: "fast" })).toEqual({ error: "Pace: use min'sec, e.g. 8'35\" or 8:35" });
  });
});

describe("savePayload", () => {
  it("is the field payload plus the typed text as the post", () => {
    expect(savePayload(run, draftValues(run, draft), "easy 5k at 8'35\"")).toEqual({
      data: {
        date: "2026-10-28",
        title: "easy 5k",
        distance: "5",
        pace: 515,
        body: textDoc("easy 5k at 8'35\""),
      },
    });
  });

  it("passes a pace error through", () => {
    expect(savePayload(run, { pace: "fast" }, "x")).toEqual({ error: "Pace: use min'sec, e.g. 8'35\" or 8:35" });
  });
});

describe("titleOf", () => {
  it("is the first text field's value", () => {
    expect(titleOf(run, { title: "easy 5k", distance: "5" })).toBe("easy 5k");
  });

  it("is empty without a text field or value", () => {
    expect(titleOf(sleep, {})).toBe("");
    expect(titleOf(run, {})).toBe("");
  });
});
