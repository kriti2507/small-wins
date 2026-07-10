// Square-spiral geometry + reveal timing for the home-page summary graph.
// Pure and deterministic so it can be unit-tested without a DOM. Coordinates
// are integer cell offsets; the component turns them into pixel positions.

export type Coord = [number, number];

// Ulam-style square spiral outward from the center [0,0], in reveal order
// (index 0 = center = oldest entry). First move is +x, then it winds around.
export function spiralCoords(n: number): Coord[] {
  if (n <= 0) return [];
  const pts: Coord[] = [[0, 0]];
  let x = 0;
  let y = 0;
  let dx = 1;
  let dy = 0;
  let leg = 1; // steps per straight run
  let done = 0; // straight runs completed
  let left = 1; // steps left in the current run
  while (pts.length < n) {
    x += dx;
    y += dy;
    pts.push([x, y]);
    left -= 1;
    if (left === 0) {
      const ndx = dy;
      const ndy = -dx; // 90° turn
      dx = ndx;
      dy = ndy;
      done += 1;
      if (done % 2 === 0) leg += 1; // run length grows every two turns
      left = leg;
    }
  }
  return pts;
}

// Number of cells across the spiral's (square) bounding box.
export function spiralSpan(n: number): number {
  const pts = spiralCoords(n);
  if (pts.length === 0) return 0;
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const [x, y] of pts) {
    if (x < minX) minX = x;
    if (x > maxX) maxX = x;
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
  }
  return Math.max(maxX - minX + 1, maxY - minY + 1);
}

// Largest cell size (px) so `span` cells plus gaps fit `availableWidth`,
// clamped to [min, max].
export function cellSizeFor(
  span: number,
  availableWidth: number,
  gap: number,
  min: number,
  max: number,
): number {
  if (span <= 0) return min;
  const raw = Math.floor((availableWidth - (span - 1) * gap) / span);
  return Math.max(min, Math.min(max, raw));
}

// Per-cell reveal delay (ms) so the total draw is ~targetMs, clamped to
// [min, max]. Few entries reveal slowly; many entries reveal fast.
export function revealDelayMs(
  count: number,
  targetMs: number,
  min: number,
  max: number,
): number {
  if (count <= 0) return max;
  return Math.max(min, Math.min(max, Math.round(targetMs / count)));
}
