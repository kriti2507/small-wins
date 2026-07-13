import { useMemo, useState } from "react";
import { useEditor } from "@tiptap/react";
import type { Topic, Entry, PostDoc } from "../types";
import type { EntryUpdate } from "../api/client";
import { uploadImage } from "../api/client";
import { parsePace, formatPace } from "../lib/pace";
import { postExtensions } from "../lib/tiptap";
import { toDoc } from "../lib/post";
import EntryFields from "./EntryFields";
import PostBody from "./PostBody";

interface Props {
  topic: Topic;
  entry: Entry;
  saving: boolean;
  onSave: (payload: EntryUpdate) => void;
  onCancel: () => void;
}

function initialValues(topic: Topic, entry: Entry): Record<string, string> {
  const v: Record<string, string> = { date: entry.date || "" };
  for (const f of topic.fields) {
    const raw = entry[f.key];
    if (raw == null) v[f.key] = "";
    else if (f.type === "pace") v[f.key] = formatPace(raw as number);
    else v[f.key] = String(raw);
  }
  return v;
}

// Combined edit view: topic fields + date + title image + post body, saved
// together with one Save.
export default function EntryEditor({ topic, entry, saving, onSave, onCancel }: Props) {
  const [values, setValues] = useState<Record<string, string>>(() =>
    initialValues(topic, entry),
  );
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [removeImage, setRemoveImage] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // The editor initializes its content once; the parent mounts EntryEditor with
  // key={entry.id} so switching entries remounts it with fresh content.
  const doc = useMemo(() => toDoc(entry.body), [entry]);
  const editor = useEditor({
    extensions: postExtensions(),
    content: doc,
    autofocus: false,
  });

  function set(key: string, value: string) {
    setValues((v) => ({ ...v, [key]: value }));
  }

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    setPreview(f ? URL.createObjectURL(f) : "");
    if (f) setRemoveImage(false);
  }

  function clearFile() {
    setFile(null);
    setPreview("");
  }

  async function handleSave() {
    setError("");
    const payload: EntryUpdate = {
      date: values.date || "",
      body: editor?.getJSON() as unknown as PostDoc,
    };
    for (const f of topic.fields) {
      const raw = values[f.key] ?? "";
      if (f.type === "pace" && raw) {
        const sec = parsePace(raw);
        if (isNaN(sec)) {
          alert(`${f.label}: use min'sec, e.g. 8'35" or 8:35`);
          return;
        }
        payload[f.key] = sec;
      } else {
        payload[f.key] = raw;
      }
    }
    try {
      setSubmitting(true);
      if (file) {
        const { url } = await uploadImage(file);
        payload.image = url;
      } else if (removeImage) {
        payload.image = null;
      }
      onSave(payload);
    } catch (err) {
      setSubmitting(false);
      setError((err as Error).message || "Could not save entry.");
    }
  }

  return (
    <div className="form">
      <EntryFields
        topic={topic}
        values={values}
        onChange={set}
        preview={preview}
        onFile={handleFile}
        onClearFile={clearFile}
        existingImage={removeImage ? null : entry.image}
        onRemoveExisting={() => setRemoveImage(true)}
      />
      <PostBody editor={editor} onUploadingChange={setUploading} />
      {error && <p className="form-error">{error}</p>}
      <div className="toolbar">
        <button
          type="button"
          className="primary"
          disabled={saving || uploading || submitting}
          onClick={handleSave}
        >
          {saving ? "Saving…" : uploading ? "Uploading…" : "Save"}
        </button>
        <button type="button" onClick={onCancel} disabled={saving}>
          Cancel
        </button>
      </div>
    </div>
  );
}
