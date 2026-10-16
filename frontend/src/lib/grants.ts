import type { Grant } from "../types";
import { MONTHS } from "./dates";

/** "Oct 15, 2026", in the viewer's time zone. */
export function formatDay(iso: string): string {
  const d = new Date(iso);
  return `${MONTHS[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
}

export function lastUsedLabel(iso: string | null): string {
  return iso ? formatDay(iso) : "never";
}

/** Apps name themselves when they register, but don't have to. */
export function appName(grant: Pick<Grant, "client_name">): string {
  return grant.client_name?.trim() || "Unnamed app";
}

/** The URL people paste into an MCP app to connect it. */
export function connectorUrl(origin: string): string {
  return `${origin}/mcp`;
}
