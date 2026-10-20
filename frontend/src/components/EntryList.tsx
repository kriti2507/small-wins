import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { Topic, Entry } from "../types";
import { tileModel } from "../lib/tile";
import { hasPost } from "../lib/post";
import { rampFor } from "../lib/palette";
import { thumbSrc } from "../lib/image";
import { deleteEntry } from "../api/client";
import ConfirmRow from "./ConfirmRow";
import ActionMenu from "./ActionMenu";

interface Props {
  topic: Topic;
  entries: Entry[];
  colorIndex: number;
  onDeleted: () => void;
}

// Entries newest-first, rendered as tiles. Layout follows the topic's setting;
// each tile shows its uploaded photo or a topic-color block with the initial.
// The whole tile links to the entry; its ⋯ menu sits above that link.
export default function EntryList({ topic, entries, colorIndex, onDeleted }: Props) {
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);
  const ordered = [...entries].sort((a, b) => (a.date < b.date ? 1 : -1));
  const layout = topic.layout === "thumbnail" ? "thumbnail" : "photo-top";
  const ramp = rampFor(topic, colorIndex);
  const gradient = `linear-gradient(135deg, ${ramp[1]}, ${ramp[3]})`;

  function remove(id: number) {
    setDeleting(true);
    deleteEntry(topic.slug, id)
      .then(() => {
        setConfirming(null);
        onDeleted();
      })
      .catch((err) => alert(err.message || "Could not delete."))
      .finally(() => setDeleting(false));
  }

  return (
    <div className="tile-grid">
      {ordered.map((entry) => {
        const t = tileModel(topic, entry);
        const href = `/topic/${topic.slug}/entry/${entry.id}`;
        return (
          <div className={`tile ${layout}`} key={entry.id}>
            <Link className="tile-link" to={href} aria-label={t.heading} />
            <ActionMenu
              className="corner-menu"
              label={`Actions for ${t.heading}`}
              items={[
                { label: "Edit", onSelect: () => navigate(`${href}?edit=1`) },
                { label: "Delete…", danger: true, onSelect: () => setConfirming(entry.id) },
              ]}
            />
            <div className="photo" style={{ background: gradient }}>
              <span className="initial">{t.initial}</span>
              {t.image && (
                <img
                  src={thumbSrc(t.image)}
                  alt={t.heading}
                  loading="lazy"
                  decoding="async"
                  onError={(e) => e.currentTarget.remove()}
                />
              )}
              <span className="read-cue">Read →</span>
            </div>
            <div className="body">
              <h4>
                {t.heading}
                {hasPost(entry) && (
                  <span className="post-dot" title="Has a written post">
                    …
                  </span>
                )}
              </h4>
              <span className="meta">{t.meta}</span>
              {confirming === entry.id && (
                <div className="tile-actions">
                  <ConfirmRow
                    message="Delete this entry?"
                    confirmLabel="Delete"
                    cancelLabel="Keep it"
                    disabled={deleting}
                    busy={deleting}
                    busyLabel="Deleting…"
                    onConfirm={() => remove(entry.id)}
                    onCancel={() => setConfirming(null)}
                  />
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
