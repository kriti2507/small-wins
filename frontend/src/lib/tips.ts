// One-time onboarding tips. The ids are stored on the account (users.tips_seen)
// and must match TIPS in backend/auth.py.
export type TipId = "starter" | "log" | "connect";
export const ALL_TIPS: TipId[] = ["starter", "log", "connect"];

/** Which tip the home page shows, if any: the starter aspects first, then —
 * once something has been logged — connecting an MCP app. */
export function homeTip(seen: string[], topicCount: number, entryCount: number): TipId | null {
  if (topicCount === 0) return null; // not loaded yet
  if (!seen.includes("starter")) return "starter";
  if (!seen.includes("connect") && entryCount > 0) return "connect";
  return null;
}

/** The topic page's tip, hidden while the entry form is open. */
export function topicTip(seen: string[], formOpen: boolean): TipId | null {
  return !formOpen && !seen.includes("log") ? "log" : null;
}

export interface Rect {
  top: number;
  bottom: number;
  left: number;
  width: number;
}
export interface Size {
  width: number;
  height: number;
}
export interface Placement {
  side: "below" | "above";
  top: number;
  left: number;
  arrowX: number; // arrow position from the bubble's left edge
}

const GAP = 12; // between anchor and bubble, room for the arrow
const MARGIN = 8; // from the viewport edge
const ARROW_INSET = 16; // keep the arrow off the rounded corners

/** Where to put a bubble of `bubble` size next to `anchor` (viewport
 * coordinates): below if it fits, else above if that fits, else below. */
export function placeBubble(anchor: Rect, bubble: Size, viewport: Size): Placement {
  const below = anchor.bottom + GAP;
  const above = anchor.top - GAP - bubble.height;
  const fitsBelow = below + bubble.height <= viewport.height - MARGIN;
  const side = fitsBelow || above < MARGIN ? "below" : "above";
  const center = anchor.left + anchor.width / 2;
  const idealLeft = center - bubble.width / 2;
  const maxLeft = Math.max(MARGIN, viewport.width - bubble.width - MARGIN);
  // When the anchor is far enough toward an edge that the bubble itself has
  // to be clamped, point the arrow at the near corner (inset) rather than at
  // the anchor's exact centre — past that point the bubble can't move any
  // closer, so a "precise" centre would drift past where the bubble can go.
  let left: number;
  let arrowX: number;
  if (idealLeft < MARGIN) {
    left = MARGIN;
    arrowX = ARROW_INSET;
  } else if (idealLeft > maxLeft) {
    left = maxLeft;
    arrowX = bubble.width - ARROW_INSET;
  } else {
    left = idealLeft;
    arrowX = bubble.width / 2;
  }
  return { side, top: side === "below" ? below : above, left, arrowX };
}
