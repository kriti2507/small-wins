import type { Topic, Entry } from "../types";
import { formatValue } from "../lib/pace";

interface Props {
  topic: Topic;
  entries: Entry[];
}

// Entries newest-first. The first text field, if any, is used as the heading.
export default function EntryList({ topic, entries }: Props) {
  const ordered = [...entries].sort((a, b) => (a.date < b.date ? 1 : -1));
  const titleField = topic.fields.find((f) => f.type === "text");

  return (
    <ul className="run-list">
      {ordered.map((entry) => {
        const heading =
          (titleField && entry[titleField.key]) || entry.date || "Entry";
        const meta = topic.fields
          .filter((f) => f !== titleField)
          .map((f) => `${f.label}: ${formatValue(f, entry[f.key])}`)
          .concat(`Date: ${entry.date}`)
          .join(" · ");
        return (
          <li className="run-item" key={entry.id}>
            <strong>{heading}</strong>
            <span className="meta">{meta}</span>
          </li>
        );
      })}
    </ul>
  );
}
