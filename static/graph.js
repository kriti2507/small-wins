// Shared summary-graph rendering + scoring, used on both home and runs pages.

// Pace is stored as seconds per km. Accepts "8'35\"", "8:35", or a plain
// decimal number of minutes (e.g. "8.5"). Returns seconds, or NaN if invalid.
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

// Compute a 0..1 composite score for each run: distance (more is better)
// and pace (faster/lower is better), each normalized across all runs, averaged.
function scoreRuns(runs) {
  const distances = runs.map((r) => r.distance);
  const paces = runs.map((r) => r.pace);
  const minD = Math.min(...distances);
  const maxD = Math.max(...distances);
  const minP = Math.min(...paces);
  const maxP = Math.max(...paces);

  return runs.map((r) => {
    const dNorm = maxD === minD ? 0.5 : (r.distance - minD) / (maxD - minD);
    const pNorm = maxP === minP ? 0.5 : (maxP - r.pace) / (maxP - minP);
    return (dNorm + pNorm) / 2;
  });
}

// 5 buckets of green, light -> dark.
const GREENS = ["#d6f0c2", "#a7dd8b", "#6cc24a", "#3a9d23", "#1e6b10"];

function scoreToColor(score) {
  const idx = Math.min(GREENS.length - 1, Math.floor(score * GREENS.length));
  return GREENS[idx];
}

// Render the graph into `container` (a DOM element).
function renderGraph(container, runs) {
  container.innerHTML = "";
  if (runs.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "No runs yet. Add one to see your summary.";
    container.appendChild(empty);
    return;
  }

  // Oldest -> newest, left to right.
  const ordered = [...runs].sort((a, b) => (a.date < b.date ? -1 : 1));
  const scores = scoreRuns(ordered);

  const grid = document.createElement("div");
  grid.className = "graph-grid";

  ordered.forEach((run, i) => {
    const box = document.createElement("div");
    box.className = "graph-box";
    box.style.backgroundColor = scoreToColor(scores[i]);

    const hr = run.heart_rate != null ? `${run.heart_rate} bpm` : "—";
    box.title =
      `${run.date}` +
      `\n${run.title || "Untitled run"}` +
      `\nDistance: ${run.distance} km` +
      `\nPace: ${formatPace(run.pace)}/km` +
      `\nHeart rate: ${hr}`;

    grid.appendChild(box);
  });

  container.appendChild(grid);
}
