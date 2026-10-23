import { useEffect, useRef, useState } from "react";
import type { Ref } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth";
import ConfirmRow from "./ConfirmRow";

interface Props {
  triggerRef?: Ref<HTMLButtonElement>;
  // Lets a caller (the onboarding tip) know when the menu opens or closes.
  onOpenChange?: (open: boolean) => void;
}

// Avatar pill in the top corner that opens a small account menu. triggerRef
// lets the onboarding tip point at the avatar.
export default function AccountMenu({ triggerRef, onOpenChange }: Props) {
  const { user, logout, deleteAccount } = useAuth();
  const [open, setOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  // Report open/closed so the onboarding tip can hide itself while the menu
  // is open.
  useEffect(() => {
    onOpenChange?.(open);
  }, [open, onOpenChange]);

  function toggle() {
    if (!open) {
      setConfirming(false);
      setError(null);
    }
    setOpen(!open);
  }

  // Close on a click outside the menu or on Escape, unless a delete is
  // underway (its outcome would have nowhere to show).
  useEffect(() => {
    if (!open || deleting) return;
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
  }, [open, deleting]);

  async function onDelete() {
    setDeleting(true);
    setError(null);
    try {
      await deleteAccount(); // signs out, so this menu unmounts
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not delete your account.");
      setDeleting(false);
    }
  }

  return (
    <div className="account" ref={ref}>
      <button
        type="button"
        className="account-trigger"
        aria-label="Account menu"
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={deleting}
        onClick={toggle}
        ref={triggerRef}
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
          {confirming ? (
            <ConfirmRow
              message="Delete your account? All your aspects, entries and images will be gone for good."
              confirmLabel="Delete account"
              cancelLabel="Cancel"
              disabled={deleting}
              busy={deleting}
              busyLabel="Deleting…"
              onConfirm={onDelete}
              onCancel={() => setConfirming(false)}
            />
          ) : (
            <button type="button" role="menuitem" className="danger" onClick={() => setConfirming(true)}>
              Delete account
            </button>
          )}
          {error && <p className="form-error">{error}</p>}
        </div>
      )}
    </div>
  );
}
