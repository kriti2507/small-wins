import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth";

// Avatar pill in the top corner that opens a small account menu.
export default function AccountMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on a click outside the menu or on Escape.
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

  return (
    <div className="account" ref={ref}>
      <button
        type="button"
        className="account-trigger"
        aria-label="Account menu"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        {user?.avatar_url ? (
          <img className="account-avatar" src={user.avatar_url} alt="" referrerPolicy="no-referrer" />
        ) : (
          <span className="account-avatar account-initial">{(user?.name || user?.email || "?")[0].toUpperCase()}</span>
        )}
        <span className="account-chevron" aria-hidden="true">▾</span>
      </button>
      {open && (
        <div className="account-menu" role="menu">
          {user?.email && <p className="account-email">{user.email}</p>}
          <Link to="/apps" role="menuitem">Connected apps</Link>
          <a href="/api/export.csv" role="menuitem" download>Export CSV</a>
          <button type="button" role="menuitem" onClick={() => logout()}>
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
