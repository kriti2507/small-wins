export const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

// Local "YYYY-MM-DD" for a Date.
export function isoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

// All "YYYY-MM-DD" dates from `start` to `end` inclusive, oldest -> newest.
// Returns [] if the range is empty or reversed.
export function enumerateDays(start: string, end: string): string[] {
  if (!start || !end || start > end) return [];
  const days: string[] = [];
  const d = new Date(start + "T00:00:00");
  const last = new Date(end + "T00:00:00");
  while (d <= last) {
    days.push(isoDate(d));
    d.setDate(d.getDate() + 1);
  }
  return days;
}

// Days-since-Monday for a date (Mon=0 ... Sun=6).
export function weekdayIndex(dateStr: string): number {
  return (new Date(dateStr + "T00:00:00").getDay() + 6) % 7;
}

// Shift a "YYYY-MM-DD" by `delta` days.
export function addDays(dateStr: string, delta: number): string {
  const d = new Date(dateStr + "T00:00:00");
  d.setDate(d.getDate() + delta);
  return isoDate(d);
}

// Cell label: day-of-month, prefixed with the month on the 1st for context.
export function formatCellLabel(dateStr: string): string {
  const [, m, d] = dateStr.split("-");
  const day = parseInt(d, 10);
  return day === 1 ? `${MONTHS[parseInt(m, 10) - 1]} 1` : String(day);
}
