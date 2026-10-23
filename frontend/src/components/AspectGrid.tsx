import { useEffect, useState } from "react";
import type { Ref } from "react";
import { Link } from "react-router-dom";
import type { Topic, Entry } from "../types";
import SummaryGraph from "./SummaryGraph";
import TopicForm from "./TopicForm";
import ConfirmRow from "./ConfirmRow";
import ActionMenu from "./ActionMenu";
import { buttonColorFor } from "../lib/palette";
import { deleteTopic } from "../api/client";

interface AspectData {
  topic: Topic;
  colorIndex: number;
  entries: Entry[];
}

interface Props {
  topicsData: AspectData[];
  onAddMore: () => void;
  // Called after a topic is edited or deleted, to reload the grid.
  onChanged: () => void;
  // For the onboarding tip: a ref on the first tile, and whether to keep its
  // ⋯ menu visible (it otherwise appears on hover) while the tip points at it.
  firstTileRef?: Ref<HTMLDivElement>;
  highlightFirst?: boolean;
  // Lets a caller (the onboarding tip) know when a tile is being edited or
  // confirming a delete, so it can stay out of the way.
  onBusyChange?: (busy: boolean) => void;
}

// Grid of per-topic summary boxes plus an "+ Add more" tile. Each box's ⋯
// menu edits it in place or deletes it.
export default function AspectGrid({
  topicsData,
  onAddMore,
  onChanged,
  firstTileRef,
  highlightFirst,
  onBusyChange,
}: Props) {
  const [editing, setEditing] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Report busy-ness (editing a tile or confirming its delete) so the
  // onboarding tip can hide itself while one of these is open.
  useEffect(() => {
    onBusyChange?.(editing !== null || confirming !== null);
  }, [editing, confirming, onBusyChange]);

  function remove(slug: string) {
    setDeleting(true);
    deleteTopic(slug)
      .then(() => {
        setConfirming(null);
        onChanged();
      })
      .catch((err) => alert(err.message || "Could not delete."))
      .finally(() => setDeleting(false));
  }

  return (
    <div className="aspect-grid">
      {topicsData.map(({ topic, colorIndex, entries }, i) => {
        if (editing === topic.slug) {
          return (
            <TopicForm
              key={topic.slug}
              topic={topic}
              entries={entries}
              onSaved={() => {
                setEditing(null);
                onChanged();
              }}
              onCancel={() => setEditing(null)}
            />
          );
        }
        const tint = buttonColorFor(topic, colorIndex);
        const count = entries.length;
        return (
          <div
            className={`aspect-box${highlightFirst && i === 0 ? " tip-target" : ""}`}
            key={topic.slug}
            ref={i === 0 ? firstTileRef : undefined}
          >
            {confirming !== topic.slug && (
              <ActionMenu
                className="corner-menu"
                label={`Actions for ${topic.name}`}
                items={[
                  { label: "Edit", onSelect: () => setEditing(topic.slug) },
                  // The server refuses to delete the last topic (it would be
                  // re-seeded), so don't offer it.
                  ...(topicsData.length > 1
                    ? [{ label: "Delete…", danger: true, onSelect: () => setConfirming(topic.slug) }]
                    : []),
                ]}
              />
            )}
            <h2>{topic.name}</h2>
            <div className="graph">
              <SummaryGraph topic={topic} entries={entries} colorIndex={colorIndex} />
            </div>
            {confirming === topic.slug ? (
              <ConfirmRow
                message={`Delete ${topic.name}${count ? ` and its ${count} ${count === 1 ? "entry" : "entries"}` : ""}? This can't be undone.`}
                confirmLabel="Delete"
                cancelLabel="Keep it"
                disabled={deleting}
                busy={deleting}
                busyLabel="Deleting…"
                onConfirm={() => remove(topic.slug)}
                onCancel={() => setConfirming(null)}
              />
            ) : (
              <Link
                className="btn primary"
                to={`/topic/${topic.slug}`}
                style={{ backgroundColor: tint, borderColor: tint }}
              >
                Learn more
              </Link>
            )}
          </div>
        );
      })}
      <div className="aspect-box add-more" onClick={onAddMore}>
        + Add more
      </div>
    </div>
  );
}
