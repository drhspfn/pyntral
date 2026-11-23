import type { CSSProperties, ReactNode } from "react";
import { sidebarHeaders, sidebarFooters } from "virtual:pyntral-extensions";
import type { Schema, SidebarConfig, SidebarRegionProps } from "./types";
import { Icon } from "./icon";
import { OverflowText } from "./overflow-text";

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
  if (header) {
    const hasIcon = header.showIcon && header.icon != null;
    const hasText = (header.showTitle && !!header.title) || (header.showSubtitle && !!header.subtitle);
    if (hasIcon || hasText) {
      const content = <>
        {hasIcon && <div className={`ra-sidebar-logo ${header.iconBackground ? "has-background" : ""}`}
          style={{ "--ra-logo-size": `${header.iconSize}px` } as CSSProperties}>
          <Icon icon={header.icon} size={header.iconSize} width={header.logoWidth ?? undefined} themeMode={themeMode}/>
        </div>}
        {hasText && <div className="ra-sidebar-heading-text">
          {header.showTitle && header.title && <strong><OverflowText>{header.title}</OverflowText></strong>}
          {header.showSubtitle && header.subtitle && <small><OverflowText>{header.subtitle}</OverflowText></small>}
        </div>}
      </>;
      const className = `ra-sidebar-heading align-${header.align} direction-${header.direction}`;
      children = <div className={`ra-sidebar-header ${header.divider ? "has-divider" : ""}`}>
        {header.linkToDashboard && schema.navigation.showDashboard !== false
          ? <button type="button" className={className} aria-label={header.title || "Overview"} onClick={() => navigate("")}>{content}</button>
          : <div className={className}>{content}</div>}
      </div>;
    }
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
