import { describe, it, expect } from "vitest";
import { appName, connectorUrl, formatDay, lastUsedLabel } from "./grants";

describe("grant display helpers", () => {
  it("formats a timestamp as a local day", () => {
    expect(formatDay("2026-10-15T12:00:00")).toBe("Oct 15, 2026");
  });

  it("says 'never' for an app that hasn't called yet", () => {
    expect(lastUsedLabel(null)).toBe("never");
    expect(lastUsedLabel("2026-01-02T12:00:00")).toBe("Jan 2, 2026");
  });

  it("names unnamed apps", () => {
    expect(appName({ client_name: "Claude" })).toBe("Claude");
    expect(appName({ client_name: null })).toBe("Unnamed app");
    expect(appName({ client_name: "  " })).toBe("Unnamed app");
  });

  it("builds the connector URL from the site's origin", () => {
    expect(connectorUrl("https://small-wins.example")).toBe("https://small-wins.example/mcp");
  });
});
