import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { TipCard } from "./TipBubble";

const noop = () => {};

describe("TipCard", () => {
  it("shows the tip with Got it and Skip tips", () => {
    const html = renderToStaticMarkup(
      <TipCard onDismiss={noop} onSkipAll={noop}>
        <p>Add an entry</p>
      </TipCard>,
    );
    expect(html).toContain("<p>Add an entry</p>");
    expect(html).toContain(">Got it<");
    expect(html).toContain(">Skip tips<");
  });
});
