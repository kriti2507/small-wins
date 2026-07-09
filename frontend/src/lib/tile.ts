import type { Topic, Entry } from "../types";
import { formatValue } from "./pace";

export interface TileModel {
  heading: string;
  meta: string;
  initial: string;
  image: string | null;
}

// Pure view model for one entry tile. Heading is the first text field, else the
// date; meta is the remaining fields plus the date, `·`-joined; initial is the
// heading's first character (for the no-photo fallback block).
export function tileModel(topic: Topic, entry: Entry): TileModel {
  const titleField = topic.fields.find((f) => f.type === "text");
  const heading = String(
    (titleField && entry[titleField.key]) || entry.date || "Entry",
  );
  const meta = topic.fields
    .filter((f) => f !== titleField)
    .map((f) => `${f.label}: ${formatValue(f, entry[f.key])}`)
    .concat(`Date: ${entry.date}`)
    .join(" · ");
  const trimmed = heading.trim();
  const initial = trimmed ? trimmed[0].toUpperCase() : "?";
  const image = (entry.image as string) || null;
  return { heading, meta, initial, image };
}
