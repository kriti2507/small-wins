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
  url: string; // served path, e.g. "/api/uploads/ab12.jpg"
}

export type Block = TextBlock | ImageBlock;

export interface Entry {
  id: number;
  date: string; // "YYYY-MM-DD"
  image?: string | null; // served path, e.g. "/api/uploads/ab12.jpg"
  body?: Block[]; // the optional blog-like post
  [fieldKey: string]: string | number | null | undefined | Block[];
}

export interface DateRange {
  start: string;
  end: string;
}
