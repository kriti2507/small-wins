import { describe, it, expect } from "vitest";
import { loginPath, safeNext, googleSignInHref, loginErrorMessage } from "./authPaths";

describe("loginPath", () => {
  it("remembers where you were, encoded", () => {
    expect(loginPath("/topic/runs", "?x=1")).toBe("/login?next=%2Ftopic%2Fruns%3Fx%3D1");
    expect(loginPath("/")).toBe("/login?next=%2F");
  });
});

describe("safeNext", () => {
  it("keeps same-site paths", () => {
    expect(safeNext("/topic/runs/entry/3")).toBe("/topic/runs/entry/3");
  });

  it("replaces anything else with /", () => {
    for (const bad of [null, "", "topic", "//evil.com", "https://evil.com", "/\\evil.com", "/\t/evil.com", "/x\ny"]) {
      expect(safeNext(bad)).toBe("/");
    }
  });
});

describe("googleSignInHref", () => {
  it("points at the backend's Google route with a safe next", () => {
    expect(googleSignInHref("/topic/runs")).toBe("/api/auth/google?next=%2Ftopic%2Fruns");
    expect(googleSignInHref("//evil.com")).toBe("/api/auth/google?next=%2F");
  });
});

describe("loginErrorMessage", () => {
  it("explains the errors the backend sends back", () => {
    expect(loginErrorMessage("unverified")).toBe(
      "This Google account's email isn't verified.",
    );
    expect(loginErrorMessage("failed")).toBe("Sign-in didn't finish. Try again.");
  });

  it("shows nothing for no or unknown codes", () => {
    expect(loginErrorMessage(null)).toBeNull();
    expect(loginErrorMessage("toString")).toBeNull();
  });
});
