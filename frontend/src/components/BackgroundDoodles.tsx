import type { CSSProperties, ReactNode } from "react";

// Decorative hand-drawn doodles that drift and bounce off the viewport
// edges. Purely presentational: fixed, non-interactive, static markup —
// all motion lives in CSS (see "Background doodles" in style.css).

type Shape = {
  path: ReactNode;
  filled?: boolean; // solid stamp; line doodles stay stroked
};

type Doodle = Shape & {
  size: number; // px
  durX: number; // seconds per horizontal crossing
  durY: number; // seconds per vertical crossing
  delayX: number; // negative delays scatter starting positions
  delayY: number;
  spin: number; // seconds per full rotation
};

const SHAPES: Record<string, Shape> = {
  // Five-point star
  star: {
    filled: true,
    path: <path d="M50 8 61 38 93 39 67 58 76 90 50 71 24 90 33 58 7 39 39 38Z" />,
  },
  // Four-point sparkle
  sparkle: {
    filled: true,
    path: (
      <path d="M50 10C53 35 65 47 90 50 65 53 53 65 50 90 47 65 35 53 10 50 35 47 47 35 50 10Z" />
    ),
  },
  // Loose circle; filling auto-closes the small gap into a solid blob
  circle: {
    filled: true,
    path: (
      <path d="M85 45C88 20 65 8 45 12 20 17 8 40 14 62 20 84 45 94 66 86 80 81 87 68 86 54" />
    ),
  },
  // Squiggle
  squiggle: {
    path: (
      <path d="M10 60C20 35 30 35 40 60 50 85 60 85 70 60 80 35 90 35 95 55" />
    ),
  },
  // Heart
  heart: {
    filled: true,
    path: (
      <path d="M50 85C20 60 10 40 22 27 32 17 46 22 50 34 54 22 68 17 78 27 90 40 80 60 50 85Z" />
    ),
  },
  // Asterisk
  asterisk: {
    path: (
      <>
        <path d="M50 15 50 85" />
        <path d="M20 32 80 68" />
        <path d="M80 32 20 68" />
      </>
    ),
  },
  // Spiral
  spiral: {
    path: (
      <path d="M50 50C55 45 55 55 48 56 38 58 36 44 46 40 60 35 66 52 56 62 44 73 26 62 28 46 31 26 56 20 70 32" />
    ),
  },
};

// Four size/timing variants per shape. Duration pairs are all distinct and
// co-prime-ish so no two doodles ever trace the same bounce path in sync.
const DOODLES: Doodle[] = [
  { ...SHAPES.star, size: 64, durX: 53, durY: 41, delayX: -12, delayY: -30, spin: 120 },
  { ...SHAPES.star, size: 40, durX: 71, durY: 58, delayX: -55, delayY: -18, spin: 105 },
  { ...SHAPES.star, size: 30, durX: 44, durY: 36, delayX: -28, delayY: -61, spin: 88 },
  { ...SHAPES.star, size: 52, durX: 62, durY: 47, delayX: -70, delayY: -9, spin: 135 },
  { ...SHAPES.sparkle, size: 44, durX: 37, durY: 29, delayX: -25, delayY: -8, spin: 80 },
  { ...SHAPES.sparkle, size: 30, durX: 57, durY: 43, delayX: -47, delayY: -26, spin: 95 },
  { ...SHAPES.sparkle, size: 24, durX: 33, durY: 51, delayX: -14, delayY: -39, spin: 72 },
  { ...SHAPES.sparkle, size: 38, durX: 66, durY: 54, delayX: -36, delayY: -52, spin: 115 },
  { ...SHAPES.circle, size: 90, durX: 67, durY: 49, delayX: -40, delayY: -15, spin: 160 },
  { ...SHAPES.circle, size: 60, durX: 51, durY: 63, delayX: -22, delayY: -44, spin: 125 },
  { ...SHAPES.circle, size: 44, durX: 76, durY: 39, delayX: -58, delayY: -31, spin: 142 },
  { ...SHAPES.circle, size: 70, durX: 43, durY: 57, delayX: -8, delayY: -66, spin: 150 },
  { ...SHAPES.squiggle, size: 80, durX: 45, durY: 59, delayX: -5, delayY: -33, spin: 140 },
  { ...SHAPES.squiggle, size: 56, durX: 63, durY: 42, delayX: -49, delayY: -20, spin: 118 },
  { ...SHAPES.squiggle, size: 44, durX: 39, durY: 69, delayX: -27, delayY: -56, spin: 96 },
  { ...SHAPES.squiggle, size: 66, durX: 55, durY: 35, delayX: -64, delayY: -12, spin: 128 },
  { ...SHAPES.heart, size: 48, durX: 61, durY: 38, delayX: -50, delayY: -22, spin: 110 },
  { ...SHAPES.heart, size: 34, durX: 47, durY: 55, delayX: -16, delayY: -42, spin: 92 },
  { ...SHAPES.heart, size: 28, durX: 69, durY: 31, delayX: -34, delayY: -58, spin: 78 },
  { ...SHAPES.heart, size: 42, durX: 41, durY: 64, delayX: -60, delayY: -37, spin: 122 },
  { ...SHAPES.asterisk, size: 40, durX: 41, durY: 53, delayX: -18, delayY: -44, spin: 95 },
  { ...SHAPES.asterisk, size: 28, durX: 59, durY: 37, delayX: -38, delayY: -13, spin: 82 },
  { ...SHAPES.asterisk, size: 24, durX: 35, durY: 61, delayX: -52, delayY: -29, spin: 70 },
  { ...SHAPES.asterisk, size: 34, durX: 73, durY: 46, delayX: -11, delayY: -63, spin: 108 },
  { ...SHAPES.spiral, size: 56, durX: 49, durY: 63, delayX: -34, delayY: -12, spin: 130 },
  { ...SHAPES.spiral, size: 40, durX: 65, durY: 45, delayX: -21, delayY: -48, spin: 112 },
  { ...SHAPES.spiral, size: 32, durX: 37, durY: 57, delayX: -45, delayY: -35, spin: 98 },
  { ...SHAPES.spiral, size: 48, durX: 58, durY: 33, delayX: -68, delayY: -24, spin: 145 },
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
