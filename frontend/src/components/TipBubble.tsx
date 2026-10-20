import { useLayoutEffect, useRef, useState } from "react";
import type { CSSProperties, ReactNode, RefObject } from "react";
import { createPortal } from "react-dom";
import { placeBubble, type Placement } from "../lib/tips";

interface CardProps {
  children: ReactNode;
  onDismiss: () => void; // "Got it": this tip only
  onSkipAll: () => void; // "Skip tips": every tip
}

export function TipCard({ children, onDismiss, onSkipAll }: CardProps) {
  return (
    <>
      <div className="tip-body">{children}</div>
      <div className="tip-actions">
        <button type="button" className="tip-skip" onClick={onSkipAll}>
          Skip tips
        </button>
        <button type="button" className="primary" onClick={onDismiss}>
          Got it
        </button>
      </div>
    </>
  );
}

interface Props extends CardProps {
  anchor: RefObject<HTMLElement>;
  label: string; // accessible name for the dialog
}

// A speech bubble pointing at `anchor`. Portaled to <body> with
// position:fixed (like HoverCell's tooltip) so transformed cards can't
// reposition it; re-placed on scroll, resize and layout shifts. It doesn't
// trap focus or dim the page — the app stays usable around it.
export default function TipBubble({ anchor, label, ...card }: Props) {
  const bubble = useRef<HTMLDivElement>(null);
  const [place, setPlace] = useState<Placement | null>(null);

  useLayoutEffect(() => {
    function measure() {
      const a = anchor.current;
      const b = bubble.current;
      if (!a || !b) return;
      setPlace(
        placeBubble(
          a.getBoundingClientRect(),
          { width: b.offsetWidth, height: b.offsetHeight },
          { width: window.innerWidth, height: window.innerHeight },
        ),
      );
    }
    measure();
    const layout = new ResizeObserver(measure);
    layout.observe(document.body);
    window.addEventListener("scroll", measure, true);
    window.addEventListener("resize", measure);
    return () => {
      layout.disconnect();
      window.removeEventListener("scroll", measure, true);
      window.removeEventListener("resize", measure);
    };
  }, [anchor]);

  // Rendered hidden first so it can be measured, then placed.
  const style: CSSProperties = place
    ? ({ top: place.top, left: place.left, "--arrow-x": `${place.arrowX}px` } as CSSProperties)
    : { top: 0, left: 0, visibility: "hidden" };

  return createPortal(
    <div ref={bubble} className={`tip-bubble ${place?.side ?? "below"}`} role="dialog" aria-label={label} style={style}>
      <TipCard {...card} />
    </div>,
    document.body,
  );
}
