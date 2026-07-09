import type { Block, DocNode, Entry, PostDoc } from "../types";

// Pure helpers for post bodies. New bodies are TipTap docs; legacy bodies are
// Block[] lists that get converted on load and re-saved as docs.

export function emptyDoc(): PostDoc {
  return { type: "doc", content: [] };
}

function paragraph(text: string): DocNode {
  return { type: "paragraph", content: [{ type: "text", text }] };
}

// Convert a legacy Block[] body into a TipTap doc; docs pass through as-is.
export function toDoc(body: PostDoc | Block[] | undefined | null): PostDoc {
  if (!body) return emptyDoc();
  if (!Array.isArray(body)) return body;
  const content: DocNode[] = [];
  for (const b of body) {
    if (b.type === "image") {
      content.push({ type: "figure", attrs: { src: b.url, width: "normal" } });
    } else {
      for (const line of b.text.split("\n")) {
        if (line.trim() !== "") content.push(paragraph(line.trim()));
      }
    }
  }
  return { type: "doc", content };
}

function nodeHasContent(node: DocNode): boolean {
  if (node.type === "figure") return true;
  if (typeof node.text === "string") return node.text.trim() !== "";
  return (node.content ?? []).some(nodeHasContent);
}

// True when the entry has something worth reading (any text or image).
export function hasPost(entry: Entry): boolean {
  return (toDoc(entry.body).content ?? []).some(nodeHasContent);
}

// Drop empty/whitespace-only text blocks; keep order and all image blocks.
export function normalize(blocks: Block[] | PostDoc | undefined): Block[] {
  if (!blocks || !Array.isArray(blocks)) return [];
  return blocks.filter(
    (b) => b.type !== "text" || b.text.trim() !== "",
  );
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
