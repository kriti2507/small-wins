export interface Preset {
  key: string;
  label: string;
}

interface Props {
  presets: Preset[];
  active: string;
  customStart: string;
  customEnd: string;
  onPreset: (key: string) => void;
  onCustomStart: (value: string) => void;
  onCustomEnd: (value: string) => void;
}

// Preset buttons + a custom date range, shared by the home capsule and the
// topic contribution graph. Purely presentational: the parent owns the active
// preset and computes the actual date range.
export default function RangeControls({
  presets,
  active,
  customStart,
  customEnd,
  onPreset,
  onCustomStart,
  onCustomEnd,
}: Props) {
  return (
    <div className="capsule-controls">
      {presets.map((p) => (
        <button
          key={p.key}
          type="button"
          className={"preset" + (active === p.key ? " active" : "")}
          onClick={() => onPreset(p.key)}
        >
          {p.label}
        </button>
      ))}
      <span className={"custom-range" + (active === "custom" ? "" : " hidden")}>
        <input
          type="date"
          value={customStart}
          onChange={(e) => onCustomStart(e.target.value)}
        />
        <span>→</span>
        <input
          type="date"
          value={customEnd}
          onChange={(e) => onCustomEnd(e.target.value)}
        />
      </span>
    </div>
  );
}
