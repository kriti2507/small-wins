import { describe, it, expect } from "vitest";
import { homeTip, topicTip, placeBubble } from "./tips";

describe("homeTip", () => {
  it("shows nothing until topics have loaded", () => {
    expect(homeTip([], 0, 0)).toBeNull();
  });

  it("starts with the starter-aspects tip", () => {
    expect(homeTip([], 2, 0)).toBe("starter");
    expect(homeTip([], 2, 5)).toBe("starter");
  });

  it("offers connecting once something is logged", () => {
    expect(homeTip(["starter"], 2, 0)).toBeNull();
    expect(homeTip(["starter"], 2, 1)).toBe("connect");
    expect(homeTip(["starter", "log"], 2, 1)).toBe("connect");
  });

  it("is done once both home tips are seen", () => {
    expect(homeTip(["starter", "connect"], 2, 3)).toBeNull();
  });
});

describe("topicTip", () => {
  it("shows the log tip until it's seen", () => {
    expect(topicTip([], false)).toBe("log");
    expect(topicTip(["log"], false)).toBeNull();
  });

  it("stays out of the way while the entry form is open", () => {
    expect(topicTip([], true)).toBeNull();
  });
});

describe("placeBubble", () => {
  const viewport = { width: 1000, height: 800 };
  const bubble = { width: 300, height: 120 };

  it("centres below the anchor when there's room", () => {
    const anchor = { top: 100, bottom: 140, left: 400, width: 200 };
    expect(placeBubble(anchor, bubble, viewport)).toEqual({
      side: "below", top: 152, left: 350, arrowX: 150,
    });
  });

  it("flips above when there's no room below", () => {
    const anchor = { top: 700, bottom: 740, left: 400, width: 200 };
    expect(placeBubble(anchor, bubble, viewport)).toMatchObject({ side: "above", top: 568 });
  });

  it("stays below when it fits neither way", () => {
    const anchor = { top: 50, bottom: 760, left: 400, width: 200 };
    expect(placeBubble(anchor, bubble, viewport).side).toBe("below");
  });

  it("keeps inside the viewport and still points at the anchor", () => {
    const anchor = { top: 10, bottom: 50, left: 940, width: 50 }; // centre 965
    const p = placeBubble(anchor, bubble, viewport);
    expect(p.left).toBe(1000 - 300 - 8);
    expect(p.arrowX).toBe(300 - 16); // clamped away from the rounded corner
  });
});
