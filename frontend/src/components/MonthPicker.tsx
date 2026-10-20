import { useEffect, useRef, useState } from "react";
import { MONTHS } from "../lib/dates";

interface Props {
  value: string; // "YYYY-MM"
  onChange: (month: string) => void;
  thisMonth: string; // "YYYY-MM"
}

// Themed stand-in for <input type="month">: a label button that opens a
// year stepper over a grid of months.
export default function MonthPicker({ value, onChange, thisMonth }: Props) {
  const [y, m] = value.split("-").map(Number);
  const [open, setOpen] = useState(false);
  const [year, setYear] = useState(y);
  const ref = useRef<HTMLDivElement>(null);

  // Close on a click outside the picker or on Escape.
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const label = new Date(y, m - 1, 1).toLocaleString("en", { month: "long", year: "numeric" });

  return (
    <div className="month-picker" ref={ref}>
      <button
        type="button"
        className="month-trigger"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => {
          setYear(y);
          setOpen(!open);
        }}
      >
        {label}
      </button>
      {open && (
        <div className="month-pop" role="dialog" aria-label="Choose month">
          <div className="month-pop-head">
            <button type="button" aria-label="Previous year" onClick={() => setYear(year - 1)}>
              ‹
            </button>
            <span>{year}</span>
            <button type="button" aria-label="Next year" onClick={() => setYear(year + 1)}>
              ›
            </button>
          </div>
          <div className="month-pop-grid">
            {MONTHS.map((name, i) => {
              const key = `${year}-${String(i + 1).padStart(2, "0")}`;
              const cls = [key === value && "selected", key === thisMonth && "current"].filter(Boolean).join(" ");
              return (
                <button
                  key={name}
                  type="button"
                  className={cls}
                  aria-pressed={key === value}
                  onClick={() => {
                    onChange(key);
                    setOpen(false);
                  }}
                >
                  {name}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
