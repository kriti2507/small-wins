import { describe, it, expect } from "vitest";
import { fitWithin, shouldReencode, extFor, MAX_DIM, SKIP_BYTES } from "./image";

const mb = (n: number) => n * 1024 * 1024;

describe("fitWithin", () => {
  it("leaves an image that already fits alone", () => {
    expect(fitWithin(800, 600)).toEqual({ width: 800, height: 600, scaled: false });
  });

  it("treats an image exactly at the limit as fitting", () => {
    expect(fitWithin(MAX_DIM, MAX_DIM).scaled).toBe(false);
  });

  it("scales the longest edge down to the limit, keeping aspect ratio", () => {
    expect(fitWithin(4000, 3000)).toEqual({ width: 2000, height: 1500, scaled: true });
  });

  it("scales by height when the image is portrait", () => {
    expect(fitWithin(3000, 4000)).toEqual({ width: 1500, height: 2000, scaled: true });
  });

  it("never rounds a dimension down to zero", () => {
    const fit = fitWithin(20000, 3);
    expect(fit.width).toBe(2000);
    expect(fit.height).toBe(1);
  });
});

describe("shouldReencode", () => {
  const fits = { width: 800, height: 600, scaled: false };
  const scaled = { width: 2000, height: 1500, scaled: true };

  it("re-encodes anything that had to be scaled down", () => {
    expect(shouldReencode({ type: "image/jpeg", size: 1000 }, scaled)).toBe(true);
  });

  it("re-encodes a small-dimensioned but heavy file", () => {
    expect(shouldReencode({ type: "image/png", size: mb(3) }, fits)).toBe(true);
  });

  it("leaves an already-small image untouched", () => {
    expect(shouldReencode({ type: "image/jpeg", size: 100_000 }, fits)).toBe(false);
  });

  it("leaves a file exactly at the skip threshold untouched", () => {
    expect(shouldReencode({ type: "image/jpeg", size: SKIP_BYTES }, fits)).toBe(false);
  });

  it("never re-encodes a GIF, which canvas would flatten to one frame", () => {
    expect(shouldReencode({ type: "image/gif", size: mb(4) }, scaled)).toBe(false);
  });
});

describe("extFor", () => {
  it("maps the types the backend accepts", () => {
    expect(extFor("image/jpeg")).toBe("jpg");
    expect(extFor("image/png")).toBe("png");
    expect(extFor("image/webp")).toBe("webp");
    expect(extFor("image/gif")).toBe("gif");
  });

  it("ignores codec parameters on the mime type", () => {
    expect(extFor("image/jpeg; charset=binary")).toBe("jpg");
  });

  it("returns empty for types the backend would reject", () => {
    // HEIC is what an iPhone hands over, and the bucket won't take it.
    expect(extFor("image/heic")).toBe("");
    expect(extFor("image/svg+xml")).toBe("");
    expect(extFor("")).toBe("");
  });
});
