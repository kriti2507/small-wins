import type { Topic } from "../types";

// A palette is 5 shades of one hue, light -> dark, so a box's shade still
// reflects the entry's score while the hue identifies the topic. The user picks
// a topic's color by id; the darkest shade tints that topic's buttons.
// Softened brights: the same hues remixed to sit comfortably on warm paper —
// saturation turned down a notch so colors read lively, not fluorescent.
export const PALETTES: Record<string, string[]> = {
  green: ["#e0eed6", "#b5d9a0", "#8cc46c", "#5fa03e", "#417328"],
  blue: ["#dbe7f2", "#a9c8e3", "#7aa9cf", "#5386b3", "#3a6389"],
  orange: ["#f6e3d1", "#eec09a", "#e09a63", "#c97a40", "#9e5c2c"],
  purple: ["#e9e0f2", "#cbb5e3", "#a984cf", "#835bab", "#5f3f80"],
  teal: ["#d6ece8", "#a3d4cb", "#6fb8ab", "#479488", "#2f6e64"],
  rose: ["#f5dde4", "#e5afc0", "#d1839c", "#b35d7a", "#8a4159"],
  red: ["#f4ddd8", "#e3aca0", "#cd7f6f", "#b05a49", "#874337"],
  amber: ["#f6ead0", "#e9cf97", "#d9b160", "#b98f39", "#8d6b27"],
  indigo: ["#dfe1f0", "#b3b8dd", "#8890c6", "#6570ab", "#474f85"],
  cyan: ["#d8ebf0", "#a5d2dd", "#74b5c6", "#4d94a8", "#356e7e"],
  lime: ["#e9f0d2", "#cfdf9e", "#b0c968", "#8fa843", "#6a7d2f"],
  slate: ["#e2e4e7", "#bcc2c9", "#929aa4", "#6a727d", "#494f58"],
};

// Ordered ids — used for the picker and for position-based fallback.
export const PALETTE_ORDER = Object.keys(PALETTES);

// Ramp for a topic at position `i` in the list (wraps around). Fallback for
// topics with no saved color.
function paletteForIndex(i: number): string[] {
  const n = PALETTE_ORDER.length;
  return PALETTES[PALETTE_ORDER[((i % n) + n) % n]];
}

// The ramp for a topic: its saved color if valid, else the position fallback.
export function rampFor(topic: Topic | null | undefined, i: number): string[] {
  const id = topic && topic.color;
  return id && PALETTES[id] ? PALETTES[id] : paletteForIndex(i || 0);
}

// The strong (darkest) shade of a topic's ramp — used to tint its buttons.
export function buttonColorFor(topic: Topic | null | undefined, i: number): string {
  const ramp = rampFor(topic, i);
  return ramp[ramp.length - 1];
}

// Index of the vivid mid shade in each 5-shade ramp — used for the picker so
// swatches read bright rather than the darkest button-tint shade.
const SWATCH_SHADE = 2;

// [{ id, name, color }] for building the color picker, in display order.
export function paletteSwatches(): { id: string; name: string; color: string }[] {
  return PALETTE_ORDER.map((id) => ({
    id,
    name: id.charAt(0).toUpperCase() + id.slice(1),
    color: PALETTES[id][SWATCH_SHADE],
  }));
}

export function scoreToColor(score: number, palette: string[]): string {
  const idx = Math.min(palette.length - 1, Math.floor(score * palette.length));
  return palette[idx];
}
