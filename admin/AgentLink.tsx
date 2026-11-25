import type { CustomFieldProps } from "@pyntral/types";
import { Button } from "@pyntral/ui";

export default function AgentLink({ value, navigate }: CustomFieldProps) {
  if (value == null) return <span className="muted">—</span>;
  return <Button variant="ghost" onClick={() => navigate(`resources/agents/${encodeURIComponent(String(value))}`)}>
    Agent #{String(value)}
  </Button>;
}
