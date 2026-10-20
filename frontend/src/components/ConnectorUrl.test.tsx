import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import ConnectorUrl from "./ConnectorUrl";

describe("ConnectorUrl", () => {
  it("shows this site's MCP connector URL", () => {
    const html = renderToStaticMarkup(<ConnectorUrl origin="https://sw.example" />);
    expect(html).toContain("<code>https://sw.example/mcp</code>");
  });
});
