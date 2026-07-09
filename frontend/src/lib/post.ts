import type { Block, Entry } from "../types";

// Pure operations over a post body (an ordered list of text/image blocks).
// Kept React-free so the editor's logic is unit-tested in isolation.

// Drop empty/whitespace-only text blocks; keep order and all image blocks.
export function normalize(blocks: Block[] | undefined): Block[] {
  return (blocks ?? []).filter(
    (b) => b.type !== "text" || b.text.trim() !== "",
  );
}

// True when the entry has at least one meaningful block to read.
export function hasPost(entry: Entry): boolean {
  return normalize(entry.body).length > 0;
}

// Move the block at `index` one slot up or down; no-op at the ends.
export function moveBlock(
  blocks: Block[],
  index: number,
  dir: "up" | "down",
): Block[] {
  const target = dir === "up" ? index - 1 : index + 1;
  if (target < 0 || target >= blocks.length) return blocks;
  const next = [...blocks];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

export function removeBlock(blocks: Block[], index: number): Block[] {
  return blocks.filter((_, i) => i !== index);
}

export function addText(blocks: Block[]): Block[] {
  return [...blocks, { type: "text", text: "" }];
}

export function addImage(blocks: Block[], url: string): Block[] {
  return [...blocks, { type: "image", url }];
}
