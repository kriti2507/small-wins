import { useState } from "react";
import type { CSSProperties } from "react";
import { createPortal } from "react-dom";

interface Props {
  className: string;
  style?: CSSProperties;
  // One tooltip line per array entry, shown stacked on hover.
  lines: string[];
}

// A single colored graph cell with an instant, cursor-following tooltip.
// Shared by SummaryGraph and ContributionGraph so every cell hovers the same
// way — no native `title` delay. The tooltip is portaled to <body> so the
// cell's :hover transform (scale) can't become its containing block and fling
// it across the screen; position:fixed then tracks the viewport correctly.
export default function HoverCell({ className, style, lines }: Props) {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);

  return (
    <div
      className={className}
      style={style}
      onMouseEnter={(e) => setPos({ x: e.clientX, y: e.clientY })}
      onMouseMove={(e) => setPos({ x: e.clientX, y: e.clientY })}
      onMouseLeave={() => setPos(null)}
    >
      {pos &&
        createPortal(
          <div className="cell-tooltip" style={{ left: pos.x, top: pos.y }}>
            {lines.map((line, i) => (
              <div key={i}>{line}</div>
            ))}
          </div>,
          document.body,
        )}
    </div>
  );
}
