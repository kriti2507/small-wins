import type { CSSProperties, ReactNode } from "react";

// Decorative hand-drawn doodles that drift and bounce off the viewport
// edges. Purely presentational: fixed, non-interactive, static markup —
// all motion lives in CSS (see "Background doodles" in style.css).

type Doodle = {
  path: ReactNode;
  size: number; // px
  durX: number; // seconds per horizontal crossing
  durY: number; // seconds per vertical crossing
  delayX: number; // negative delays scatter starting positions
  delayY: number;
  spin: number; // seconds per full rotation
  filled?: boolean; // solid stamp; line doodles stay stroked
};

const DOODLES: Doodle[] = [
  {
    // Five-point star
    path: <path d="M50 8 61 38 93 39 67 58 76 90 50 71 24 90 33 58 7 39 39 38Z" />,
    size: 64, durX: 53, durY: 41, delayX: -12, delayY: -30, spin: 120, filled: true,
  },
  {
    // Four-point sparkle
    path: (
      <path d="M50 10C53 35 65 47 90 50 65 53 53 65 50 90 47 65 35 53 10 50 35 47 47 35 50 10Z" />
    ),
    size: 44, durX: 37, durY: 29, delayX: -25, delayY: -8, spin: 80, filled: true,
  },
  {
    // Loose circle; filling auto-closes the small gap into a solid blob
    path: (
      <path d="M85 45C88 20 65 8 45 12 20 17 8 40 14 62 20 84 45 94 66 86 80 81 87 68 86 54" />
    ),
    size: 90, durX: 67, durY: 49, delayX: -40, delayY: -15, spin: 160, filled: true,
  },
  {
    // Squiggle
    path: (
      <path d="M10 60C20 35 30 35 40 60 50 85 60 85 70 60 80 35 90 35 95 55" />
    ),
    size: 80, durX: 45, durY: 59, delayX: -5, delayY: -33, spin: 140,
  },
  {
    // Heart
    path: (
      <path d="M50 85C20 60 10 40 22 27 32 17 46 22 50 34 54 22 68 17 78 27 90 40 80 60 50 85Z" />
    ),
    size: 48, durX: 61, durY: 38, delayX: -50, delayY: -22, spin: 110, filled: true,
  },
  {
    // Asterisk
    path: (
      <>
        <path d="M50 15 50 85" />
        <path d="M20 32 80 68" />
        <path d="M80 32 20 68" />
      </>
    ),
    size: 40, durX: 41, durY: 53, delayX: -18, delayY: -44, spin: 95,
  },
  {
    // Spiral
    path: (
      <path d="M50 50C55 45 55 55 48 56 38 58 36 44 46 40 60 35 66 52 56 62 44 73 26 62 28 46 31 26 56 20 70 32" />
    ),
    size: 56, durX: 49, durY: 63, delayX: -34, delayY: -12, spin: 130,
  },
];

export default function BackgroundDoodles() {
  return (
    <div className="doodles" aria-hidden="true">
      {DOODLES.map((d, i) => (
        <div
          key={i}
          className={d.filled ? "doodle-x filled" : "doodle-x"}
          style={
            {
              "--size": `${d.size}px`,
              "--dur-x": `${d.durX}s`,
              "--dur-y": `${d.durY}s`,
              "--delay-x": `${d.delayX}s`,
              "--delay-y": `${d.delayY}s`,
              "--spin": `${d.spin}s`,
            } as CSSProperties
          }
        >
          <div className="doodle-y">
            <svg
              viewBox="0 0 100 100"
              fill={d.filled ? "currentColor" : "none"}
              stroke={d.filled ? "none" : "currentColor"}
              strokeWidth={d.filled ? undefined : 7}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              {d.path}
            </svg>
          </div>
        </div>
      ))}
    </div>
  );
}
