import type { Topic } from "../types";

// A palette is 5 shades of one hue, light -> dark, so a box's shade still
// reflects the entry's score while the hue identifies the topic. The user picks
// a topic's color by id; the darkest shade tints that topic's buttons.
export const PALETTES: Record<string, string[]> = {
  green: ["#d9f7c0", "#93ec5e", "#4fdc17", "#2eb500", "#1c7a00"],
  blue: ["#cfe6ff", "#8ec2ff", "#3d92ff", "#0f66f0", "#0a4bc0"],
  orange: ["#ffe0bd", "#ffb56b", "#ff8a1f", "#f26a00", "#c25000"],
  purple: ["#ecd6ff", "#c98eff", "#a347ff", "#8215e6", "#6410b0"],
  teal: ["#bff7ee", "#6fecd8", "#1fd9bd", "#06b39a", "#058070"],
  rose: ["#ffd3e0", "#ff8fb0", "#ff4d7d", "#ed1a54", "#b8003c"],
  red: ["#ffd2cd", "#ff8f83", "#ff4f3d", "#ed2410", "#b81404"],
  amber: ["#fff0a8", "#ffdd52", "#ffc814", "#e6a800", "#b88200"],
  indigo: ["#d9dcff", "#a3aaff", "#6670ff", "#3b46f0", "#2730c0"],
  cyan: ["#c2f2ff", "#6fdfff", "#1fc6f0", "#049bc2", "#037394"],
  lime: ["#eafcbf", "#ccf56f", "#a3e61f", "#82c200", "#5f9000"],
  slate: ["#dfe3e8", "#b4bcc6", "#838d99", "#5a636e", "#363d45"],
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

// [{ id, name, color }] for building the color picker, in display order.
export function paletteSwatches(): { id: string; name: string; color: string }[] {
  return PALETTE_ORDER.map((id) => ({
    id,
    name: id.charAt(0).toUpperCase() + id.slice(1),
    color: PALETTES[id][PALETTES[id].length - 1],
  }));
}

export function scoreToColor(score: number, palette: string[]): string {
  const idx = Math.min(palette.length - 1, Math.floor(score * palette.length));
  return palette[idx];
}
