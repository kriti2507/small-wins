import type { Topic } from "../types";

interface Props {
  topic: Topic;
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
  preview: string; // object URL of a newly-picked file, or ""
  onFile: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onClearFile: () => void;
  existingImage?: string | null; // current saved image (edit only)
  onRemoveExisting?: () => void; // edit only
}

// Shared field/date/photo inputs for the add and edit forms. Pace fields take
// "8'35\"" and are parsed to seconds by the caller on save.
export default function EntryFields({
  topic,
  values,
  onChange,
  preview,
  onFile,
  onClearFile,
  existingImage,
  onRemoveExisting,
}: Props) {
  return (
    <>
      <div>
        {topic.fields.map((f) => (
          <label key={f.key}>
            {f.label}
            {f.type === "pace" ? (
              <input
                type="text"
                placeholder={"8'35\""}
                value={values[f.key] ?? ""}
                onChange={(e) => onChange(f.key, e.target.value)}
              />
            ) : f.type === "number" ? (
              <input
                type="number"
                step="any"
                value={values[f.key] ?? ""}
                onChange={(e) => onChange(f.key, e.target.value)}
              />
            ) : (
              <input
                type="text"
                value={values[f.key] ?? ""}
                onChange={(e) => onChange(f.key, e.target.value)}
              />
            )}
          </label>
        ))}
      </div>
      <label>
        Photo (optional)
        <input type="file" accept="image/*" onChange={onFile} />
      </label>
      {preview ? (
        <div className="photo-preview">
          <img src={preview} alt="preview" />
          <button type="button" onClick={onClearFile}>
            Remove
          </button>
        </div>
      ) : existingImage ? (
        <div className="photo-preview">
          <img src={existingImage} alt="current" />
          <button type="button" onClick={onRemoveExisting}>
            Remove
          </button>
        </div>
      ) : null}
      <label>
        Date
        <input
          type="date"
          name="date"
          required
          value={values.date ?? ""}
          onChange={(e) => onChange("date", e.target.value)}
        />
      </label>
    </>
  );
}
