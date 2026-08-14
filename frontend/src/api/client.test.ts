import { describe, it, expect } from "vitest";
import { readJson, httpErrorMessage } from "./client";

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
    expect(httpErrorMessage(403)).toMatch(/admin/i);
  });
});
