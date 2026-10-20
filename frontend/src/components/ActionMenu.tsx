import { useEffect, useId, useRef, useState } from "react";

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

// A small round "⋯" button that discloses a short list of actions. Closes on
// an outside click, Escape, losing focus, or picking an item. A card or tile
// is often itself covered by a link; this sits as a sibling stacked above it
// (via z-index), and clicks still stop propagation as a safeguard.
export default function ActionMenu({ label, items, className = "" }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const listId = useId();

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
    <div
      ref={ref}
      className={["action-menu", open && "open", className].filter(Boolean).join(" ")}
      onBlur={(e) => {
        if (!ref.current?.contains(e.relatedTarget as Node)) setOpen(false);
      }}
    >
      <button
        type="button"
        className="action-menu-button"
        aria-label={label}
        aria-expanded={open}
        aria-controls={listId}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOpen((o) => !o);
        }}
      >
        ⋯
      </button>
      {open && (
        <div className="action-menu-list" id={listId}>
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
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
