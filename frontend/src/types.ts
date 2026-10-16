// Mirrors the JSON the Flask API returns. Single source of truth for the app.

export type FieldType = "text" | "number" | "pace";
export type Direction = "higher" | "lower" | "none";

export interface Field {
  key: string;
  label: string;
  type: FieldType;
  direction: Direction;
}

export type Layout = "photo-top" | "thumbnail";

export interface Topic {
  slug: string;
  name: string;
  color: string; // palette id, e.g. "green"
  layout: Layout;
  fields: Field[];
}

// A post body is an ordered list of blocks: freeform paragraphs and photos.
export interface TextBlock {
  type: "text";
  text: string;
}

export interface ImageBlock {
  type: "image";
  url: string; // served path, e.g. "/api/images/users/<id>/<hex>.jpg"
}

export type Block = TextBlock | ImageBlock;

// A TipTap/ProseMirror document. Typed structurally so lib code and tests
// don't depend on the editor packages.
export interface DocMark {
  type: string;
  attrs?: Record<string, unknown>;
}

export interface DocNode {
  type: string;
  attrs?: Record<string, unknown>;
  marks?: DocMark[];
  text?: string;
  content?: DocNode[];
}

export interface PostDoc {
  type: "doc";
  content?: DocNode[];
}

export interface Entry {
  id: number;
  date: string; // "YYYY-MM-DD"
  image?: string | null; // served path, e.g. "/api/images/users/<id>/<hex>.jpg"
  body?: PostDoc | Block[]; // TipTap doc; Block[] on legacy entries not yet re-saved
  [fieldKey: string]: string | number | null | undefined | Block[] | PostDoc;
}

export interface DateRange {
  start: string;
  end: string;
}

// One connected MCP app (GET /api/mcp/grants).
export interface Grant {
  id: number;
  client_name: string | null; // what the app calls itself; may be missing
  redirect_host: string; // e.g. "claude.ai", or the whole URI for app schemes
  created_at: string; // ISO timestamp
  last_used_at: string | null; // ISO timestamp; null until the app's first call
}
