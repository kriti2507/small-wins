import { describe, it, expect } from "vitest";
import { visitSource, rememberSource, savedSource } from "./source";

const HOST = "small-wins-live.vercel.app";

describe("visitSource", () => {
  it("prefers utm_source, then ?ref=", () => {
    expect(visitSource("?utm_source=twitter&ref=x", "https://t.co/abc", HOST)).toBe("twitter");
    expect(visitSource("?ref=friend", "https://t.co/abc", HOST)).toBe("friend");
  });

  it("falls back to the referring site, without www.", () => {
    expect(visitSource("", "https://www.reddit.com/r/x", HOST)).toBe("reddit.com");
    expect(visitSource("", "https://t.co/abc", HOST)).toBe("t.co");
  });

  it("is direct with no referrer, our own site as referrer, or a junk one", () => {
    expect(visitSource("", "", HOST)).toBe("direct");
    expect(visitSource("", `https://${HOST}/topic/runs`, HOST)).toBe("direct");
    expect(visitSource("", "not a url", HOST)).toBe("direct");
    expect(visitSource("?utm_source=", "", HOST)).toBe("direct");
  });
});

function memoryStorage(): Storage {
  const data = new Map<string, string>();
  return {
    getItem: (k) => data.get(k) ?? null,
    setItem: (k, v) => void data.set(k, v),
    removeItem: (k) => void data.delete(k),
    clear: () => data.clear(),
    key: (i) => [...data.keys()][i] ?? null,
    get length() {
      return data.size;
    },
  };
}

describe("rememberSource", () => {
  it("keeps the first visit's source, not later ones", () => {
    const storage = memoryStorage();
    rememberSource(storage, "?utm_source=twitter", "", HOST);
    rememberSource(storage, "", "https://reddit.com/", HOST);
    expect(savedSource(storage)).toBe("twitter");
  });

  it("never throws when storage is unavailable", () => {
    const broken = { getItem: () => { throw new Error("blocked"); } } as unknown as Storage;
    expect(() => rememberSource(broken, "", "", HOST)).not.toThrow();
    expect(savedSource(broken)).toBeNull();
    expect(() => rememberSource(null, "", "", HOST)).not.toThrow();
    expect(savedSource(null)).toBeNull();
  });
});
