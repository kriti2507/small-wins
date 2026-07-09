import { useState } from "react";
import ColorPicker from "./ColorPicker";
import { PALETTE_ORDER } from "../lib/palette";
import { addTopic } from "../api/client";

interface FieldRow {
  label: string;
  type: string;
  direction: string;
}

interface Props {
  onCreated: () => void;
  onCancel: () => void;
}

const emptyRow = (): FieldRow => ({ label: "", type: "number", direction: "higher" });

// Create-topic form: name, color, and a list of field definitions.
export default function TopicForm({ onCreated, onCancel }: Props) {
  const [name, setName] = useState("");
  const [color, setColor] = useState<string>(PALETTE_ORDER[0]);
  const [layout, setLayout] = useState("photo-top");
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
    const fields = rows
      .map((r) => ({ label: r.label.trim(), type: r.type, direction: r.direction }))
      .filter((f) => f.label);

    addTopic({ name, color, layout, fields })
      .then(() => {
        setName("");
        setColor(PALETTE_ORDER[0]);
        setLayout("photo-top");
        setRows([emptyRow()]);
        onCreated();
      })
      .catch((err) => alert(err.message || "Error"));
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <h2>New aspect</h2>
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

      <div className="toolbar">
        <button type="submit" className="primary">
          Create
        </button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
