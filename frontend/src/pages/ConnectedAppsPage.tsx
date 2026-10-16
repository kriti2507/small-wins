import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { Grant } from "../types";
import { listGrants, revokeGrant } from "../api/client";
import GrantList from "../components/GrantList";

export default function ConnectedAppsPage() {
  const [grants, setGrants] = useState<Grant[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    document.title = "Connected apps — Small Wins";
    listGrants()
      .then(setGrants)
      .catch((e: Error) => setError(e.message));
  }, []);

  async function revoke(id: number) {
    setBusy(true);
    setError(null);
    try {
      await revokeGrant(id);
      setGrants((gs) => (gs ?? []).filter((g) => g.id !== id));
      setConfirming(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Link className="back" to="/">
        ← Back
      </Link>
      <h1>Connected apps</h1>
      <p className="intro">
        Apps you've connected through MCP (like Claude) can read your entries and
        add or edit them. Revoke one to cut it off right away.
      </p>
      {error && <p className="login-error">{error}</p>}
      {grants && (
        <GrantList
          grants={grants}
          confirming={confirming}
          busy={busy}
          origin={window.location.origin}
          onAsk={setConfirming}
          onConfirm={revoke}
          onCancel={() => {
            setConfirming(null);
            setError(null);
          }}
        />
      )}
    </>
  );
}
