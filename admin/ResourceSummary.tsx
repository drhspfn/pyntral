import { useQuery } from "@tanstack/react-query";
import type { CustomCrudProps } from "@pyntral/types";
import { Card } from "@pyntral/ui";

/** Add a metric without replacing the standard CRUD view or its controls. */
export default function ResourceSummary({ resource, mode, record, loadList }: CustomCrudProps) {
  const summary = useQuery({ queryKey: ["list", resource.id, "slot-summary"],
    queryFn: () => loadList({ limit: 1 }), enabled: mode === "list" });
  return <Card title={mode === "list" ? "Resource overview" : "Record summary"}>
    {mode === "list" ? (summary.error ? "Summary unavailable" : summary.data ? `${summary.data.total} records` : "Loading…")
      : String(record?.[resource.titleField] ?? "Record details")}
  </Card>;
}
