import { describe, expect, test } from "vitest";
import {
  emptyDoc,
  toDoc,
  hasPost,
} from "./post";
import type { Block, Entry, PostDoc } from "../types";

const text = (t: string): Block => ({ type: "text", text: t });
const image = (u: string): Block => ({ type: "image", url: u });

const paragraph = (t: string) => ({
  type: "paragraph",
  content: [{ type: "text", text: t }],
});
const figure = (src: string) => ({
  type: "figure",
  attrs: { src, width: "normal" },
});

describe("toDoc", () => {
  test("turns nothing into an empty doc", () => {
    expect(toDoc(undefined)).toEqual({ type: "doc", content: [] });
    expect(toDoc(null)).toEqual({ type: "doc", content: [] });
  });

  test("passes an existing doc through unchanged", () => {
    const doc: PostDoc = { type: "doc", content: [paragraph("hi")] };
    expect(toDoc(doc)).toBe(doc);
  });

  test("converts legacy text blocks to paragraphs, one per line", () => {
    expect(toDoc([text("line one\nline two")])).toEqual({
      type: "doc",
      content: [paragraph("line one"), paragraph("line two")],
    });
  });

  test("converts legacy image blocks to normal-width figures", () => {
    expect(toDoc([image("/a.jpg")])).toEqual({
      type: "doc",
      content: [figure("/a.jpg")],
    });
  });

  test("drops blank legacy text and keeps order", () => {
    expect(toDoc([text("  "), image("/a.jpg"), text("after")])).toEqual({
      type: "doc",
      content: [figure("/a.jpg"), paragraph("after")],
    });
  });
});

describe("hasPost", () => {
  test("true for a legacy body with a real block", () => {
    const e: Entry = { id: 1, date: "2026-07-08", body: [text("hi")] };
    expect(hasPost(e)).toBe(true);
  });

  test("true for a doc with text or a figure", () => {
    const withText: Entry = {
      id: 1,
      date: "d",
      body: { type: "doc", content: [paragraph("hi")] },
    };
    const withFigure: Entry = {
      id: 1,
      date: "d",
      body: { type: "doc", content: [figure("/a.jpg")] },
    };
    expect(hasPost(withText)).toBe(true);
    expect(hasPost(withFigure)).toBe(true);
  });

  test("false when absent, empty, or only blank content", () => {
    expect(hasPost({ id: 1, date: "d" })).toBe(false);
    expect(hasPost({ id: 1, date: "d", body: [] })).toBe(false);
    expect(hasPost({ id: 1, date: "d", body: [text("  ")] })).toBe(false);
    expect(hasPost({ id: 1, date: "d", body: emptyDoc() })).toBe(false);
    expect(
      hasPost({
        id: 1,
        date: "d",
        body: { type: "doc", content: [{ type: "paragraph" }] },
      }),
    ).toBe(false);
  });
});

