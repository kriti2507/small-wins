import type { Topic, Entry, DateRange } from "../types";
import { scoreEntries } from "../lib/scoring";
import { rampFor, scoreToColor } from "../lib/palette";
import { formatValue } from "../lib/pace";
import { enumerateDays, weekdayIndex, addDays, MONTHS } from "../lib/dates";

interface Props {
  topic: Topic;
  entries: Entry[];
  colorIndex: number;
  range: DateRange;
}

// GitHub-style contribution graph: one cell per calendar day across `range`,
// so gaps between entries show as empty space. Weeks are columns (Mon->Sun,
// top to bottom) flowing left->right. A day's shade is the average score of
// that day's entries; days with no entry are a faint neutral.
export default function ContributionGraph({ topic, entries, colorIndex, range }: Props) {
  if (entries.length === 0) {
    return <p className="empty">No entries yet. Add one to see your summary.</p>;
  }

  const days = enumerateDays(range.start, range.end);
  if (days.length === 0) {
    return <p className="empty">No entries in this period.</p>;
  }

  const palette = rampFor(topic, colorIndex);

  // Score every entry over the full set, then bucket by date so days with
  // several entries can be averaged into a single cell.
  const scores = scoreEntries(topic, entries);
  const byDay: Record<string, { entries: Entry[]; sum: number }> = {};
  entries.forEach((entry, i) => {
    if (!entry.date) return;
    const b = byDay[entry.date] || (byDay[entry.date] = { entries: [], sum: 0 });
    b.entries.push(entry);
    b.sum += scores[i];
  });

  // Pad to whole weeks so the 7 weekday rows stay aligned.
  const gridStart = addDays(range.start, -weekdayIndex(range.start));
  const gridEnd = addDays(range.end, 6 - weekdayIndex(range.end));
  const gridDays = enumerateDays(gridStart, gridEnd);
  const numWeeks = gridDays.length / 7;
  const inRange = new Set(days);

  // Month labels: one slot per week column, labeled when the week's Monday
  // falls in a different month than the previous column's.
  const monthSlots: (string | null)[] = [];
  let prevMonth = -1;
  for (let w = 0; w < numWeeks; w++) {
    const monday = gridDays[w * 7];
    const month = parseInt(monday.split("-")[1], 10) - 1;
    if (month !== prevMonth) {
      monthSlots.push(MONTHS[month]);
      prevMonth = month;
    } else {
      monthSlots.push(null);
    }
  }

  return (
    <>
      <div className="contrib-months">
        {monthSlots.map((label, i) => (
          <span key={i}>{label}</span>
        ))}
      </div>
      <div className="contrib-grid">
        {gridDays.map((day) => {
          const bucket = byDay[day];
          if (!inRange.has(day)) {
            return <div key={day} className="contrib-cell pad" />;
          }
          if (bucket) {
            const lines: string[] = [];
            bucket.entries.forEach((entry) => {
              lines.push(entry.date);
              topic.fields.forEach((f) =>
                lines.push(`${f.label}: ${formatValue(f, entry[f.key])}`),
              );
            });
            return (
              <div
                key={day}
                className="contrib-cell"
                style={{
                  backgroundColor: scoreToColor(bucket.sum / bucket.entries.length, palette),
                }}
                title={lines.join("\n")}
              />
            );
          }
          return <div key={day} className="contrib-cell empty-day" title={day} />;
        })}
      </div>
    </>
  );
}
