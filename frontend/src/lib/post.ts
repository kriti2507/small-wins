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
