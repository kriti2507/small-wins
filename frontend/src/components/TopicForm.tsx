import { useState } from "react";
import ColorPicker from "./ColorPicker";
import { PALETTE_ORDER } from "../lib/palette";
import { addTopic, updateTopic } from "../api/client";
import type { Topic } from "../types";

interface FieldRow {
  label: string;
  type: string;
  direction: string;
}

interface Props {
  // Present when editing an existing topic. Its fields aren't editable here:
  // entries store values by field key, so changing them could orphan data.
  topic?: Topic;
  onSaved: () => void;
  onCancel: () => void;
}

const emptyRow = (): FieldRow => ({ label: "", type: "number", direction: "higher" });

// Create-topic form: name, color, and a list of field definitions. With a
// `topic`, edits that topic's name, color, and layout instead.
export default function TopicForm({ topic, onSaved, onCancel }: Props) {
  const [name, setName] = useState(topic?.name ?? "");
  const [color, setColor] = useState<string>(topic?.color ?? PALETTE_ORDER[0]);
  const [layout, setLayout] = useState<string>(topic?.layout ?? "photo-top");
  const [rows, setRows] = useState<FieldRow[]>([emptyRow()]);

  function updateRow(i: number, patch: Partial<FieldRow>) {
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  }

  function changeType(i: number, type: string) {
    // Text fields cannot be scored.
    updateRow(i, type === "text" ? { type, direction: "none" } : { type });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (topic) {
      updateTopic(topic.slug, { name, color, layout })
        .then(onSaved)
        .catch((err) => alert(err.message || "Error"));
      return;
    }
    const fields = rows
      .map((r) => ({ label: r.label.trim(), type: r.type, direction: r.direction }))
      .filter((f) => f.label);

    addTopic({ name, color, layout, fields })
      .then(() => {
        setName("");
        setColor(PALETTE_ORDER[0]);
        setLayout("photo-top");
        setRows([emptyRow()]);
        onSaved();
      })
      .catch((err) => alert(err.message || "Error"));
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <h2>{topic ? "Edit aspect" : "New aspect"}</h2>
      <label>
        Name
        <input
          type="text"
          name="name"
          placeholder="Hikes"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </label>

      <div className="color-field">
        <span className="color-field-label">Color</span>
        <ColorPicker selected={color} onSelect={setColor} />
      </div>

      <label>
        Tile layout
        <select value={layout} onChange={(e) => setLayout(e.target.value)}>
          <option value="photo-top">Photo on top</option>
          <option value="thumbnail">Side thumbnail</option>
        </select>
      </label>

      {!topic && (
        <>
          <div>
            {rows.map((row, i) => (
              <div className="field-row" key={i}>
                <input
                  type="text"
                  placeholder="Field label (e.g. Distance)"
                  className="f-label"
                  value={row.label}
                  onChange={(e) => updateRow(i, { label: e.target.value })}
                />
                <select
                  className="f-type"
                  value={row.type}
                  onChange={(e) => changeType(i, e.target.value)}
                >
                  <option value="number">number</option>
                  <option value="text">text</option>
                  <option value="pace">pace</option>
                </select>
                <select
                  className="f-dir"
                  value={row.direction}
                  disabled={row.type === "text"}
                  onChange={(e) => updateRow(i, { direction: e.target.value })}
                >
                  <option value="higher">higher is better</option>
                  <option value="lower">lower is better</option>
                  <option value="none">not scored</option>
                </select>
                <button
                  type="button"
                  className="f-remove"
                  onClick={() => setRows((rs) => rs.filter((_, j) => j !== i))}
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
          <button type="button" onClick={() => setRows((rs) => [...rs, emptyRow()])}>
            + Add field
          </button>
        </>
      )}

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
