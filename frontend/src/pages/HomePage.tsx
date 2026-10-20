import { useEffect, useState } from "react";
import type { DateRange } from "../types";
import { getTopics, getEntries } from "../api/client";
import { scoreEntries } from "../lib/scoring";
import { isoDate } from "../lib/dates";
import Capsule, { type CapsuleTopicData } from "../components/Capsule";
import AspectGrid from "../components/AspectGrid";
import TopicForm from "../components/TopicForm";
import BackgroundDoodles from "../components/BackgroundDoodles";
import AccountMenu from "../components/AccountMenu";
import MonthPicker from "../components/MonthPicker";

// "YYYY-MM" for the month `delta` months away from `month`.
function shiftMonth(month: string, delta: number): string {
  const [y, m] = month.split("-").map(Number);
  return isoDate(new Date(y, m - 1 + delta, 1)).slice(0, 7);
}

// First through last day of a "YYYY-MM" month.
function monthRange(month: string): DateRange {
  const [y, m] = month.split("-").map(Number);
  return { start: `${month}-01`, end: isoDate(new Date(y, m, 0)) };
}

export default function HomePage() {
  const [topicsData, setTopicsData] = useState<CapsuleTopicData[]>([]);
  const [showForm, setShowForm] = useState(false);
  const thisMonth = isoDate(new Date()).slice(0, 7);
  const [month, setMonth] = useState(thisMonth);

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

  return (
    <>
      <BackgroundDoodles />
      <AccountMenu />
      <h1>Small Wins</h1>
      <p className="intro">
        A little diary for the good things. Track the small wins across the
        different parts of your life, and watch each one fill in over time.
      </p>

      <section className="capsule">
        <div className="capsule-head">
          <h2>Time Capsule</h2>
          <div className="capsule-controls">
            <button type="button" className="preset" aria-label="Previous month" onClick={() => setMonth(shiftMonth(month, -1))}>
              ‹
            </button>
            <MonthPicker value={month} onChange={setMonth} thisMonth={thisMonth} />
            <button type="button" className="preset" aria-label="Next month" onClick={() => setMonth(shiftMonth(month, 1))}>
              ›
            </button>
            {month !== thisMonth && (
              <button type="button" className="preset" onClick={() => setMonth(thisMonth)}>
                Today
              </button>
            )}
          </div>
        </div>
        <div>
          <Capsule topicsData={topicsData} range={monthRange(month)} />
        </div>
      </section>

      <AspectGrid
        topicsData={topicsData}
        onAddMore={() => setShowForm(true)}
        onChanged={load}
      />

      {showForm && (
        <TopicForm
          onSaved={() => {
            setShowForm(false);
            load();
          }}
          onCancel={() => setShowForm(false)}
        />
      )}
    </>
  );
}
