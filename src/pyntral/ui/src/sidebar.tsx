import type { ReactNode } from "react";
import { sidebarHeaders, sidebarFooters } from "virtual:pyntral-extensions";
import type { Schema, SidebarConfig, SidebarRegionProps } from "./types";
import { Brand, hasBrandContent } from "./brand";

export function sidebarConfig(schema: Schema): SidebarConfig {
  return schema.navigation?.sidebar ?? {
    width: 238, minWidth: 238, maxWidth: 420, mobileWidth: 238, resizable: true,
    showIcons: true, iconSize: 16, indent: 9, maxIndentDepth: 5, dashboardIcon: "layout-dashboard",
    header: { title: schema.title, icon: "command", showIcon: true, showTitle: true, showSubtitle: true,
      align: "left", direction: "horizontal", divider: true, iconSize: 24, iconBackground: true, linkToDashboard: true },
    footer: { showUser: true, showAvatar: true, showRoles: true, divider: true },
  };
}

type RegionProps = Omit<SidebarRegionProps, "children">;
export function SidebarHeaderRegion(props: RegionProps) {
  const { config, schema, navigate, themeMode } = props;
  const header = config.header;
  const Custom = config.headerComponent ? sidebarHeaders[config.headerComponent] : undefined;
  let children: ReactNode = null;
  if (header && hasBrandContent(header)) {
    children = <div className={`ra-sidebar-header ${header.divider ? "has-divider" : ""}`}>
      <Brand config={header} themeMode={themeMode}
        onClick={header.linkToDashboard && schema.navigation.showDashboard !== false ? () => navigate("") : undefined}/>
    </div>;
  }
  return Custom ? <Custom {...props}>{children}</Custom> : children;
}

export function SidebarFooterRegion(props: RegionProps) {
  const { config, user } = props;
  const footer = config.footer;
  const Custom = config.footerComponent ? sidebarFooters[config.footerComponent] : undefined;
  const children = footer?.showUser ? <div className={`ra-sidebar-footer ${footer.divider ? "has-divider" : ""}`}>
    <div className="user-card">
      {footer.showAvatar && <div className="user-avatar">{user.username.slice(0, 2).toUpperCase()}</div>}
      <div className="user-name"><strong>{user.display_name || user.username}</strong>
        {footer.showRoles && <span>{user.roles.join(", ") || "Member"}</span>}
      </div>
    </div>
  </div> : null;
  return Custom ? <Custom {...props}>{children}</Custom> : children;
}
