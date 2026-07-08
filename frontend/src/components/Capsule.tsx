import type { Topic, Entry, DateRange } from "../types";
import { rampFor, scoreToColor } from "../lib/palette";
import { formatValue } from "../lib/pace";
import {
  enumerateDays,
  weekdayIndex,
  addDays,
  formatCellLabel,
  WEEKDAYS,
} from "../lib/dates";

// Per-topic data the capsule renders. scoreById maps entry.id -> score,
// computed over the topic's full entry set so a box's shade matches its
// topic page.
export interface CapsuleTopicData {
  topic: Topic;
  colorIndex: number;
  entries: Entry[];
  scoreById: Record<number, number>;
}

interface Props {
  topicsData: CapsuleTopicData[];
  range: DateRange;
}

interface Box {
  topic: Topic;
  entry: Entry;
  palette: string[];
  score: number | undefined;
}

// A calendar of day cells spanning `range`, stacking a colored box per entry
// across all topics.
export default function Capsule({ topicsData, range }: Props) {
  const days = enumerateDays(range.start, range.end);

  // Bucket entries by date. Each box carries what it needs to render.
  const byDay: Record<string, Box[]> = {};
  days.forEach((d) => (byDay[d] = []));
  let total = 0;
  topicsData.forEach(({ topic, colorIndex, entries, scoreById }) => {
    const palette = rampFor(topic, colorIndex);
    entries.forEach((entry) => {
      if (!entry.date || !(entry.date in byDay)) return;
      byDay[entry.date].push({ topic, entry, palette, score: scoreById[entry.id] });
      total += 1;
    });
  });

  if (days.length === 0 || total === 0) {
    return <p className="empty">No entries in this period.</p>;
  }

  // Pad to whole weeks; days outside the selected range are muted placeholders.
  const gridStart = addDays(range.start, -weekdayIndex(range.start));
  const gridEnd = addDays(range.end, 6 - weekdayIndex(range.end));
  const gridDays = enumerateDays(gridStart, gridEnd);

  return (
    <div className="calendar">
      {WEEKDAYS.map((name) => (
        <div key={name} className="weekday-head">
          {name}
        </div>
      ))}
      {gridDays.map((day) => {
        const inRange = day in byDay;
        return (
          <div key={day} className={inRange ? "day-cell" : "day-cell outside"}>
            <div className="day-label">{formatCellLabel(day)}</div>
            {inRange && (
              <div className="day-boxes">
                {byDay[day].map(({ topic, entry, palette, score }, i) => {
                  const lines = [topic.name, entry.date];
                  topic.fields.forEach((f) => {
                    lines.push(`${f.label}: ${formatValue(f, entry[f.key])}`);
                  });
                  return (
                    <div
                      key={i}
                      className="graph-box"
                      style={{
                        backgroundColor: scoreToColor(score == null ? 0.5 : score, palette),
                      }}
                      title={lines.join("\n")}
                    />
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
