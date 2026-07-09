import { useState } from "react";
import type { Topic } from "../types";
import { parsePace } from "../lib/pace";
import { addEntry, uploadImage } from "../api/client";

interface Props {
  topic: Topic;
  onAdded: () => void;
  onCancel: () => void;
}

// Add-entry form: one input per field (pace fields parsed to seconds on save).
export default function EntryForm({ topic, onAdded, onCancel }: Props) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [error, setError] = useState("");

  function set(key: string, value: string) {
    setValues((v) => ({ ...v, [key]: value }));
  }

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    setPreview(f ? URL.createObjectURL(f) : "");
  }

  function clearFile() {
    setFile(null);
    setPreview("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const data: Record<string, string | number> = { date: values.date || "" };
    for (const f of topic.fields) {
      const raw = values[f.key] ?? "";
      if (f.type === "pace" && raw) {
        const sec = parsePace(raw);
        if (isNaN(sec)) {
          alert(`${f.label}: use min'sec, e.g. 8'35" or 8:35`);
          return;
        }
        data[f.key] = sec;
      } else {
        data[f.key] = raw;
      }
    }

    try {
      if (file) {
        const { url } = await uploadImage(file);
        data.image = url;
      }
      await addEntry(topic.slug, data);
      setValues({});
      clearFile();
      onAdded();
    } catch (err) {
      setError((err as Error).message || "Could not save entry.");
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <div>
        {topic.fields.map((f) => (
          <label key={f.key}>
            {f.label}
            {f.type === "pace" ? (
              <input
                type="text"
                placeholder={"8'35\""}
                value={values[f.key] ?? ""}
                onChange={(e) => set(f.key, e.target.value)}
              />
            ) : f.type === "number" ? (
              <input
                type="number"
                step="any"
                value={values[f.key] ?? ""}
                onChange={(e) => set(f.key, e.target.value)}
              />
            ) : (
              <input
                type="text"
                value={values[f.key] ?? ""}
                onChange={(e) => set(f.key, e.target.value)}
              />
            )}
          </label>
        ))}
      </div>
      <label>
        Photo (optional)
        <input type="file" accept="image/*" onChange={handleFile} />
      </label>
      {preview && (
        <div className="photo-preview">
          <img src={preview} alt="preview" />
          <button type="button" onClick={clearFile}>
            Remove
          </button>
        </div>
      )}
      <label>
        Date
        <input
          type="date"
          name="date"
          required
          value={values.date ?? ""}
          onChange={(e) => set("date", e.target.value)}
        />
      </label>
      {error && <p className="form-error">{error}</p>}
      <div className="toolbar">
        <button type="submit" className="primary">
          Save
        </button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
