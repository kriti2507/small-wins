import { useEffect, useRef, useState } from "react";

export interface MenuItem {
  label: string;
  onSelect: () => void;
  danger?: boolean;
}

interface Props {
  // Accessible name for the ⋯ button, e.g. "Actions for Workout".
  label: string;
  items: MenuItem[];
  className?: string;
}

// A small round "⋯" button that opens a short menu. Closes on an outside
// click, Escape, or picking an item. Clicks don't propagate, so it can sit
// on top of a card or tile that is itself a link.
export default function ActionMenu({ label, items, className = "" }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: PointerEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div ref={ref} className={`action-menu${open ? " open" : ""} ${className}`}>
      <button
        type="button"
        className="action-menu-button"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOpen((o) => !o);
        }}
      >
        ⋯
      </button>
      {open && (
        <div className="action-menu-list" role="menu">
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              className={item.danger ? "danger" : ""}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setOpen(false);
                item.onSelect();
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
