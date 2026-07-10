import { useEffect, useState } from "react";
import type { DateRange } from "../types";
import { getTopics, getEntries } from "../api/client";
import { scoreEntries } from "../lib/scoring";
import { isoDate } from "../lib/dates";
import Capsule, { type CapsuleTopicData } from "../components/Capsule";
import AspectGrid from "../components/AspectGrid";
import TopicForm from "../components/TopicForm";
import RangeControls, { type Preset } from "../components/RangeControls";
import { useAuth } from "../auth";

const PRESETS: Preset[] = [
  { key: "7", label: "Last 7 days" },
  { key: "30", label: "Last 30 days" },
  { key: "month", label: "This month" },
  { key: "custom", label: "Custom" },
];

// Range for a preset, inclusive of today.
function presetRange(preset: string): DateRange {
  const today = new Date();
  const end = isoDate(today);
  if (preset === "month") {
    const first = new Date(today.getFullYear(), today.getMonth(), 1);
    return { start: isoDate(first), end };
  }
  const days = parseInt(preset, 10);
  const start = new Date(today);
  start.setDate(start.getDate() - (days - 1));
  return { start: isoDate(start), end };
}

export default function HomePage() {
  const { isAdmin, logout } = useAuth();
  const [topicsData, setTopicsData] = useState<CapsuleTopicData[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [preset, setPreset] = useState("7");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");

  function load() {
    getTopics().then((topics) =>
      Promise.all(
        topics.map((topic, colorIndex) =>
          getEntries(topic.slug).then((entries) => {
            // Score over the topic's full entry set so a box's shade matches
            // the topic page, then index by entry id.
            const scores = scoreEntries(topic, entries);
            const scoreById: Record<number, number> = {};
            entries.forEach((e, i) => (scoreById[e.id] = scores[i]));
            return { topic, colorIndex, entries, scoreById };
          }),
        ),
      ).then(setTopicsData),
    );
  }

  useEffect(() => {
    document.title = "Small Wins";
    load();
  }, []);

  function onPreset(key: string) {
    setPreset(key);
    if (key === "custom" && (!customStart || !customEnd)) {
      const r = presetRange("7");
      setCustomStart(r.start);
      setCustomEnd(r.end);
    }
  }

  const range: DateRange =
    preset === "custom" ? { start: customStart, end: customEnd } : presetRange(preset);

  return (
    <>
      <h1>Small Wins</h1>

      <section className="capsule">
        <div className="capsule-head">
          <h2>Time Capsule</h2>
          <RangeControls
            presets={PRESETS}
            active={preset}
            customStart={customStart}
            customEnd={customEnd}
            onPreset={onPreset}
            onCustomStart={setCustomStart}
            onCustomEnd={setCustomEnd}
          />
        </div>
        <div>
          <Capsule topicsData={topicsData} range={range} />
        </div>
      </section>

      <AspectGrid topicsData={topicsData} onAddMore={() => setShowForm(true)} />

      {showForm && (
        <TopicForm
          onCreated={() => {
            setShowForm(false);
            load();
          }}
          onCancel={() => setShowForm(false)}
        />
      )}

      {isAdmin && (
        <footer className="admin-bar">
          <button type="button" className="linklike" onClick={() => logout()}>
            Log out
          </button>
        </footer>
      )}
    </>
  );
}
