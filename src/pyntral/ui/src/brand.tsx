import type { SidebarHeaderConfig, ThemeMode } from "./types";
import { Icon } from "./icon";

export function hasBrandContent(config: SidebarHeaderConfig): boolean {
  return (config.showIcon && config.icon != null) || (config.showTitle && !!config.title)
    || (config.showSubtitle && !!config.subtitle);
}
export interface BrandProps {
  config: SidebarHeaderConfig;
  themeMode?: ThemeMode;
  onClick?: () => void;
  className?: string;
}
/** Shared application brand, usable in the sidebar, sign-in screen and extensions. */
export function Brand({ config, themeMode, onClick, className = "" }: BrandProps) {
  if (!hasBrandContent(config)) return null;
  const content = <>
    {config.showIcon && config.icon != null && <span className={`ra-brand-logo ${config.iconBackground ? "has-background" : ""}`}>
      <Icon icon={config.icon} size={config.iconSize} width={config.logoWidth ?? undefined} themeMode={themeMode}/>
    </span>}
    {((config.showTitle && config.title) || (config.showSubtitle && config.subtitle)) &&
      <span className="ra-brand-text">
        {config.showTitle && config.title && <strong title={config.title}>{config.title}</strong>}
        {config.showSubtitle && config.subtitle && <small title={config.subtitle}>{config.subtitle}</small>}
      </span>}
  </>;
  const classes = `ra-brand align-${config.align} direction-${config.direction} ${className}`;
  return onClick ? <button type="button" className={classes} aria-label={config.title || "Overview"} onClick={onClick}>{content}</button>
    : <div className={classes}>{content}</div>;
}
