import type { CustomFieldProps } from "@pyntral/types";

/** Overrides the list and detail rendering for Order.status. */
export default function OrderStatusBadge({ value }: CustomFieldProps) {
  const status = String(value || "pending");
  const palette: Record<string, [string, string]> = {
    pending: ["#fff4df", "#9c660a"],
    fulfilled: ["#e4f8ed", "#148450"],
    cancelled: ["#fee9eb", "#bb4c55"],
  };
  const [background, color] = palette[status] || ["#edf1f3", "#567"];
  return <span style={{ background, color, borderRadius: 99, padding: "5px 10px", fontSize: 11, fontWeight: 700 }}>
    {status[0]?.toUpperCase() + status.slice(1)}
  </span>;
}
