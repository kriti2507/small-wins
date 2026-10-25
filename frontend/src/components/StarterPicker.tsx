import { useState, type CSSProperties } from "react";
import { addTopic } from "../api/client";
import { PALETTES } from "../lib/palette";
import {
  MAX_STARTERS, PREVIEW_DAYS, STARTER_TOPICS, createStarters, previewShades, toggleStarter,
} from "../lib/starterTopics";

// A new account's first screen: pick 1–3 topics from sticky notes, with a
// sample time capsule filling in beside them. Already-created topics stay if a
// later one fails, and onDone reloads the home page.
export default function StarterPicker({
  onDone,
  initialSelected = [],
}: {
  onDone: () => void;
  initialSelected?: string[];
}) {
  const [selected, setSelected] = useState<string[]>(initialSelected);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const full = selected.length >= MAX_STARTERS;
  const picked = STARTER_TOPICS.filter((t) => selected.includes(t.name));

  async function start() {
    setSaving(true);
    setError(null);
    try {
      await createStarters(selected, addTopic);
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSaving(false);
      onDone(); // show whatever was created; the picker stays only if nothing was
    }
  }

  const count =
    selected.length === 0 ? "Nothing picked yet"
    : full ? `${MAX_STARTERS} of ${MAX_STARTERS}, nice picks!`
    : `${selected.length} of ${MAX_STARTERS} picked`;

  return (
    <section className="starter-picker">
      <h2>What do you want to track?</h2>
      <p className="starter-hint">
        Pick up to 3 to start. You can add more and customize everything later.
      </p>
      <div className="starter-layout">
        <div className="starter-notes">
          {STARTER_TOPICS.map((t) => {
            const on = selected.includes(t.name);
            const ramp = PALETTES[t.color];
            return (
              <button
                key={t.name}
                type="button"
                className={"starter-note" + (on ? " on" : "")}
                style={{ "--note-tint": ramp[0], "--note-ink": ramp[4] } as CSSProperties}
                aria-pressed={on}
                disabled={saving || (full && !on)}
                onClick={() => setSelected(toggleStarter(selected, t.name))}
              >
                {on && <span className="starter-circle" aria-hidden="true" />}
                <span className="starter-note-name">{t.name}</span>
                <span className="starter-note-hint">{t.hint}</span>
                <span className="starter-note-icon" aria-hidden="true">{t.icon}</span>
              </button>
            );
          })}
        </div>
        {/* Decorative: shows what the picks will look like once logged. */}
        <div className="starter-preview" aria-hidden="true">
          <h3>Your time capsule will look like…</h3>
          {picked.map((t) => (
            <div key={t.name} className="starter-lane">
              <div className="starter-lane-name">{t.icon} {t.name}</div>
              <div className="starter-boxes">
                {previewShades(t.name).map((s, i) => (
                  <i key={i} style={s < 0 ? undefined : { background: PALETTES[t.color][s] }} />
                ))}
              </div>
            </div>
          ))}
          {!full && (
            <div className="starter-lane open">
              <div className="starter-lane-name">
                {selected.length === 0 ? "Pick a note to see it here" : "+ one more?"}
              </div>
              <div className="starter-boxes">
                {Array.from({ length: PREVIEW_DAYS }, (_, i) => <i key={i} />)}
              </div>
            </div>
          )}
        </div>
      </div>
      {error && <p className="form-error">{error}</p>}
      <div className="starter-actions">
        <button
          type="button"
          className="primary starter-start"
          disabled={saving || selected.length === 0}
          onClick={start}
        >
          {saving ? "Setting up…" : "Start tracking →"}
        </button>
        <span className="starter-count">{count}</span>
      </div>
    </section>
  );
}
