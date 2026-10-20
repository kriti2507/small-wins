import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import ActionMenu from "./ActionMenu";

describe("ActionMenu", () => {
  it("renders a closed, labelled ⋯ button", () => {
    const html = renderToStaticMarkup(
      <ActionMenu label="Actions for Workout" items={[{ label: "Edit", onSelect: () => {} }]} />,
    );
    expect(html).toContain('aria-label="Actions for Workout"');
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain("⋯");
    expect(html).not.toContain("action-menu-list");
  });
});
