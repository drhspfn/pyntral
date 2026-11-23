import type { SidebarRegionProps } from "@pyntral/types";

/** Example wrapper: retain the configured region and add app-owned content. */
export default function SidebarRegion({ children }: SidebarRegionProps) {
  return <div style={{ minWidth: 0 }}>{children}</div>;
}
