// Mirrors the JSON the Flask API returns. Single source of truth for the app.

export type FieldType = "text" | "number" | "pace";
export type Direction = "higher" | "lower" | "none";

export interface Field {
  key: string;
  label: string;
  type: FieldType;
  direction: Direction;
}

export interface Topic {
  slug: string;
  name: string;
  color: string; // palette id, e.g. "green"
  fields: Field[];
}

export interface Entry {
  id: number;
  date: string; // "YYYY-MM-DD"
  [fieldKey: string]: string | number | null;
}

export interface DateRange {
  start: string;
  end: string;
}
