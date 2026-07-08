import type { Topic, Entry } from "../types";
import { scoreEntries } from "../lib/scoring";
import { rampFor, scoreToColor } from "../lib/palette";
import { formatValue } from "../lib/pace";

interface Props {
  topic: Topic;
  entries: Entry[];
  colorIndex: number;
}

// One box per entry (oldest -> newest), shaded by the entry's score.
export default function SummaryGraph({ topic, entries, colorIndex }: Props) {
  if (entries.length === 0) {
    return <p className="empty">No entries yet. Add one to see your summary.</p>;
  }

  const ordered = [...entries].sort((a, b) => (a.date < b.date ? -1 : 1));
  const scores = scoreEntries(topic, ordered);
  const palette = rampFor(topic, colorIndex);

  return (
    <div className="graph-grid">
      {ordered.map((entry, i) => {
        const lines = [entry.date || "(no date)"];
        topic.fields.forEach((f) => {
          lines.push(`${f.label}: ${formatValue(f, entry[f.key])}`);
        });
        return (
          <div
            key={entry.id}
            className="graph-box"
            style={{ backgroundColor: scoreToColor(scores[i], palette) }}
            title={lines.join("\n")}
          />
        );
      })}
    </div>
  );
}
