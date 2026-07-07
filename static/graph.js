// Shared helpers: pace parsing, field formatting, scoring, and the summary
// graph. Used on both the home and topic pages.

// --- Pace (stored as seconds per km) ---------------------------------------

// Accepts "8'35\"", "8:35", or a plain decimal number of minutes ("8.5").
// Returns seconds, or NaN if invalid.
function parsePace(str) {
  if (str == null) return NaN;
  const s = String(str).trim();
  const m = s.match(/^(\d+)\s*['":]\s*(\d{1,2})\s*"?$/);
  if (m) {
    return parseInt(m[1], 10) * 60 + parseInt(m[2], 10);
  }
  const n = Number(s);
  return isNaN(n) ? NaN : Math.round(n * 60);
}

// Format seconds-per-km as "8'35"".
function formatPace(sec) {
  if (sec == null || isNaN(sec)) return "—";
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}'${String(s).padStart(2, "0")}"`;
}

// Human-readable value for a field.
function formatValue(field, value) {
  if (value == null || value === "") return "—";
  if (field.type === "pace") return formatPace(value);
  return value;
}

// --- Scoring ---------------------------------------------------------------

// Returns a 0..1 composite score for each entry. Scored fields are those with
// direction "higher" or "lower"; each is normalized across all entries and the
// per-entry scores are averaged. Entries with no scorable values get 0.5.
function scoreEntries(topic, entries) {
  const scored = topic.fields.filter(
    (f) => f.direction === "higher" || f.direction === "lower"
  );

  const ranges = {};
  scored.forEach((f) => {
    const vals = entries
      .map((e) => e[f.key])
      .filter((v) => v != null && !isNaN(v));
    ranges[f.key] = { min: Math.min(...vals), max: Math.max(...vals) };
  });

  return entries.map((e) => {
    const parts = [];
    scored.forEach((f) => {
      const v = e[f.key];
      if (v == null || isNaN(v)) return;
      const { min, max } = ranges[f.key];
      let norm;
      if (max === min) norm = 0.5;
      else norm = f.direction === "higher" ? (v - min) / (max - min) : (max - v) / (max - min);
      parts.push(norm);
    });
    if (parts.length === 0) return 0.5;
    return parts.reduce((a, b) => a + b, 0) / parts.length;
  });
}

// A palette is 5 shades of one hue, light -> dark, so a box's shade still
// reflects the entry's score while the hue identifies the topic. The user picks
// a topic's color by id (see the create form); the darkest shade is used to
// tint that topic's buttons.
const PALETTES = {
  green: ["#d6f0c2", "#a7dd8b", "#6cc24a", "#3a9d23", "#1e6b10"],
  blue: ["#cfe3fb", "#9cc4f5", "#5b9be8", "#2f6fcf", "#1a4a94"],
  orange: ["#ffe1c2", "#ffc088", "#f99746", "#e2701a", "#a84e08"],
  purple: ["#e6d6f5", "#c9a7e8", "#a76cd6", "#7f3ac2", "#571d8f"],
  teal: ["#c8f0ea", "#8dddd0", "#4ec2b0", "#1f9d89", "#0f6b5c"],
  rose: ["#fcd6df", "#f59cb2", "#e85b7f", "#cf2f57", "#941a3a"],
  red: ["#fbd5d1", "#f2a099", "#e56a5e", "#cf3b2c", "#971f13"],
  amber: ["#fbeeb0", "#f5da6b", "#ecc031", "#c99a15", "#8f6a08"],
  indigo: ["#d9dcf7", "#adb3ec", "#7a83db", "#4c56c0", "#2b3287"],
  cyan: ["#c9eef7", "#8bd8ec", "#46bcd9", "#1f95b5", "#0f6478"],
  lime: ["#e6f5c2", "#c9e88b", "#a7d24a", "#7fae23", "#567610"],
  slate: ["#dfe3e8", "#b4bcc6", "#838d99", "#5a636e", "#363d45"],
};

// Ordered ids — used for the picker and for position-based fallback.
const PALETTE_ORDER = Object.keys(PALETTES);

// Ramp for a topic at position `i` in the list (wraps around). Fallback for
// topics with no saved color.
function paletteForIndex(i) {
  const n = PALETTE_ORDER.length;
  return PALETTES[PALETTE_ORDER[((i % n) + n) % n]];
}

// The ramp for a topic: its saved color if valid, else the position fallback.
function rampFor(topic, i) {
  const id = topic && topic.color;
  return id && PALETTES[id] ? PALETTES[id] : paletteForIndex(i || 0);
}

// The strong (darkest) shade of a topic's ramp — used to tint its buttons.
function buttonColorFor(topic, i) {
  const ramp = rampFor(topic, i);
  return ramp[ramp.length - 1];
}

// [{ id, name, color }] for building the color picker, in display order.
function paletteSwatches() {
  return PALETTE_ORDER.map((id) => ({
    id,
    name: id.charAt(0).toUpperCase() + id.slice(1),
    color: PALETTES[id][PALETTES[id].length - 1],
  }));
}

function scoreToColor(score, palette) {
  const idx = Math.min(palette.length - 1, Math.floor(score * palette.length));
  return palette[idx];
}

// --- Graph -----------------------------------------------------------------

// Render one box per entry (oldest -> newest) into `container`.
// `colorIndex` picks the topic's color ramp (defaults to the first palette).
function renderGraph(container, topic, entries, colorIndex = 0) {
  container.innerHTML = "";
  if (entries.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "No entries yet. Add one to see your summary.";
    container.appendChild(empty);
    return;
  }

  const ordered = [...entries].sort((a, b) => (a.date < b.date ? -1 : 1));
  const scores = scoreEntries(topic, ordered);
  const palette = rampFor(topic, colorIndex);

  const grid = document.createElement("div");
  grid.className = "graph-grid";

  ordered.forEach((entry, i) => {
    const box = document.createElement("div");
    box.className = "graph-box";
    box.style.backgroundColor = scoreToColor(scores[i], palette);

    const lines = [entry.date || "(no date)"];
    topic.fields.forEach((f) => {
      lines.push(`${f.label}: ${formatValue(f, entry[f.key])}`);
    });
    box.title = lines.join("\n");

    grid.appendChild(box);
  });

  container.appendChild(grid);
}

// --- Contribution graph (topic page) ---------------------------------------

// A GitHub-style contribution graph: one cell per calendar day across `range`
// ({start, end}), so gaps between entries show up as empty space. Weeks are
// columns (Mon->Sun, top to bottom) flowing left->right. A day's shade is the
// average score of that day's entries (scored over the topic's full entry set,
// so shades match the rest of the app); days with no entry are a faint neutral.
// A month-label row sits above the grid for time context.
function renderContributions(container, topic, entries, colorIndex, range) {
  container.innerHTML = "";

  if (entries.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "No entries yet. Add one to see your summary.";
    container.appendChild(empty);
    return;
  }

  const days = enumerateDays(range.start, range.end);
  if (days.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "No entries in this period.";
    container.appendChild(empty);
    return;
  }

  const palette = rampFor(topic, colorIndex);

  // Score every entry over the full set, then bucket by date so days with
  // several entries can be averaged into a single cell.
  const scores = scoreEntries(topic, entries);
  const byDay = {};
  entries.forEach((entry, i) => {
    if (!entry.date) return;
    const b = byDay[entry.date] || (byDay[entry.date] = { entries: [], sum: 0 });
    b.entries.push(entry);
    b.sum += scores[i];
  });

  // Pad to whole weeks: from the Monday on/before the range start to the Sunday
  // on/after the range end, so the 7 weekday rows stay aligned.
  const gridStart = addDays(range.start, -weekdayIndex(range.start));
  const gridEnd = addDays(range.end, 6 - weekdayIndex(range.end));
  const gridDays = enumerateDays(gridStart, gridEnd);
  const numWeeks = gridDays.length / 7;
  const inRange = new Set(days);

  // Month labels: one slot per week column, labeled when the week's Monday
  // falls in a different month than the previous column's.
  const months = document.createElement("div");
  months.className = "contrib-months";
  let prevMonth = -1;
  for (let w = 0; w < numWeeks; w++) {
    const monday = gridDays[w * 7];
    const month = parseInt(monday.split("-")[1], 10) - 1;
    const slot = document.createElement("span");
    if (month !== prevMonth) {
      slot.textContent = MONTHS[month];
      prevMonth = month;
    }
    months.appendChild(slot);
  }

  const grid = document.createElement("div");
  grid.className = "contrib-grid";

  gridDays.forEach((day) => {
    const cell = document.createElement("div");
    cell.className = "contrib-cell";
    const bucket = byDay[day];
    if (!inRange.has(day)) {
      cell.classList.add("pad"); // padding outside the selected range
    } else if (bucket) {
      cell.style.backgroundColor = scoreToColor(bucket.sum / bucket.entries.length, palette);
      const lines = [];
      bucket.entries.forEach((entry) => {
        lines.push(entry.date);
        topic.fields.forEach((f) => lines.push(`${f.label}: ${formatValue(f, entry[f.key])}`));
      });
      cell.title = lines.join("\n");
    } else {
      cell.classList.add("empty-day");
      cell.title = day;
    }
    grid.appendChild(cell);
  });

  container.appendChild(months);
  container.appendChild(grid);
}

// --- Time capsule ----------------------------------------------------------

// Local "YYYY-MM-DD" for a Date.
function isoOf(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

// All "YYYY-MM-DD" dates from `start` to `end` inclusive, oldest -> newest.
// Returns [] if the range is empty or reversed.
function enumerateDays(start, end) {
  if (!start || !end || start > end) return [];
  const days = [];
  const d = new Date(start + "T00:00:00");
  const last = new Date(end + "T00:00:00");
  while (d <= last) {
    days.push(isoOf(d));
    d.setDate(d.getDate() + 1);
  }
  return days;
}

// Days-since-Monday for a date (Mon=0 ... Sun=6).
function weekdayIndex(dateStr) {
  return (new Date(dateStr + "T00:00:00").getDay() + 6) % 7;
}

// Shift a "YYYY-MM-DD" by `delta` days.
function addDays(dateStr, delta) {
  const d = new Date(dateStr + "T00:00:00");
  d.setDate(d.getDate() + delta);
  return isoOf(d);
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

// Cell label: day-of-month, prefixed with the month on the 1st for context.
function formatCellLabel(dateStr) {
  const [, m, d] = dateStr.split("-");
  const day = parseInt(d, 10);
  return day === 1 ? `${MONTHS[parseInt(m, 10) - 1]} 1` : String(day);
}

// Render a calendar of day columns spanning `range` ({start, end}), stacking a
// colored box per entry across all topics. `topicsData` is an array of
// { topic, colorIndex, entries, scoreById } where scoreById maps entry.id ->
// score (computed over the topic's full entry set — see buildTopicsData).
function renderCapsule(container, topicsData, range) {
  container.innerHTML = "";
  const days = enumerateDays(range.start, range.end);

  // Bucket entries by date. Each item carries what a box needs to render.
  const byDay = {};
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
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "No entries in this period.";
    container.appendChild(empty);
    return;
  }

  const calendar = document.createElement("div");
  calendar.className = "calendar";

  // Weekday headers (Mon -> Sun).
  WEEKDAYS.forEach((name) => {
    const h = document.createElement("div");
    h.className = "weekday-head";
    h.textContent = name;
    calendar.appendChild(h);
  });

  // Pad to whole weeks: the grid runs from the Monday on/before the range
  // start to the Sunday on/after the range end. Days outside the selected
  // range are rendered as muted placeholder cells so weekdays stay aligned.
  const gridStart = addDays(range.start, -weekdayIndex(range.start));
  const gridEnd = addDays(range.end, 6 - weekdayIndex(range.end));

  enumerateDays(gridStart, gridEnd).forEach((day) => {
    const cell = document.createElement("div");
    const inRange = day in byDay;
    cell.className = inRange ? "day-cell" : "day-cell outside";

    const label = document.createElement("div");
    label.className = "day-label";
    label.textContent = formatCellLabel(day);
    cell.appendChild(label);

    if (inRange) {
      const boxes = document.createElement("div");
      boxes.className = "day-boxes";
      byDay[day].forEach(({ topic, entry, palette, score }) => {
        const box = document.createElement("div");
        box.className = "graph-box";
        box.style.backgroundColor = scoreToColor(
          score == null ? 0.5 : score,
          palette
        );
        const lines = [topic.name, entry.date];
        topic.fields.forEach((f) => {
          lines.push(`${f.label}: ${formatValue(f, entry[f.key])}`);
        });
        box.title = lines.join("\n");
        boxes.appendChild(box);
      });
      cell.appendChild(boxes);
    }

    calendar.appendChild(cell);
  });

  container.appendChild(calendar);
}
