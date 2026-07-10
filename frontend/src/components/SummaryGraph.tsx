import { useEffect, useRef, useState } from "react";
import type { Topic, Entry } from "../types";
import { scoreEntries } from "../lib/scoring";
import { rampFor, scoreToColor } from "../lib/palette";
import { formatValue } from "../lib/pace";
import { spiralCoords, spiralSpan, cellSizeFor, revealDelayMs } from "../lib/spiral";
import HoverCell from "./HoverCell";

interface Props {
  topic: Topic;
  entries: Entry[];
  colorIndex: number;
}

// Layout/timing constants. AVAILABLE_WIDTH is the card's usable inner width
// (~280px card minus padding); the spiral scales its cells to fit this.
const AVAILABLE_WIDTH = 220;
const GAP = 3;
const MIN_CELL = 4;
const MAX_CELL = 16;
const TARGET_DRAW_MS = 2500; // aim for ~constant total draw time
const MIN_DELAY = 8;
const MAX_DELAY = 110;
const HOLD_MS = 1500; // pause on the full spiral before clearing
const RESET_MS = 350; // blank pause before replaying

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

// Entries laid out along a square spiral (oldest at center -> newest at the
// edge), shaded by score. The spiral draws in one cell at a time and loops
// GIF-style; it pauses fully-drawn while hovered so tooltips are usable, and
// renders statically when the user prefers reduced motion.
export default function SummaryGraph({ topic, entries, colorIndex }: Props) {
  const count = entries.length;
  const ordered = [...entries].sort((a, b) => (a.date < b.date ? -1 : 1));
  const scores = scoreEntries(topic, ordered);
  const palette = rampFor(topic, colorIndex);

  const coords = spiralCoords(count);
  const span = spiralSpan(count);
  const cell = cellSizeFor(span, AVAILABLE_WIDTH, GAP, MIN_CELL, MAX_CELL);
  const step = cell + GAP;
  const stagePx = span > 0 ? span * cell + (span - 1) * GAP : 0;
  const delay = revealDelayMs(count, TARGET_DRAW_MS, MIN_DELAY, MAX_DELAY);

  // Shift the (possibly negative) coordinates so the top-left cell is at 0,0.
  const minX = coords.length ? Math.min(...coords.map((c) => c[0])) : 0;
  const minY = coords.length ? Math.min(...coords.map((c) => c[1])) : 0;

  const reduced = prefersReducedMotion();
  const [visible, setVisible] = useState(reduced ? count : 0);
  const pausedRef = useRef(false);
  const nRef = useRef(0);

  useEffect(() => {
    if (reduced || count === 0) {
      setVisible(count);
      return;
    }
    setVisible(0);
    nRef.current = 0;
    let timer = window.setTimeout(tick, delay);
    function tick() {
      if (pausedRef.current) {
        timer = window.setTimeout(tick, 120);
        return;
      }
      if (nRef.current < count) {
        nRef.current += 1;
        setVisible(nRef.current);
        timer = window.setTimeout(tick, delay);
      } else {
        timer = window.setTimeout(() => {
          nRef.current = 0;
          setVisible(0);
          timer = window.setTimeout(tick, RESET_MS);
        }, HOLD_MS);
      }
    }
    return () => window.clearTimeout(timer);
  }, [count, delay, reduced]);

  if (count === 0) {
    return <p className="empty">No entries yet. Add one to see your summary.</p>;
  }

  return (
    <div
      className="spiral-stage"
      style={{ width: stagePx, height: stagePx }}
      onMouseEnter={() => {
        pausedRef.current = true;
        if (!reduced) setVisible(count);
      }}
      onMouseLeave={() => {
        nRef.current = count;
        pausedRef.current = false;
      }}
    >
      {coords.map((c, i) => {
        const entry = ordered[i];
        const lines = [entry.date || "(no date)"];
        topic.fields.forEach((f) => {
          lines.push(`${f.label}: ${formatValue(f, entry[f.key])}`);
        });
        const on = i < visible;
        return (
          <HoverCell
            key={entry.id}
            className={on ? "spiral-box on" : "spiral-box"}
            style={{
              width: cell,
              height: cell,
              left: (c[0] - minX) * step,
              top: (c[1] - minY) * step,
              backgroundColor: scoreToColor(scores[i], palette),
            }}
            lines={lines}
          />
        );
      })}
    </div>
  );
}
