import { useState } from "react";
import type { Topic } from "../types";
import { parsePace } from "../lib/pace";
import { addEntry } from "../api/client";

interface Props {
  topic: Topic;
  onAdded: () => void;
  onCancel: () => void;
}

// Add-entry form: one input per field (pace fields parsed to seconds on save).
export default function EntryForm({ topic, onAdded, onCancel }: Props) {
  const [values, setValues] = useState<Record<string, string>>({});

  function set(key: string, value: string) {
    setValues((v) => ({ ...v, [key]: value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
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

    addEntry(topic.slug, data).then(() => {
      setValues({});
      onAdded();
    });
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
        Date
        <input
          type="date"
          name="date"
          required
          value={values.date ?? ""}
          onChange={(e) => set("date", e.target.value)}
        />
      </label>
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
