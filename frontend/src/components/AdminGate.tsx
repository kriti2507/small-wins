import { useState } from "react";
import type { MouseEvent, ReactNode } from "react";
import { createPortal } from "react-dom";
import { useAuth } from "../auth";

interface Props {
  children: ReactNode;
  // Extra class(es) on the wrapper, e.g. to keep grid layouts intact.
  className?: string;
}

// Wraps an edit affordance. Admins see the children untouched; visitors see
// them dimmed and inert with an instant "Only admin can make changes"
// tooltip. While the auth check is still loading, children are inert but no
// tooltip shows (avoids flashing the message at the admin).
export default function AdminGate({ children, className }: Props) {
  const { isAdmin, loading } = useAuth();
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);

  if (isAdmin) return <>{children}</>;

  const track = (e: MouseEvent<HTMLDivElement>) =>
    !loading && setPos({ x: e.clientX, y: e.clientY });

  return (
    <div
      className={"admin-gate" + (className ? ` ${className}` : "")}
      onMouseEnter={track}
      onMouseMove={track}
      onMouseLeave={() => setPos(null)}
    >
      <div
        className="admin-gate-content"
        ref={(el) => el?.setAttribute("inert", "")}
      >
        {children}
      </div>
      {pos &&
        createPortal(
          <div className="cell-tooltip" style={{ left: pos.x, top: pos.y }}>
            Only admin can make changes
          </div>,
          document.body,
        )}
    </div>
  );
}
