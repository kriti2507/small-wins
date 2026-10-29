import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { PostDoc, QuickAddDraft, Topic } from "../types";
import { addEntry, parseQuickAdd, uploadImage } from "../api/client";
import { isoDate } from "../lib/dates";
import { MAX_TEXT, draftValues, fieldPayload, textDoc } from "../lib/quickAdd";
import QuickAddCard from "./QuickAddCard";

interface Props {
  topics: Topic[];
  onSaved: () => void;
}

// How long "Logged to …" stays after a save.
const LOGGED_MS = 6000;

// Home's one-line way to log a win: type it, get a draft filled in from the
// text (backend/quick_add.py), check it, save. What was typed becomes the post.
export default function QuickAdd({ topics, onSaved }: Props) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // The text as it was sent, with the draft that came back for it.
  const [draft, setDraft] = useState<{ text: string; parsed: QuickAddDraft } | null>(null);
  const [slug, setSlug] = useState<string | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [logged, setLogged] = useState<{ topic: Topic; id: number } | null>(null);

  useEffect(() => {
    if (!logged) return;
    const t = setTimeout(() => setLogged(null), LOGGED_MS);
    return () => clearTimeout(t);
  }, [logged]);

  // Switching topics starts from that topic's own draft, so values typed
  // for one topic's fields never land in another's.
  function pick(next: string, parsed: QuickAddDraft) {
    const topic = topics.find((t) => t.slug === next);
    if (!topic) return;
    setSlug(next);
    setValues(draftValues(topic, parsed));
  }

  function clearFile() {
    setFile(null);
    setPreview("");
  }

  function discard() {
    setDraft(null);
    setSlug(null);
    setValues({});
    clearFile();
    setError("");
  }

  async function handleParse(e: React.FormEvent) {
    e.preventDefault();
    const typed = text.trim();
    if (!typed || busy) return;
    setBusy(true);
    setError("");
    setLogged(null);
    try {
      const parsed = await parseQuickAdd(typed, isoDate(new Date()));
      discard();
      setDraft({ text: typed, parsed });
      if (parsed.topic) pick(parsed.topic, parsed);
    } catch (err) {
      setError((err as Error).message || "Could not read that.");
    } finally {
      setBusy(false);
    }
  }

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    setPreview(f ? URL.createObjectURL(f) : "");
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    const topic = topics.find((t) => t.slug === slug);
    if (!topic || !draft || busy) return;
    const payload = fieldPayload(topic, values);
    if ("error" in payload) {
      setError(payload.error);
      return;
    }
    setBusy(true);
    setError("");
    try {
      const data: Record<string, string | number | PostDoc> = { ...payload.data, body: textDoc(draft.text) };
      if (file) data.image = (await uploadImage(file)).url;
      const entry = await addEntry(topic.slug, data);
      discard();
      setText("");
      setLogged({ topic, id: entry.id });
      onSaved();
    } catch (err) {
      setError((err as Error).message || "Could not save entry.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="quick-add">
      <form className="quick-add-bar" onSubmit={handleParse}>
        <input
          type="text"
          aria-label="Log a win"
          placeholder="What's your win today?"
          maxLength={MAX_TEXT}
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={busy && !draft}
        />
        <button type="submit" className="primary" disabled={busy || !text.trim()}>
          {busy && !draft ? "…" : "Add"}
        </button>
      </form>
      {draft && (
        <QuickAddCard
          topics={topics}
          suggestions={draft.parsed.suggestions}
          slug={slug}
          onPick={(s) => pick(s, draft.parsed)}
          values={values}
          onChange={(key, value) => setValues((v) => ({ ...v, [key]: value }))}
          preview={preview}
          onFile={handleFile}
          onClearFile={clearFile}
          onSave={handleSave}
          onDiscard={discard}
          busy={busy}
        />
      )}
      {error && <p className="form-error">{error}</p>}
      {logged && (
        <p className="quick-add-logged" role="status">
          Logged to {logged.topic.name} ·{" "}
          <Link to={`/topic/${logged.topic.slug}/entry/${logged.id}`}>view</Link>
        </p>
      )}
    </section>
  );
}
