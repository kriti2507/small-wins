import { useState } from "react";
import ColorPicker from "./ColorPicker";
import ConfirmRow from "./ConfirmRow";
import { PALETTES, PALETTE_ORDER } from "../lib/palette";
import { addTopic, updateTopic } from "../api/client";
import {
  countWithValue,
  emptyRow,
  fieldsPayload,
  moveRow,
  rowsFromTopic,
  type FieldRow,
} from "../lib/fieldRows";
import type { Entry, FieldType, Topic } from "../types";

interface Props {
  // Present when editing an existing topic.
  topic?: Topic;
  // The topic's entries, so removing a field that has values asks first.
  entries?: Entry[];
  onSaved: () => void;
  onCancel: () => void;
}

// Create or edit a topic: name, color, and its ordered fields. An existing
// field's type is locked (its values were stored as that type); remove it and
// add a new one to change it. Nothing is saved until Save. Tile layout isn't
// asked here: new topics get the server's default (photo on top) and it's
// switched on the topic page, which saves it for that topic.
export default function TopicForm({ topic, entries = [], onSaved, onCancel }: Props) {
  const [name, setName] = useState(topic?.name ?? "");
  const [color, setColor] = useState<string>(topic?.color ?? PALETTE_ORDER[0]);
  // Field rows are tinted with the chosen color so each one reads as a block.
  const ramp = PALETTES[color] ?? PALETTES[PALETTE_ORDER[0]];
  const [rows, setRows] = useState<FieldRow[]>(() => (topic ? rowsFromTopic(topic) : [emptyRow()]));
  // Id of the row whose removal is awaiting confirmation. Tracked by id (not
  // index) so reordering the rows doesn't have to disturb it.
  const [confirming, setConfirming] = useState<number | null>(null);

  function updateRow(i: number, patch: Partial<FieldRow>) {
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  }

  function changeType(i: number, type: FieldType) {
    // Text fields cannot be scored.
    updateRow(i, type === "text" ? { type, direction: "none" } : { type });
  }

  function move(i: number, delta: -1 | 1) {
    setRows((rs) => moveRow(rs, i, delta));
  }

  function removeRow(id: number) {
    setConfirming(null);
    setRows((rs) => rs.filter((r) => r.id !== id));
  }

  function askRemove(row: FieldRow) {
    if (row.key !== undefined && countWithValue(entries, row.key) > 0) setConfirming(row.id);
    else removeRow(row.id);
  }

  function removeMessage(row: FieldRow) {
    const n = countWithValue(entries, row.key ?? "");
    const label = row.label.trim() || "this field";
    return n === 1
      ? `Remove ${label}? 1 entry has a value, and it'll be erased when you save.`
      : `Remove ${label}? ${n} entries have a value, and they'll be erased when you save.`;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const fields = fieldsPayload(rows);
    if (topic) {
      if (fields.some((f) => !f.label)) {
        alert("Every field needs a label.");
        return;
      }
      updateTopic(topic.slug, { name, color, fields })
        .then(onSaved)
        .catch((err) => alert(err.message || "Error"));
      return;
    }
    addTopic({ name, color, fields })
      .then(() => {
        setName("");
        setColor(PALETTE_ORDER[0]);
        setRows([emptyRow()]);
        onSaved();
      })
      .catch((err) => alert(err.message || "Error"));
  }

  return (
    <form className="form topic-form" onSubmit={handleSubmit}>
      <h2>{topic ? "Edit aspect" : "New aspect"}</h2>
      <label>
        Name
        <input
          type="text"
          name="name"
          placeholder="Hikes"
          required
          autoFocus={!!topic}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </label>

      <div className="color-field">
        <span className="color-field-label">Color</span>
        <ColorPicker selected={color} onSelect={setColor} />
      </div>

      <div
        className="field-list"
        style={{ "--row-a": ramp[0], "--row-b": ramp[1] } as React.CSSProperties}
      >
        <span className="field-list-label">Fields</span>
        {rows.map((row, i) => {
          const rowName = row.label.trim() || `field ${i + 1}`;
          return confirming === row.id ? (
            <ConfirmRow
              key={row.id}
              message={removeMessage(row)}
              confirmLabel="Remove"
              cancelLabel="Keep"
              disabled={false}
              busy={false}
              busyLabel="Removing…"
              onConfirm={() => removeRow(row.id)}
              onCancel={() => setConfirming(null)}
            />
          ) : (
            <div className="field-row" key={row.id}>
              <div className="f-move">
                <button
                  type="button"
                  aria-label={`Move ${rowName} up`}
                  disabled={i === 0}
                  onClick={() => move(i, -1)}
                >
                  ▲
                </button>
                <button
                  type="button"
                  aria-label={`Move ${rowName} down`}
                  disabled={i === rows.length - 1}
                  onClick={() => move(i, 1)}
                >
                  ▼
                </button>
              </div>
              <input
                type="text"
                placeholder="Field label (e.g. Distance)"
                className="f-label"
                value={row.label}
                onChange={(e) => updateRow(i, { label: e.target.value })}
              />
              {row.key !== undefined ? (
                <span className="f-type-tag" title="A field's type can't change once it exists">
                  {row.type}
                </span>
              ) : (
                <select
                  className="f-type"
                  value={row.type}
                  onChange={(e) => changeType(i, e.target.value as FieldType)}
                >
                  <option value="number">number</option>
                  <option value="text">text</option>
                  <option value="pace">pace</option>
                </select>
              )}
              <select
                className="f-dir"
                value={row.direction}
                disabled={row.type === "text"}
                onChange={(e) => updateRow(i, { direction: e.target.value as FieldRow["direction"] })}
              >
                <option value="higher">higher is better</option>
                <option value="lower">lower is better</option>
                <option value="none">not scored</option>
              </select>
              <button
                type="button"
                className="f-remove"
                aria-label={`Remove ${rowName}`}
                onClick={() => askRemove(row)}
              >
                ✕
              </button>
            </div>
          );
        })}
      </div>
      <button type="button" onClick={() => setRows((rs) => [...rs, emptyRow()])}>
        + Add field
      </button>

      <div className="toolbar">
        <button type="submit" className="primary">
          {topic ? "Save" : "Create"}
        </button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
