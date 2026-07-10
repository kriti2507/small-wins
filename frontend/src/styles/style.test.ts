import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, test } from "vitest";

// Vitest mocks CSS imports to empty, so read the stylesheet from disk instead.
// Strip comments so their text can't leak into a rule's selector capture.
const css = readFileSync(
  fileURLToPath(new URL("./style.css", import.meta.url)),
  "utf8",
).replace(/\/\*[\s\S]*?\*\//g, "");

// Concatenated bodies of every rule whose selector list contains `selector`
// as a standalone selector (exact match — ignores `.on` / `:hover` variants).
function bodyOf(selector: string): string {
  const bodies: string[] = [];
  const re = /([^{}]+)\{([^}]*)\}/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(css))) {
    const selectors = m[1].split(",").map((s) => s.trim());
    if (selectors.includes(selector)) bodies.push(m[2]);
  }
  return bodies.join("\n");
}

// `.graph-box` is the shared, always-visible box class used by the Time Capsule
// calendar (Capsule.tsx). The spiral summary graph reveals its cells with
// `opacity: 0` until an `.on` class is added — that animation styling must live
// on a separate class (`.spiral-box`), or the capsule's boxes inherit it and
// vanish. Regression guard for that class collision.
describe("capsule / spiral CSS decoupling", () => {
  test(".graph-box stays visible (no spiral animation styling)", () => {
    const body = bodyOf(".graph-box");
    expect(body).not.toBe("");
    expect(body).not.toMatch(/opacity\s*:\s*0\b/);
    expect(body).not.toMatch(/position\s*:\s*absolute/);
  });

  test(".spiral-box carries the reveal animation", () => {
    const body = bodyOf(".spiral-box");
    expect(body).toMatch(/opacity\s*:\s*0\b/);
    expect(body).toMatch(/position\s*:\s*absolute/);
  });
});
