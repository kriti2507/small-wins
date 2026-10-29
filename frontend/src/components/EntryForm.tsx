import { useState } from "react";
import type { Topic } from "../types";
import { fieldPayload } from "../lib/quickAdd";
import { addEntry, uploadImage } from "../api/client";
import EntryFields from "./EntryFields";

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
    const payload = fieldPayload(topic, values);
    if ("error" in payload) {
      alert(payload.error);
      return;
    }
    const { data } = payload;

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
      <EntryFields
        topic={topic}
        values={values}
        onChange={set}
        preview={preview}
        onFile={handleFile}
        onClearFile={clearFile}
      />
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
