import { describe, it, expect } from "vitest";
import {
  STARTER_TOPICS, MAX_STARTERS, PREVIEW_DAYS, toggleStarter, createStarters, previewShades,
} from "./starterTopics";
import { PALETTES } from "./palette";

describe("STARTER_TOPICS", () => {
  it("offers 9 templates with unique names and valid, distinct colors", () => {
    expect(STARTER_TOPICS).toHaveLength(9);
    const names = STARTER_TOPICS.map((t) => t.name);
    expect(new Set(names).size).toBe(9);
    const colors = STARTER_TOPICS.map((t) => t.color);
    expect(new Set(colors).size).toBe(9);
    colors.forEach((c) => expect(PALETTES[c]).toBeDefined());
  });

  it("gives every template a Title text field first", () => {
    STARTER_TOPICS.forEach((t) =>
      expect(t.fields[0]).toEqual({ label: "Title", type: "text", direction: "none" }),
    );
  });

  it("gives every template an icon and a short hint for its note", () => {
    STARTER_TOPICS.forEach((t) => {
      expect(t.icon).toBeTruthy();
      expect(t.hint).toBeTruthy();
    });
  });
});

describe("toggleStarter", () => {
  it("adds and removes a name", () => {
    expect(toggleStarter([], "Sleep")).toEqual(["Sleep"]);
    expect(toggleStarter(["Sleep", "Walk"], "Sleep")).toEqual(["Walk"]);
  });

  it("ignores a new pick once MAX_STARTERS are chosen", () => {
    const full = ["Workout", "Journal", "Sleep"];
    expect(MAX_STARTERS).toBe(3);
    expect(toggleStarter(full, "Walk")).toEqual(full);
  });
});

describe("createStarters", () => {
  it("creates the chosen templates one at a time, in catalog order", async () => {
    const calls: string[] = [];
    await createStarters(["Walk", "Workout"], async (t) => {
      calls.push(t.name);
    });
    expect(calls).toEqual(["Workout", "Walk"]);
  });

  it("sends only the topic payload, not the picker's icon and hint", async () => {
    const sent: object[] = [];
    await createStarters(["Journal"], async (t) => {
      sent.push(t);
    });
    expect(sent).toEqual([
      {
        name: "Journal",
        color: "purple",
        layout: "photo-top",
        fields: [{ label: "Title", type: "text", direction: "none" }],
      },
    ]);
  });

  it("stops at the first failure", async () => {
    const calls: string[] = [];
    const add = async (t: { name: string }) => {
      calls.push(t.name);
      throw new Error("nope");
    };
    await expect(createStarters(["Workout", "Journal"], add)).rejects.toThrow("nope");
    expect(calls).toEqual(["Workout"]);
  });
});

describe("previewShades", () => {
  it("gives PREVIEW_DAYS shades, each empty (-1) or a palette index 0-4", () => {
    const shades = previewShades("Workout");
    expect(shades).toHaveLength(PREVIEW_DAYS);
    shades.forEach((s) => expect([-1, 0, 1, 2, 3, 4]).toContain(s));
  });

  it("is stable for a name and differs between names", () => {
    expect(previewShades("Sleep")).toEqual(previewShades("Sleep"));
    expect(previewShades("Sleep")).not.toEqual(previewShades("Walk"));
  });

  it("mixes empty days with filled ones, like a real month", () => {
    STARTER_TOPICS.forEach((t) => {
      const shades = previewShades(t.name);
      expect(shades.some((s) => s === -1)).toBe(true);
      expect(shades.some((s) => s >= 2)).toBe(true);
    });
  });
});
