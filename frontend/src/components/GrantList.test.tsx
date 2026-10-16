import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import GrantList from "./GrantList";
import type { Grant } from "../types";

const GRANTS: Grant[] = [
  { id: 2, client_name: "Claude", redirect_host: "claude.ai",
    created_at: "2026-10-15T12:00:00", last_used_at: null },
  { id: 1, client_name: null, redirect_host: "cursor://x/cb",
    created_at: "2026-09-01T12:00:00", last_used_at: "2026-10-01T12:00:00" },
];

const noop = () => {};

function render(props: Partial<Parameters<typeof GrantList>[0]> = {}) {
  return renderToStaticMarkup(
    <GrantList grants={GRANTS} confirming={null} busy={false} origin="https://sw.example"
      onAsk={noop} onConfirm={noop} onCancel={noop} {...props} />,
  );
}

describe("GrantList", () => {
  it("lists each app with where it redirects and when it was used", () => {
    const html = render();
    expect(html).toContain("Claude");
    expect(html).toContain("Redirects to claude.ai");
    expect(html).toContain("Connected Oct 15, 2026");
    expect(html).toContain("Last used never");
    expect(html).toContain("Unnamed app");
    expect(html).toContain("Last used Oct 1, 2026");
    expect(html.match(/>Revoke</g)).toHaveLength(2);
  });

  it("asks to confirm before revoking, on that row only", () => {
    const html = render({ confirming: 2 });
    expect(html).toContain("Revoke Claude?");
    expect(html).not.toContain("Revoke Unnamed app?");
    expect(html).toContain(">Keep<");
  });

  it("explains how to connect an app when there are none", () => {
    const html = render({ grants: [] });
    expect(html).toContain("No apps are connected");
    expect(html).toContain("https://sw.example/mcp");
  });
});
