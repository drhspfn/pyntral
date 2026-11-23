import type { SidebarRegionProps } from "@pyntral/types";

/** Add environment context without replacing the configured account footer. */
export default function SidebarFooter({ children }: SidebarRegionProps) {
  return <div style={{ minWidth: 0 }}>
    {children}
    <small style={{ display: "block", padding: "4px 8px", fontSize: 10, color: "var(--ra-muted)" }}>
      Demo environment
    </small>
  </div>;
}
