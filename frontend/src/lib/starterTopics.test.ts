import { describe, it, expect } from "vitest";
import { STARTER_TOPICS, MAX_STARTERS, toggleStarter, createStarters } from "./starterTopics";
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
