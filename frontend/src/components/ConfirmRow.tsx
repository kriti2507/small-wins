import { useEffect } from "react";

interface Props {
  message: string;
  confirmLabel: string;
  cancelLabel: string;
  // Whether the buttons should be inert — true whenever any conflicting
  // operation (save, upload, delete) is in flight.
  disabled: boolean;
  // Whether the destructive action itself is in flight — drives the label.
  // Distinct from `disabled`: a save's upload disables this row without a
  // delete being underway, and the label shouldn't claim otherwise.
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
  disabled,
  busy,
  busyLabel,
  onConfirm,
  onCancel,
}: Props) {
  useEffect(() => {
    // Escape honours `disabled` too, so the keyboard can't back out of a row
    // whose buttons are inert.
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && !disabled) onCancel();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onCancel, disabled]);

  return (
    <div className="confirm-row" role="alert">
      <p>{message}</p>
      <div className="confirm-actions">
        <button type="button" className="danger" disabled={disabled} onClick={onConfirm}>
          {busy ? busyLabel : confirmLabel}
        </button>
        <button type="button" disabled={disabled} onClick={onCancel} autoFocus>
          {cancelLabel}
        </button>
      </div>
    </div>
  );
}
