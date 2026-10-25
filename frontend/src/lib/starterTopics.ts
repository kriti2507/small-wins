import type { FieldPayload } from "./fieldRows";

// Templates a new account picks its first topics from (StarterPicker). Each is
// an addTopic payload; everything can be renamed or changed later.
export type StarterTopic = {
  name: string;
  color: string;
  layout: string;
  fields: FieldPayload[];
};

export const MAX_STARTERS = 3;

const title: FieldPayload = { label: "Title", type: "text", direction: "none" };
const more = (label: string): FieldPayload => ({ label, type: "number", direction: "higher" });

export const STARTER_TOPICS: StarterTopic[] = [
  { name: "Workout", color: "green", layout: "photo-top", fields: [title, more("Duration (min)")] },
  { name: "Journal", color: "purple", layout: "photo-top", fields: [title] },
  { name: "Reading", color: "blue", layout: "photo-top", fields: [title, more("Pages")] },
  { name: "Meditation", color: "teal", layout: "photo-top", fields: [title, more("Minutes")] },
  { name: "Sleep", color: "indigo", layout: "photo-top", fields: [title, more("Hours")] },
  { name: "Learning", color: "amber", layout: "photo-top", fields: [title, more("Minutes")] },
  { name: "Gratitude", color: "rose", layout: "photo-top", fields: [title] },
  { name: "Cooking", color: "orange", layout: "photo-top", fields: [title] },
  { name: "Walk", color: "lime", layout: "photo-top", fields: [title, more("Steps")] },
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
  add: (topic: StarterTopic) => Promise<unknown>,
): Promise<void> {
  for (const t of STARTER_TOPICS.filter((t) => names.includes(t.name))) {
    await add(t);
  }
}
