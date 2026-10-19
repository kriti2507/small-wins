import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, test } from "vitest";

// "Add to Home Screen" on iOS depends on static files and tags that no
// component touches, so read them from disk and check the wiring directly.
const frontend = (path: string) =>
  fileURLToPath(new URL(`../${path}`, import.meta.url));
const html = readFileSync(frontend("index.html"), "utf8");

// Width and height from a PNG's IHDR chunk.
function pngSize(path: string): [number, number] {
  const bytes = readFileSync(frontend(path));
  expect(bytes.subarray(1, 4).toString("ascii")).toBe("PNG");
  expect(bytes.subarray(12, 16).toString("ascii")).toBe("IHDR");
  return [bytes.readUInt32BE(16), bytes.readUInt32BE(20)];
}

// The opening tag of every `<name ...>` element in index.html, flattened to one
// line, so attribute checks don't depend on attribute order or line wrapping.
function tags(name: string): string[] {
  const found = html.match(new RegExp(`<${name}\\b[^>]*>`, "g")) ?? [];
  return found.map((tag) => tag.replace(/\s+/g, " "));
}

describe("index.html home-screen tags", () => {
  test("links the touch icon, svg favicon and manifest", () => {
    expect(tags("link")).toContainEqual(
      expect.stringMatching(/^(?=.*rel="apple-touch-icon")(?=.*href="\/apple-touch-icon\.png")/),
    );
    expect(tags("link")).toContainEqual(
      expect.stringMatching(
        /^(?=.*rel="icon")(?=.*type="image\/svg\+xml")(?=.*href="\/icon\.svg")/,
      ),
    );
    expect(tags("link")).toContainEqual(
      expect.stringMatching(/^(?=.*rel="manifest")(?=.*href="\/manifest\.webmanifest")/),
    );
  });

  test("the old emoji favicon is gone", () => {
    expect(html).not.toContain("data:image/svg+xml");
  });

  test("opens full-screen, edge to edge (viewport-fit=cover)", () => {
    expect(tags("meta")).toContainEqual(
      expect.stringMatching(/^(?=.*name="apple-mobile-web-app-capable")(?=.*content="yes")/),
    );
    expect(tags("meta")).toContainEqual(
      expect.stringMatching(/^(?=.*name="mobile-web-app-capable")(?=.*content="yes")/),
    );
    expect(tags("meta")).toContainEqual(
      expect.stringMatching(
        /^(?=.*name="apple-mobile-web-app-title")(?=.*content="Small Wins")/,
      ),
    );
    expect(tags("meta")).toContainEqual(
      expect.stringMatching(/^(?=.*name="viewport")(?=.*content="[^"]*viewport-fit=cover)/),
    );
  });
});

describe("manifest", () => {
  const manifest = JSON.parse(
    readFileSync(frontend("public/manifest.webmanifest"), "utf8"),
  );

  test("installs as a standalone app", () => {
    expect(manifest.name).toBe("Small Wins");
    expect(manifest.short_name).toBe("Small Wins");
    expect(manifest.display).toBe("standalone");
    expect(manifest.start_url).toBe("/");
  });

  test("every listed icon exists at its declared size", () => {
    expect(manifest.icons.length).toBeGreaterThan(0);
    for (const icon of manifest.icons) {
      const [w, h] = icon.sizes.split("x").map(Number);
      expect(pngSize(`public${icon.src}`)).toEqual([w, h]);
    }
  });
});

describe("icon files", () => {
  test("the svg source exists", () => {
    expect(existsSync(frontend("public/icon.svg"))).toBe(true);
  });

  test("apple-touch-icon is 180x180", () => {
    expect(pngSize("public/apple-touch-icon.png")).toEqual([180, 180]);
  });
});
