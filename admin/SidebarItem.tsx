import type { SidebarItemProps } from "@pyntral/types";

/** Keep the accessible navigation button and its default icon/label/indicators. */
export default function SidebarItem({ children, id, type }: SidebarItemProps) {
  return <>{children}{type === "page" && id === "insights" &&
    <small style={{ flex: "none", color: "var(--ra-muted)", fontSize: 10 }}>UI</small>}</>;
}
