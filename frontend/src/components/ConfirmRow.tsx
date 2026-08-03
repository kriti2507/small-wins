import { useEffect } from "react";

interface Props {
  message: string;
  confirmLabel: string;
  cancelLabel: string;
  busy: boolean;
  busyLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
}

// Inline stand-in for window.confirm: styleable, dismissable with Escape,
// consistent with the rest of the app. Focus goes to the cancel button, not
// the destructive one, so a stray Enter can't confirm by accident.
export default function ConfirmRow({
  message,
  confirmLabel,
  cancelLabel,
  busy,
  busyLabel,
  onConfirm,
  onCancel,
}: Props) {
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onCancel();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onCancel]);

  return (
    <div className="confirm-row" role="alert">
      <p>{message}</p>
      <div className="confirm-actions">
        <button type="button" className="danger" disabled={busy} onClick={onConfirm}>
          {busy ? busyLabel : confirmLabel}
        </button>
        <button type="button" disabled={busy} onClick={onCancel} autoFocus>
          {cancelLabel}
        </button>
      </div>
    </div>
  );
}
