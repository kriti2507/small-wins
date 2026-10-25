import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import StarterPicker from "./StarterPicker";

const noop = () => {};

function render(initialSelected?: string[]) {
  return renderToStaticMarkup(<StarterPicker onDone={noop} initialSelected={initialSelected} />);
}

describe("StarterPicker", () => {
  it("explains the choice and that more can be added later", () => {
    const html = render();
    expect(html).toContain("What do you want to track?");
    expect(html).toContain("Pick up to 3 to start. You can add more and customize everything later.");
  });

  it("shows all 9 notes and disables Start until one is picked", () => {
    const html = render();
    expect(html.match(/class="starter-note[ "]/g)).toHaveLength(9);
    expect(html).toMatch(/<button[^>]*disabled[^>]*>Start tracking →<\/button>/);
    expect(html).toContain("Nothing picked yet");
  });

  it("circles picked notes and disables the rest once 3 are picked", () => {
    const html = render(["Workout", "Journal", "Sleep"]);
    expect(html.match(/aria-pressed="true"/g)).toHaveLength(3);
    expect(html.match(/class="starter-circle"/g)).toHaveLength(3);
    expect(html.match(/aria-pressed="false"[^>]*disabled/g)).toHaveLength(6);
    expect(html).not.toMatch(/<button[^>]*disabled[^>]*>Start tracking →<\/button>/);
    expect(html).toContain("3 of 3, nice picks!");
  });

  it("previews a capsule lane per pick, in catalog order, plus one open slot", () => {
    const html = render(["Sleep", "Workout"]);
    expect(html.match(/class="starter-lane"/g)).toHaveLength(2);
    expect(html.match(/class="starter-lane open"/g)).toHaveLength(1);
    expect(html.indexOf("🏃 Workout")).toBeLessThan(html.indexOf("🌙 Sleep"));
    expect(html).toContain("2 of 3 picked");
  });

  it("has no open slot once 3 are picked", () => {
    const html = render(["Workout", "Journal", "Sleep"]);
    expect(html.match(/class="starter-lane"/g)).toHaveLength(3);
    expect(html).not.toContain("starter-lane open");
  });
});
