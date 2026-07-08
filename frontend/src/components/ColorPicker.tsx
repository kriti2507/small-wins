import { paletteSwatches } from "../lib/palette";

interface Props {
  selected: string | null;
  onSelect: (id: string) => void;
}

// A row of color swatches; the selected one gets a ring.
export default function ColorPicker({ selected, onSelect }: Props) {
  return (
    <div className="swatch-row">
      {paletteSwatches().map(({ id, name, color }) => (
        <button
          key={id}
          type="button"
          className={"swatch" + (selected === id ? " selected" : "")}
          style={{ backgroundColor: color }}
          title={name}
          onClick={() => onSelect(id)}
        />
      ))}
    </div>
  );
}
