import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { Topic, Entry, PostDoc } from "../types";
import { getTopics, getEntry, saveEntryBody } from "../api/client";
import { buttonColorFor } from "../lib/palette";
import { tileModel } from "../lib/tile";
import { toDoc, hasPost } from "../lib/post";
import RichPostEditor from "../components/RichPostEditor";
import PostView from "../components/PostView";

export default function EntryPage() {
  const { slug = "", id = "" } = useParams();
  const entryId = Number(id);
  const [topic, setTopic] = useState<Topic | null>(null);
  const [entry, setEntry] = useState<Entry | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  // PostView/RichPostEditor rebuild their TipTap instance when this reference
  // changes, so convert once per entry, not once per render.
  const doc = useMemo(() => toDoc(entry?.body), [entry]);

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

  function save(nextDoc: PostDoc) {
    setSaving(true);
    saveEntryBody(slug, entryId, nextDoc)
      .then((updated) => {
        setEntry(updated);
        setEditing(false);
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

  return (
    <>
      <Link className="back" to={`/topic/${slug}`}>
        ← Back
      </Link>
      <article className="article">
        {entry.image && <img className="article-hero" src={entry.image} alt="" />}
        <div className="post-head">
          <div>
            <h1>{t.heading}</h1>
            <span className="meta">{t.meta}</span>
          </div>
          {!editing && (
            <button className="primary" onClick={() => setEditing(true)}>
              Edit
            </button>
          )}
        </div>

        {editing ? (
          <RichPostEditor
            initial={doc}
            saving={saving}
            onSave={save}
            onCancel={() => setEditing(false)}
          />
        ) : hasPost(entry) ? (
          <PostView doc={doc} />
        ) : (
          <p className="post-empty">Nothing written yet. Hit Edit to start.</p>
        )}
      </article>
    </>
  );
}
