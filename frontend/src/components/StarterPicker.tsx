import { useState, type CSSProperties } from "react";
import { addTopic } from "../api/client";
import { PALETTES } from "../lib/palette";
import { MAX_STARTERS, STARTER_TOPICS, createStarters, toggleStarter } from "../lib/starterTopics";

// A new account's first screen: pick 1–3 topics to start with. Already-created
// topics stay if a later one fails, and onDone reloads the home page.
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

  return (
    <section className="starter-picker">
      <h2>What do you want to track?</h2>
      <p className="starter-hint">
        Pick up to 3 to start. You can add more and customize everything later.
      </p>
      <div className="starter-grid">
        {STARTER_TOPICS.map((t) => {
          const on = selected.includes(t.name);
          const ramp = PALETTES[t.color];
          return (
            <button
              key={t.name}
              type="button"
              className={"starter-card" + (on ? " on" : "")}
              style={{ "--topic-color": ramp[ramp.length - 1], "--topic-tint": ramp[0] } as CSSProperties}
              aria-pressed={on}
              disabled={saving || (full && !on)}
              onClick={() => setSelected(toggleStarter(selected, t.name))}
            >
              {t.name}
            </button>
          );
        })}
      </div>
      {error && <p className="form-error">{error}</p>}
      <button
        type="button"
        className="starter-start"
        disabled={saving || selected.length === 0}
        onClick={start}
      >
        {saving ? "Setting up…" : "Start"}
      </button>
    </section>
  );
}
