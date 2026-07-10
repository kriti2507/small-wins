import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { Topic, Entry, DateRange } from "../types";
import { getTopics, getEntries, setTopicLayout } from "../api/client";
import { buttonColorFor } from "../lib/palette";
import { isoDate } from "../lib/dates";
import ContributionGraph from "../components/ContributionGraph";
import EntryForm from "../components/EntryForm";
import EntryList from "../components/EntryList";
import RangeControls, { type Preset } from "../components/RangeControls";
import AdminGate from "../components/AdminGate";

const PRESETS: Preset[] = [
  { key: "30", label: "30d" },
  { key: "90", label: "90d" },
  { key: "365", label: "1y" },
  { key: "all", label: "All" },
  { key: "custom", label: "Custom" },
];

export default function TopicPage() {
  const { slug = "" } = useParams();
  const [topic, setTopic] = useState<Topic | null>(null);
  const [colorIndex, setColorIndex] = useState(0);
  const [notFound, setNotFound] = useState(false);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [preset, setPreset] = useState("all");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");

  function loadEntries(s: string) {
    getEntries(s).then(setEntries);
  }

  function changeLayout(layout: string) {
    if (!topic || (topic.layout ?? "photo-top") === layout) return;
    setTopicLayout(topic.slug, layout)
      .then((updated) => setTopic(updated))
      .catch((err) => alert(err.message || "Could not change layout."));
  }

  useEffect(() => {
    getTopics().then((topics) => {
      const idx = topics.findIndex((t) => t.slug === slug);
      const found = topics[idx];
      if (!found) {
        setNotFound(true);
        return;
      }
      setTopic(found);
      setColorIndex(idx);
      document.title = `${found.name} — Small Wins`;
      document.documentElement.style.setProperty(
        "--topic-color",
        buttonColorFor(found, idx),
      );
      loadEntries(slug);
    });
    // Reset the topic tint when leaving so the home page uses its default.
    return () => {
      document.documentElement.style.removeProperty("--topic-color");
    };
  }, [slug]);

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
      <Link className="back" to="/">
        ← Back
      </Link>
      <h1>{topic.name}</h1>

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
        <AdminGate>
          <button className="primary" onClick={() => setShowForm(true)}>
            + Add entry
          </button>
        </AdminGate>
        <AdminGate>
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
        </AdminGate>
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

      <EntryList topic={topic} entries={entries} colorIndex={colorIndex} />
    </>
  );
}
