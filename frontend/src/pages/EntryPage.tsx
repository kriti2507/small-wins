import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { Topic, Entry, Block } from "../types";
import { getTopics, getEntry, saveEntryBody, uploadImage } from "../api/client";
import { buttonColorFor } from "../lib/palette";
import { tileModel } from "../lib/tile";
import {
  normalize,
  moveBlock,
  removeBlock,
  addText,
  addImage,
} from "../lib/post";

export default function EntryPage() {
  const { slug = "", id = "" } = useParams();
  const entryId = Number(id);
  const [topic, setTopic] = useState<Topic | null>(null);
  const [entry, setEntry] = useState<Entry | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Block[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getTopics().then((topics) => {
      const idx = topics.findIndex((t) => t.slug === slug);
      const found = topics[idx];
      if (!found) {
        setNotFound(true);
        return;
      }
      setTopic(found);
      document.documentElement.style.setProperty(
        "--topic-color",
        buttonColorFor(found, idx),
      );
      getEntry(slug, entryId)
        .then((e) => {
          setEntry(e);
          document.title = `${tileModel(found, e).heading} — Small Wins`;
        })
        .catch(() => setNotFound(true));
    });
    return () => {
      document.documentElement.style.removeProperty("--topic-color");
    };
  }, [slug, entryId]);

  function startEditing() {
    setDraft(Array.isArray(entry?.body) ? entry.body : []);
    setEditing(true);
  }

  function cancelEditing() {
    setEditing(false);
    setDraft([]);
  }

  function onAddPhoto(file: File) {
    uploadImage(file)
      .then(({ url }) => setDraft((d) => addImage(d, url)))
      .catch((err) => alert(err.message || "Could not upload photo."));
  }

  function save() {
    setSaving(true);
    saveEntryBody(slug, entryId, normalize(draft))
      .then((updated) => {
        setEntry(updated);
        setEditing(false);
        setDraft([]);
      })
      .catch((err) => alert(err.message || "Could not save."))
      .finally(() => setSaving(false));
  }

  if (notFound) {
    return (
      <>
        <Link className="back" to={`/topic/${slug}`}>
          ← Back
        </Link>
        <h1>Unknown entry</h1>
      </>
    );
  }

  if (!topic || !entry) return null;

  const t = tileModel(topic, entry);
  const blocks = normalize(entry.body);

  return (
    <>
      <Link className="back" to={`/topic/${slug}`}>
        ← Back
      </Link>
      <div className="post-head">
        <div>
          <h1>{t.heading}</h1>
          <span className="meta">{t.meta}</span>
        </div>
        {!editing && (
          <button className="primary" onClick={startEditing}>
            Edit
          </button>
        )}
      </div>

      {editing ? (
        <PostEditor
          draft={draft}
          saving={saving}
          onChange={setDraft}
          onAddPhoto={onAddPhoto}
          onSave={save}
          onCancel={cancelEditing}
        />
      ) : blocks.length === 0 ? (
        <p className="post-empty">Nothing written yet. Hit Edit to start.</p>
      ) : (
        <article className="post">
          {blocks.map((b, i) =>
            b.type === "text" ? (
              <p key={i} className="post-text">
                {b.text}
              </p>
            ) : (
              <img key={i} className="post-image" src={b.url} alt="" />
            ),
          )}
        </article>
      )}
    </>
  );
}

interface EditorProps {
  draft: Block[];
  saving: boolean;
  onChange: (blocks: Block[]) => void;
  onAddPhoto: (file: File) => void;
  onSave: () => void;
  onCancel: () => void;
}

function PostEditor({
  draft,
  saving,
  onChange,
  onAddPhoto,
  onSave,
  onCancel,
}: EditorProps) {
  return (
    <div className="post-editor">
      {draft.map((b, i) => (
        <div className="block" key={i}>
          <div className="block-controls">
            <button type="button" onClick={() => onChange(moveBlock(draft, i, "up"))} disabled={i === 0}>
              ↑
            </button>
            <button
              type="button"
              onClick={() => onChange(moveBlock(draft, i, "down"))}
              disabled={i === draft.length - 1}
            >
              ↓
            </button>
            <button type="button" onClick={() => onChange(removeBlock(draft, i))}>
              ✕
            </button>
          </div>
          {b.type === "text" ? (
            <textarea
              className="block-text"
              value={b.text}
              placeholder="Write…"
              onChange={(e) => {
                const next = [...draft];
                next[i] = { type: "text", text: e.target.value };
                onChange(next);
              }}
            />
          ) : (
            <img className="block-image" src={b.url} alt="" />
          )}
        </div>
      ))}

      <div className="post-editor-actions">
        <button type="button" onClick={() => onChange(addText(draft))}>
          + Text
        </button>
        <label className="add-photo">
          + Photo
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) onAddPhoto(file);
              e.target.value = "";
            }}
          />
        </label>
        <span className="spacer" />
        <button type="button" onClick={onCancel} disabled={saving}>
          Cancel
        </button>
        <button type="button" className="primary" onClick={onSave} disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </button>
      </div>
    </div>
  );
}
