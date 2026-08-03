import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import type { Topic, Entry } from "../types";
import { getTopics, getEntry, updateEntry, deleteEntry } from "../api/client";
import type { EntryUpdate } from "../api/client";
import { buttonColorFor } from "../lib/palette";
import { tileModel } from "../lib/tile";
import { toDoc, hasPost } from "../lib/post";
import EntryEditor from "../components/EntryEditor";
import PostView from "../components/PostView";
import AdminGate from "../components/AdminGate";
import { useAuth } from "../auth";

export default function EntryPage() {
  const { slug = "", id = "" } = useParams();
  const entryId = Number(id);
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const [topic, setTopic] = useState<Topic | null>(null);
  const [entry, setEntry] = useState<Entry | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // PostView rebuilds its TipTap instance when this reference changes, so
  // convert once per entry, not once per render.
  const doc = useMemo(() => toDoc(entry?.body), [entry]);

  useEffect(() => {
    setEntry(null);
    setEditing(false);
    setNotFound(false);
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

  function save(payload: EntryUpdate) {
    setSaving(true);
    updateEntry(slug, entryId, payload)
      .then((updated) => {
        setEntry(updated);
        setEditing(false);
      })
      .catch((err) => alert(err.message || "Could not save."))
      .finally(() => setSaving(false));
  }

  function remove() {
    setDeleting(true);
    deleteEntry(slug, entryId)
      .then(() => navigate(`/topic/${slug}`, { replace: true }))
      .catch((err) => {
        alert(err.message || "Could not delete.");
        setDeleting(false);
      });
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

  return (
    <>
      <Link className="back" to={`/topic/${slug}`}>
        ← Back
      </Link>
      <article className="article">
        {editing ? (
          <EntryEditor
            key={entry.id}
            topic={topic}
            entry={entry}
            saving={saving}
            onSave={save}
            onCancel={() => setEditing(false)}
            onDelete={remove}
            deleting={deleting}
          />
        ) : (
          <>
            {entry.image && <img className="article-hero" src={entry.image} alt="" />}
            <div className="post-head">
              <div>
                <h1>{t.heading}</h1>
                <span className="meta">{t.meta}</span>
              </div>
              <AdminGate>
                <button className="primary" onClick={() => setEditing(true)}>
                  Edit
                </button>
              </AdminGate>
            </div>
            {hasPost(entry) ? (
              <PostView doc={doc} />
            ) : (
              <p className="post-empty">
                {isAdmin ? "Nothing written yet. Hit Edit to start." : "Nothing written yet."}
              </p>
            )}
          </>
        )}
      </article>
    </>
  );
}
