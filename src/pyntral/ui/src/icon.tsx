import { useSyncExternalStore, type ComponentProps } from "react";
import { CircleHelp } from "lucide-react";
import { DynamicIcon, dynamicIconImports } from "lucide-react/dynamic";
import type { IconSpec, ThemeMode } from "./types";

const names = new Set<string>(Object.keys(dynamicIconImports));
type IconName = ComponentProps<typeof DynamicIcon>["name"];
export interface IconProps {
  icon: IconSpec;
  size?: number;
  width?: number;
  className?: string;
  label?: string;
  fallback?: string;
  themeMode?: ThemeMode;
}
function subscribeTheme(callback: () => void) {
  const observer = new MutationObserver(callback);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => observer.disconnect();
}
function themeSnapshot(): ThemeMode {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}
function safeUrl(src: string | null | undefined): string | undefined {
  if (!src || /[\x00-\x20\\]/.test(src) || src.startsWith("//")) return undefined;
  try {
    const url = new URL(src, document.baseURI);
    return ["http:", "https:"].includes(url.protocol) && !url.username && !url.password ? url.href : undefined;
  } catch { return undefined; }
}
function ImageGlyph({ icon, size, width, className, label, themeMode }: Omit<IconProps, "icon"> & {
  icon: Extract<IconSpec, { kind: "image" }>; size: number;
}) {
  const actual = useSyncExternalStore(subscribeTheme, themeSnapshot, () => "light" as const);
  const mode = themeMode ?? actual;
  const src = safeUrl(icon[mode] ?? icon.src ?? icon.light ?? icon.dark);
  if (!src) return <CircleHelp size={size} className={className} aria-label={label}/>;
  return <img src={src} width={width ?? size} height={size} alt={label ?? ""} className={`ra-icon-image ${className ?? ""}`} />;
}
/** Resolves schema-supplied Lucide names lazily; custom SVG stays in an image context. */
export function Icon({ icon, size = 16, width, className, label, fallback = "circle-help", themeMode }: IconProps) {
  if (icon == null) return null;
  if (typeof icon === "object") {
    if (icon.kind === "image") return <ImageGlyph icon={icon} size={size} width={width} className={className} label={label} themeMode={themeMode}/>;
    return <img src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(icon.svg)}`}
      width={width ?? size} height={size} alt={label ?? ""} className={`ra-icon-image ${className ?? ""}`}/>;
  }
  const name = names.has(icon) ? icon : names.has(fallback) ? fallback : "circle-help";
  return <span className={`ra-icon-slot ${className ?? ""}`} style={{ width: size, height: size }}>
    <DynamicIcon key={name} name={name as IconName} size={size}
      aria-label={label} aria-hidden={label ? undefined : true}/>
  </span>;
}
