import { describe, expect, test } from "vitest";
import {
  emptyDoc,
  toDoc,
  hasPost,
  normalize,
  moveBlock,
  removeBlock,
  addText,
  addImage,
} from "./post";
import type { Block, Entry, PostDoc } from "../types";

const text = (t: string): Block => ({ type: "text", text: t });
const image = (u: string): Block => ({ type: "image", url: u });

describe("normalize", () => {
  test("drops empty and whitespace-only text blocks", () => {
    const blocks = [text("hello"), text("   "), text(""), image("/a.jpg")];
    expect(normalize(blocks)).toEqual([text("hello"), image("/a.jpg")]);
  });

  test("preserves order and keeps image blocks", () => {
    const blocks = [image("/a.jpg"), text("mid"), image("/b.jpg")];
    expect(normalize(blocks)).toEqual(blocks);
  });

  test("handles undefined as an empty list", () => {
    expect(normalize(undefined)).toEqual([]);
  });
});

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

describe("moveBlock", () => {
  test("moves a block up, swapping with its predecessor", () => {
    const blocks = [text("a"), text("b"), text("c")];
    expect(moveBlock(blocks, 1, "up")).toEqual([text("b"), text("a"), text("c")]);
  });

  test("moves a block down, swapping with its successor", () => {
    const blocks = [text("a"), text("b"), text("c")];
    expect(moveBlock(blocks, 1, "down")).toEqual([text("a"), text("c"), text("b")]);
  });

  test("is a no-op at the ends", () => {
    const blocks = [text("a"), text("b")];
    expect(moveBlock(blocks, 0, "up")).toEqual(blocks);
    expect(moveBlock(blocks, 1, "down")).toEqual(blocks);
  });

  test("does not mutate the input", () => {
    const blocks = [text("a"), text("b")];
    moveBlock(blocks, 1, "up");
    expect(blocks).toEqual([text("a"), text("b")]);
  });
});

describe("removeBlock", () => {
  test("removes the block at the given index", () => {
    const blocks = [text("a"), text("b"), text("c")];
    expect(removeBlock(blocks, 1)).toEqual([text("a"), text("c")]);
  });

  test("does not mutate the input", () => {
    const blocks = [text("a"), text("b")];
    removeBlock(blocks, 0);
    expect(blocks).toEqual([text("a"), text("b")]);
  });
});

describe("addText", () => {
  test("appends an empty text block", () => {
    expect(addText([image("/a.jpg")])).toEqual([image("/a.jpg"), text("")]);
  });
});

describe("addImage", () => {
  test("appends an image block with the given url", () => {
    expect(addImage([text("a")], "/b.jpg")).toEqual([text("a"), image("/b.jpg")]);
  });
});
