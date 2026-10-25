import type { FieldPayload } from "./fieldRows";

// Templates a new account picks its first topics from (StarterPicker). Each is
// an addTopic payload plus the icon and hint its note shows; everything can be
// renamed or changed later.
export type StarterTopic = {
  name: string;
  color: string;
  layout: string;
  fields: FieldPayload[];
  icon: string;
  hint: string;
};

export const MAX_STARTERS = 3;

const title: FieldPayload = { label: "Title", type: "text", direction: "none" };
const more = (label: string): FieldPayload => ({ label, type: "number", direction: "higher" });

export const STARTER_TOPICS: StarterTopic[] = [
  { name: "Workout", color: "green", layout: "photo-top", fields: [title, more("Duration (min)")], icon: "🏃", hint: "e.g. a 30 min run" },
  { name: "Journal", color: "purple", layout: "photo-top", fields: [title], icon: "📓", hint: "a few lines a day" },
  { name: "Reading", color: "blue", layout: "photo-top", fields: [title, more("Pages")], icon: "📚", hint: "pages you read" },
  { name: "Meditation", color: "teal", layout: "photo-top", fields: [title, more("Minutes")], icon: "🧘", hint: "minutes of calm" },
  { name: "Sleep", color: "indigo", layout: "photo-top", fields: [title, more("Hours")], icon: "🌙", hint: "hours you slept" },
  { name: "Learning", color: "amber", layout: "photo-top", fields: [title, more("Minutes")], icon: "💡", hint: "time spent learning" },
  { name: "Gratitude", color: "rose", layout: "photo-top", fields: [title], icon: "🌷", hint: "one good thing" },
  { name: "Cooking", color: "orange", layout: "photo-top", fields: [title], icon: "🍳", hint: "meals you made" },
  { name: "Walk", color: "lime", layout: "photo-top", fields: [title, more("Steps")], icon: "👣", hint: "steps outside" },
];

/** `selected` with `name` toggled; a new pick past MAX_STARTERS is ignored. */
export function toggleStarter(selected: string[], name: string): string[] {
  if (selected.includes(name)) return selected.filter((n) => n !== name);
  return selected.length >= MAX_STARTERS ? selected : [...selected, name];
}

/** Create the chosen templates one by one, in catalog order, so the new
 *  topics appear in the same order as on the picker. Stops at the first error. */
export async function createStarters(
  names: string[],
  add: (topic: Pick<StarterTopic, "name" | "color" | "layout" | "fields">) => Promise<unknown>,
): Promise<void> {
  for (const { name, color, layout, fields } of STARTER_TOPICS.filter((t) => names.includes(t.name))) {
    await add({ name, color, layout, fields });
  }
}

// Days in the picker's sample time capsule (two rows of a fortnight).
export const PREVIEW_DAYS = 28;

/** Made-up but stable shades for a template's sample capsule: -1 for a day
 *  with nothing logged, else an index into its 5-shade palette. Seeded by the
 *  name so a lane looks the same on every render. */
export function previewShades(name: string): number[] {
  let seed = 0;
  for (const ch of name) seed = (seed * 31 + ch.charCodeAt(0)) >>> 0;
  return Array.from({ length: PREVIEW_DAYS }, () => {
    seed = (seed * 1664525 + 1013904223) >>> 0; // LCG step
    const r = seed / 2 ** 32;
    return r < 0.3 ? -1 : Math.min(4, Math.floor(((r - 0.3) / 0.7) * 5));
  });
}
