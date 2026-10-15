import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { readJson, httpErrorMessage, uploadImage } from "./client";

vi.mock("../lib/image", () => ({
  prepareImage: vi.fn(),
}));
import { prepareImage } from "../lib/image";

const res = (status: number, body: string, statusText = "") => ({
  ok: status >= 200 && status < 300,
  status,
  statusText,
  text: async () => body,
});

describe("readJson", () => {
  it("returns the parsed body on success", async () => {
    await expect(readJson(res(200, '{"url":"https://cdn/a.jpg"}'))).resolves.toEqual({
      url: "https://cdn/a.jpg",
    });
  });

  it("prefers the API's own error message", async () => {
    await expect(readJson(res(400, '{"error":"Unsupported file type."}'))).rejects.toThrow(
      "Unsupported file type.",
    );
  });

  it("reports Vercel's plain-text 413 by status, not as a parser error", async () => {
    // The exact body that made this surface as:
    //   Unexpected token 'R', "Request En"... is not valid JSON
    const err = (await readJson(res(413, "Request Entity Too Large")).catch(
      (e) => e,
    )) as Error;
    expect(err.message).toBe("That file is too large to upload.");
    expect(err.message).not.toMatch(/JSON/);
  });

  it("reports an HTML error page by status", async () => {
    const err = (await readJson(
      res(500, "<!doctype html>\n<title>500 Internal Server Error</title>", "Internal Server Error"),
    ).catch((e) => e)) as Error;
    expect(err.message).toBe("Request failed (500 Internal Server Error).");
  });

  it("handles an empty body", async () => {
    await expect(readJson(res(502, ""))).rejects.toThrow("Request failed (502).");
    await expect(readJson(res(204, ""))).resolves.toBeNull();
  });

  it("does not mistake a JSON body without an error key for a message", async () => {
    await expect(readJson(res(400, '{"detail":"nope"}'))).rejects.toThrow(
      "Request failed (400).",
    );
  });
});

describe("httpErrorMessage", () => {
  it("explains the statuses a user can act on", () => {
    expect(httpErrorMessage(413)).toMatch(/too large/i);
    expect(httpErrorMessage(401)).toMatch(/sign in again/i);
    expect(httpErrorMessage(403)).not.toMatch(/admin/i);
  });
});

const okJson = (body: unknown) =>
  new Response(JSON.stringify(body), { status: 201, headers: { "Content-Type": "application/json" } });

describe("uploadImage", () => {
  const calls: { url: string; init?: RequestInit }[] = [];
  let thumbStatus = 200;

  beforeEach(() => {
    calls.length = 0;
    thumbStatus = 200;
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url === "/api/uploads/sign") {
        const asked = JSON.parse(String(init?.body));
        return okJson({
          upload_url: "https://s/full",
          url: "/api/images/users/1/a.jpg",
          ...(asked.thumb ? { thumb_upload_url: "https://s/thumb" } : {}),
        });
      }
      if (url === "https://s/thumb") return new Response("", { status: thumbStatus });
      return new Response("", { status: 200 });
    }));
  });
  afterEach(() => vi.unstubAllGlobals());

  const file = new File(["x"], "a.jpg", { type: "image/jpeg" });

  it("uploads the image and its thumbnail with a one-year cache header", async () => {
    vi.mocked(prepareImage).mockResolvedValue({
      blob: new Blob(["full"], { type: "image/jpeg" }),
      ext: "jpg",
      thumb: new Blob(["t"], { type: "image/webp" }),
    });

    await expect(uploadImage(file)).resolves.toEqual({ url: "/api/images/users/1/a.jpg" });

    expect(JSON.parse(String(calls[0].init?.body))).toEqual({ ext: "jpg", thumb: true });
    const full = calls.find((c) => c.url === "https://s/full")!;
    const thumb = calls.find((c) => c.url === "https://s/thumb")!;
    expect(full.init?.headers).toMatchObject({
      "Content-Type": "image/jpeg",
      "cache-control": "max-age=31536000",
    });
    expect(thumb.init?.headers).toMatchObject({
      "Content-Type": "image/webp",
      "cache-control": "max-age=31536000",
    });
  });

  it("succeeds even when the thumbnail upload fails", async () => {
    thumbStatus = 500;
    vi.mocked(prepareImage).mockResolvedValue({
      blob: new Blob(["full"], { type: "image/jpeg" }),
      ext: "jpg",
      thumb: new Blob(["t"], { type: "image/webp" }),
    });
    await expect(uploadImage(file)).resolves.toEqual({ url: "/api/images/users/1/a.jpg" });
  });

  it("asks for no thumbnail when there is none (GIFs)", async () => {
    vi.mocked(prepareImage).mockResolvedValue({
      blob: new Blob(["gif"], { type: "image/gif" }),
      ext: "gif",
      thumb: null,
    });
    await uploadImage(file);
    expect(JSON.parse(String(calls[0].init?.body))).toEqual({ ext: "gif", thumb: false });
    expect(calls.map((c) => c.url)).toEqual(["/api/uploads/sign", "https://s/full"]);
  });
});
