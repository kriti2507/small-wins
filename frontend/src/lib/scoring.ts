import type { Topic, Entry } from "../types";

// Returns a 0..1 composite score for each entry. Scored fields are those with
// direction "higher" or "lower"; each is normalized across all entries and the
// per-entry scores are averaged. Entries with no scorable values get 0.5.
export function scoreEntries(topic: Topic, entries: Entry[]): number[] {
  const scored = topic.fields.filter(
    (f) => f.direction === "higher" || f.direction === "lower",
  );

  const ranges: Record<string, { min: number; max: number }> = {};
  scored.forEach((f) => {
    const vals = entries
      .map((e) => e[f.key])
      .filter((v): v is number => v != null && !isNaN(v as number));
    ranges[f.key] = { min: Math.min(...vals), max: Math.max(...vals) };
  });

  return entries.map((e) => {
    const parts: number[] = [];
    scored.forEach((f) => {
      const v = e[f.key];
      if (v == null || isNaN(v as number)) return;
      const { min, max } = ranges[f.key];
      let norm: number;
      if (max === min) norm = 0.5;
      else
        norm =
          f.direction === "higher"
            ? ((v as number) - min) / (max - min)
            : (max - (v as number)) / (max - min);
      parts.push(norm);
    });
    if (parts.length === 0) return 0.5;
    return parts.reduce((a, b) => a + b, 0) / parts.length;
  });
}
