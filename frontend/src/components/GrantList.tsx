import type { Grant } from "../types";
import ConfirmRow from "./ConfirmRow";
import { appName, connectorUrl, formatDay, lastUsedLabel } from "../lib/grants";

interface Props {
  grants: Grant[];
  confirming: number | null; // id of the row asking "are you sure?"
  busy: boolean; // a revoke is in flight
  origin: string; // this site's origin, for the empty-state connector URL
  onAsk: (id: number) => void;
  onConfirm: (id: number) => void;
  onCancel: () => void;
}

export default function GrantList({ grants, confirming, busy, origin, onAsk, onConfirm, onCancel }: Props) {
  if (grants.length === 0) {
    return (
      <p className="empty">
        No apps are connected. To connect one, add a custom connector in Claude
        (or another MCP app) with the URL <code>{connectorUrl(origin)}</code>.
      </p>
    );
  }
  return (
    <ul className="grant-list">
      {grants.map((g) => (
        <li key={g.id} className="grant">
          <div className="grant-info">
            <strong>{appName(g)}</strong>
            {/* Template strings, not JSX text + expressions: one text node
                each, so server rendering (and the tests) see plain text. */}
            <span className="grant-meta">{`Redirects to ${g.redirect_host}`}</span>
            <span className="grant-meta">
              {`Connected ${formatDay(g.created_at)} · Last used ${lastUsedLabel(g.last_used_at)}`}
            </span>
          </div>
          {confirming === g.id ? (
            <ConfirmRow
              message={`Revoke ${appName(g)}? It stops working until you connect it again.`}
              confirmLabel="Revoke"
              cancelLabel="Keep"
              disabled={busy}
              busy={busy}
              busyLabel="Revoking…"
              onConfirm={() => onConfirm(g.id)}
              onCancel={onCancel}
            />
          ) : (
            <button
              type="button"
              className="danger"
              aria-label={`Revoke ${appName(g)}`}
              disabled={busy || confirming !== null}
              onClick={() => onAsk(g.id)}
            >
              Revoke
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}
