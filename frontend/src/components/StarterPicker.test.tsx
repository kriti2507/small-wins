import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import StarterPicker from "./StarterPicker";

const noop = () => {};

describe("StarterPicker", () => {
  it("explains the choice and that more can be added later", () => {
    const html = renderToStaticMarkup(<StarterPicker onDone={noop} />);
    expect(html).toContain("What do you want to track?");
    expect(html).toContain("Pick up to 3 to start. You can add more and customize everything later.");
  });

  it("shows all 9 templates and disables Start until one is picked", () => {
    const html = renderToStaticMarkup(<StarterPicker onDone={noop} />);
    expect(html.match(/class="starter-card[ "]/g)).toHaveLength(9);
    expect(html).toMatch(/<button[^>]*disabled[^>]*>Start<\/button>/);
  });

  it("disables the unpicked cards once 3 are picked", () => {
    const html = renderToStaticMarkup(
      <StarterPicker onDone={noop} initialSelected={["Workout", "Journal", "Sleep"]} />,
    );
    expect(html.match(/aria-pressed="true"/g)).toHaveLength(3);
    expect(html.match(/aria-pressed="false"[^>]*disabled/g)).toHaveLength(6);
    expect(html).not.toMatch(/<button[^>]*disabled[^>]*>Start<\/button>/);
  });
});
