import type { Topic } from "../types";
import { buttonColorFor } from "../lib/palette";
import { chipOrder } from "../lib/quickAdd";
import EntryFields from "./EntryFields";

interface Props {
  topics: Topic[];
  suggestions: string[]; // slugs to offer first
  slug: string | null; // the picked topic; null asks "Which topic?"
  onPick: (slug: string) => void;
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
  preview: string;
  onFile: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onClearFile: () => void;
  onSave: (e: React.FormEvent) => void;
  onDiscard: () => void;
  busy: boolean;
}

// The draft a quick add produced: topic chips (the picked one pressed), then
// that topic's fields to check before saving.
export default function QuickAddCard({
  topics,
  suggestions,
  slug,
  onPick,
  values,
  onChange,
  preview,
  onFile,
  onClearFile,
  onSave,
  onDiscard,
  busy,
}: Props) {
  const topic = topics.find((t) => t.slug === slug) ?? null;
  return (
    <form className="form quick-add-card" onSubmit={onSave}>
      <div className="quick-add-topics" role="group" aria-label="Topic">
        {!topic && <p className="quick-add-ask">Which topic?</p>}
        {chipOrder(topics, suggestions).map((t) => (
          <button
            key={t.slug}
            type="button"
            className={`preset${t.slug === slug ? " active" : ""}`}
            aria-pressed={t.slug === slug}
            style={{ "--topic-color": buttonColorFor(t, topics.indexOf(t)) } as React.CSSProperties}
            onClick={() => onPick(t.slug)}
          >
            {t.name}
          </button>
        ))}
      </div>
      {topic && (
        <EntryFields
          topic={topic}
          values={values}
          onChange={onChange}
          preview={preview}
          onFile={onFile}
          onClearFile={onClearFile}
        />
      )}
      <div className="toolbar">
        {topic && (
          <button type="submit" className="primary" disabled={busy}>
            Save
          </button>
        )}
        <button type="button" onClick={onDiscard}>
          Discard
        </button>
      </div>
    </form>
  );
}
