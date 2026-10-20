import { useEffect, useState } from "react";
import { connectorUrl } from "../lib/grants";

// The URL people paste into Claude, ChatGPT etc. to connect Small Wins, with a
// Copy button where the browser allows it (the URL stays selectable anyway).
export default function ConnectorUrl({ origin }: { origin: string }) {
  const [copied, setCopied] = useState(false);
  const url = connectorUrl(origin);
  const canCopy = typeof navigator !== "undefined" && !!navigator.clipboard;

  useEffect(() => {
    if (!copied) return;
    const t = setTimeout(() => setCopied(false), 2000);
    return () => clearTimeout(t);
  }, [copied]);

  function copy() {
    navigator.clipboard.writeText(url).then(() => setCopied(true), () => {});
  }

  return (
    <div className="connector-url">
      <code>{url}</code>
      {canCopy && (
        <button type="button" className="preset" onClick={copy}>
          {copied ? "Copied" : "Copy"}
        </button>
      )}
    </div>
  );
}
