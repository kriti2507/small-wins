import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import type { Topic, Entry, DateRange } from "../types";
import { getTopics, getEntries, setTopicLayout, deleteTopic } from "../api/client";
import { buttonColorFor } from "../lib/palette";
import { isoDate } from "../lib/dates";
import ContributionGraph from "../components/ContributionGraph";
import EntryForm from "../components/EntryForm";
import EntryList from "../components/EntryList";
import RangeControls, { type Preset } from "../components/RangeControls";
import BackgroundDoodles from "../components/BackgroundDoodles";
import ActionMenu from "../components/ActionMenu";
import ConfirmRow from "../components/ConfirmRow";
import TopicForm from "../components/TopicForm";

const PRESETS: Preset[] = [
  { key: "30", label: "30d" },
  { key: "90", label: "90d" },
  { key: "365", label: "1y" },
  { key: "all", label: "All" },
  { key: "custom", label: "Custom" },
];

export default function TopicPage() {
  const { slug = "" } = useParams();
  const navigate = useNavigate();
  const [topic, setTopic] = useState<Topic | null>(null);
  const [colorIndex, setColorIndex] = useState(0);
  const [notFound, setNotFound] = useState(false);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [preset, setPreset] = useState("all");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const [topicCount, setTopicCount] = useState(0);
  const [editing, setEditing] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  function loadEntries(s: string) {
    getEntries(s).then(setEntries);
  }

  function changeLayout(layout: string) {
    if (!topic || (topic.layout ?? "photo-top") === layout) return;
    setTopicLayout(topic.slug, layout)
      .then((updated) => setTopic(updated))
      .catch((err) => alert(err.message || "Could not change layout."));
  }

  function loadTopic() {
    getTopics().then((topics) => {
      const idx = topics.findIndex((t) => t.slug === slug);
      const found = topics[idx];
      if (!found) {
        setNotFound(true);
        return;
      }
      setTopic(found);
      setColorIndex(idx);
      setTopicCount(topics.length);
      document.title = `${found.name} — Small Wins`;
      document.documentElement.style.setProperty(
        "--topic-color",
        buttonColorFor(found, idx),
      );
      loadEntries(slug);
    });
  }

  useEffect(() => {
    // A slug change reuses this component (same route, different topic), so
    // any edit/delete UI from the previous topic shouldn't carry over.
    setEditing(false);
    setConfirmingDelete(false);
    loadTopic();
    // Reset the topic tint when leaving so the home page uses its default.
    return () => {
      document.documentElement.style.removeProperty("--topic-color");
    };
  }, [slug]);

  function removeTopic() {
    setDeleting(true);
    deleteTopic(slug)
      .then(() => navigate("/"))
      .catch((err) => {
        alert(err.message || "Could not delete.");
        setDeleting(false);
      });
  }

  // Range for a preset, always ending today. "all" spans from the earliest
  // entry; a number spans that many days back (inclusive of today).
  function presetRange(p: string): DateRange {
    const today = new Date();
    const end = isoDate(today);
    if (p === "all") {
      const dates = entries.map((e) => e.date).filter(Boolean).sort();
      return { start: dates.length ? dates[0] : end, end };
    }
    const days = parseInt(p, 10);
    const start = new Date(today);
    start.setDate(start.getDate() - (days - 1));
    return { start: isoDate(start), end };
  }

  function onPreset(key: string) {
    setPreset(key);
    if (key === "custom" && (!customStart || !customEnd)) {
      const r = presetRange("90");
      setCustomStart(r.start);
      setCustomEnd(r.end);
    }
  }

  if (notFound) {
    return (
      <>
        <Link className="back" to="/">
          ← Back
        </Link>
        <h1>Unknown topic</h1>
      </>
    );
  }

  if (!topic) return null;

  const range: DateRange =
    preset === "custom" ? { start: customStart, end: customEnd } : presetRange(preset);

  return (
    <>
      <BackgroundDoodles />
      <Link className="back" to="/">
        ← Back
      </Link>
      {editing ? (
        <TopicForm
          topic={topic}
          entries={entries}
          onSaved={() => {
            setEditing(false);
            loadTopic();
          }}
          onCancel={() => setEditing(false)}
        />
      ) : (
        <div className="topic-head">
          <h1>{topic.name}</h1>
          {!confirmingDelete && (
            <ActionMenu
              label={`Actions for ${topic.name}`}
              items={[
                { label: "Edit aspect", onSelect: () => setEditing(true) },
                // The server refuses to delete the last topic (it would be
                // re-seeded), so don't offer it.
                ...(topicCount > 1
                  ? [{ label: "Delete aspect…", danger: true, onSelect: () => setConfirmingDelete(true) }]
                  : []),
              ]}
            />
          )}
        </div>
      )}
      {confirmingDelete && (
        <ConfirmRow
          message={`Delete ${topic.name}${entries.length ? ` and its ${entries.length} ${entries.length === 1 ? "entry" : "entries"}` : ""}? This can't be undone.`}
          confirmLabel="Delete"
          cancelLabel="Keep it"
          disabled={deleting}
          busy={deleting}
          busyLabel="Deleting…"
          onConfirm={removeTopic}
          onCancel={() => setConfirmingDelete(false)}
        />
      )}

      <div className="summary-box">
        <RangeControls
          presets={PRESETS}
          active={preset}
          customStart={customStart}
          customEnd={customEnd}
          onPreset={onPreset}
          onCustomStart={setCustomStart}
          onCustomEnd={setCustomEnd}
        />
        <div>
          <ContributionGraph
            topic={topic}
            entries={entries}
            colorIndex={colorIndex}
            range={range}
          />
        </div>
      </div>

      <div className="toolbar">
        <button className="primary" onClick={() => setShowForm(true)}>
          + Add entry
        </button>
        <div className="layout-toggle" role="group" aria-label="Tile layout">
          <button
            type="button"
            className={(topic.layout ?? "photo-top") !== "thumbnail" ? "active" : ""}
            onClick={() => changeLayout("photo-top")}
          >
            Photo
          </button>
          <button
            type="button"
            className={topic.layout === "thumbnail" ? "active" : ""}
            onClick={() => changeLayout("thumbnail")}
          >
            Thumbnail
          </button>
        </div>
      </div>

      {showForm && (
        <EntryForm
          topic={topic}
          onAdded={() => {
            setShowForm(false);
            loadEntries(slug);
          }}
          onCancel={() => setShowForm(false)}
        />
      )}

      <EntryList
        topic={topic}
        entries={entries}
        colorIndex={colorIndex}
        onDeleted={() => loadEntries(slug)}
      />
    </>
  );
}
