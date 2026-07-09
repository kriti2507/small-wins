// Pace is stored as seconds per km.
import type { Field, Block } from "../types";

// Accepts "8'35\"", "8:35", or a plain decimal number of minutes ("8.5").
// Returns seconds, or NaN if invalid.
export function parsePace(str: string | null | undefined): number {
  if (str == null) return NaN;
  const s = String(str).trim();
  const m = s.match(/^(\d+)\s*['":]\s*(\d{1,2})\s*"?$/);
  if (m) {
    return parseInt(m[1], 10) * 60 + parseInt(m[2], 10);
  }
  const n = Number(s);
  return isNaN(n) ? NaN : Math.round(n * 60);
}

// Format seconds-per-km as "8'35\"".
export function formatPace(sec: number | null | undefined): string {
  if (sec == null || isNaN(sec)) return "—";
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}'${String(s).padStart(2, "0")}"`;
}

// Human-readable value for a field.
export function formatValue(
  field: Field,
  value: string | number | null | undefined | Block[],
): string | number {
  if (value == null || value === "" || Array.isArray(value)) return "—";
  if (field.type === "pace") return formatPace(value as number);
  return value;
}
