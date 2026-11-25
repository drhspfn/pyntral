import type { CustomFieldProps } from "@pyntral/types";
import { StatusBadge } from "@pyntral/ui";

/** Optional custom renderer; standard Order.status now uses StatusBadgeConfig. */
export default function OrderStatusBadge({ value }: CustomFieldProps) {
  return <StatusBadge value={value == null ? null : String(value)}
    labels={{ pending:"Pending", fulfilled:"Fulfilled", cancelled:"Cancelled" }}/>;
}
