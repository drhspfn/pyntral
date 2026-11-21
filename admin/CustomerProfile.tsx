import { useState } from "react";
import { useAdminFeedback } from "@pyntral/feedback";
import type { CustomActionProps } from "@pyntral/types";

/** A full custom record action page, with the current entity and submit callback. */
export default function CustomerProfile({ record, resource, invoke, navigate }: CustomActionProps) {
  const feedback = useAdminFeedback();
  const [response, setResponse] = useState<unknown>(null);
  const [error, setError] = useState("");
  return <div className="surface" style={{ padding: 22, maxWidth: 560 }}>
    <h2>{String(record.name ?? "Customer")}</h2>
    <p>Email: {String(record.email ?? "—")}</p>
    <p>This page is a React action extension. Its props contain the current record.</p>
    <button className="btn primary" onClick={async () => {
      const accepted = await feedback.confirm({ title: "Load customer profile?",
        message: `Fetch details for ${String(record.name ?? "this customer")}?`,
        confirmLabel: "Fetch profile" });
      if (!accepted) return;
      try { setResponse(await invoke({})); setError(""); }
      catch (reason) {
        const message = reason instanceof Error ? reason.message : "Action failed";
        setError(message);
        feedback.toast(message, { kind: "error" });
      }
    }}>Call Python handler</button>
    {error && <p role="alert">{error}</p>}
    {response != null && <pre>{JSON.stringify(response, null, 2)}</pre>}
    <button className="btn subtle" style={{ marginLeft: 8 }}
      onClick={() => navigate(`resources/${resource.id}`)}>Back to customers</button>
  </div>;
}
