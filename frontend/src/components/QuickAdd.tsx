import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { QuickAddDraft, Topic } from "../types";
import { addEntry, deleteEntry, parseQuickAdd, uploadImage } from "../api/client";
import { isoDate } from "../lib/dates";
import { MAX_TEXT, draftValues, savePayload, titleOf } from "../lib/quickAdd";
import QuickAddCard from "./QuickAddCard";

interface Props {
  topics: Topic[];
  onSaved: () => void;
}

// How long "Logged …" (and its Undo) stays after a save.
const LOGGED_MS = 10000;

// The text as it was sent, with the draft that came back for it.
interface Sent {
  text: string;
  parsed: QuickAddDraft;
}

// What was just saved, enough to undo it back into an open draft.
interface Logged extends Sent {
  topic: Topic;
  id: number;
  values: Record<string, string>;
}

// Home's one-line way to log a win (backend/quick_add.py reads the text).
// A clear win is saved straight away, with Undo; anything ambiguous opens a
// draft card to check first. What was typed becomes the post.
export default function QuickAdd({ topics, onSaved }: Props) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState<Sent | null>(null);
  const [slug, setSlug] = useState<string | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [logged, setLogged] = useState<Logged | null>(null);

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

  /** Save values to topic; throws with a readable message. */
  async function save(topic: Topic, vals: Record<string, string>, sent: Sent, photo: File | null) {
    const payload = savePayload(topic, vals, sent.text);
    if ("error" in payload) throw new Error(payload.error);
    if (photo) payload.data.image = (await uploadImage(photo)).url;
    const entry = await addEntry(topic.slug, payload.data);
    discard();
    setText("");
    setLogged({ ...sent, topic, id: entry.id, values: vals });
    onSaved();
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
      const sent = { text: typed, parsed };
      const topic = topics.find((t) => t.slug === parsed.topic);
      discard();
      if (parsed.clear && topic) {
        await save(topic, draftValues(topic, parsed), sent, null);
      } else {
        setDraft(sent);
        if (topic) pick(topic.slug, parsed);
      }
    } catch (err) {
      setError((err as Error).message || "Could not log that.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    const topic = topics.find((t) => t.slug === slug);
    if (!topic || !draft || busy) return;
    setBusy(true);
    setError("");
    try {
      await save(topic, values, draft, file);
    } catch (err) {
      setError((err as Error).message || "Could not save entry.");
    } finally {
      setBusy(false);
    }
  }

  // Delete what was just saved and reopen it as a draft to fix.
  async function undo() {
    if (!logged || busy) return;
    setBusy(true);
    setError("");
    try {
      await deleteEntry(logged.topic.slug, logged.id);
      setLogged(null);
      setText(logged.text);
      setDraft({ text: logged.text, parsed: logged.parsed });
      setSlug(logged.topic.slug);
      setValues(logged.values);
      onSaved();
    } catch (err) {
      setError((err as Error).message || "Could not undo.");
    } finally {
      setBusy(false);
    }
  }

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    setPreview(f ? URL.createObjectURL(f) : "");
  }

  const loggedTitle = logged ? titleOf(logged.topic, logged.values) : "";

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
          Logged {loggedTitle && <>“{loggedTitle}” </>}to {logged.topic.name} ·{" "}
          <button type="button" className="quick-add-undo" onClick={undo} disabled={busy}>
            Undo
          </button>{" "}
          · <Link to={`/topic/${logged.topic.slug}/entry/${logged.id}`}>View</Link>
        </p>
      )}
    </section>
  );
}
