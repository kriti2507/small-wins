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

// 5 buckets of green, light -> dark.
const GREENS = ["#d6f0c2", "#a7dd8b", "#6cc24a", "#3a9d23", "#1e6b10"];

function scoreToColor(score) {
  const idx = Math.min(GREENS.length - 1, Math.floor(score * GREENS.length));
  return GREENS[idx];
}

// --- Graph -----------------------------------------------------------------

// Render one box per entry (oldest -> newest) into `container`.
function renderGraph(container, topic, entries) {
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

  const grid = document.createElement("div");
  grid.className = "graph-grid";

  ordered.forEach((entry, i) => {
    const box = document.createElement("div");
    box.className = "graph-box";
    box.style.backgroundColor = scoreToColor(scores[i]);

    const lines = [entry.date || "(no date)"];
    topic.fields.forEach((f) => {
      lines.push(`${f.label}: ${formatValue(f, entry[f.key])}`);
    });
    box.title = lines.join("\n");

    grid.appendChild(box);
  });

  container.appendChild(grid);
}
