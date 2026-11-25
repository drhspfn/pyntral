import type { CSSProperties, ReactNode } from "react";

type Length = number | string;
export interface SkeletonProps {
  variant?: "rect" | "text" | "circle";
  width?: Length;
  height?: Length;
  size?: Length;
  radius?: Length;
  animation?: "shimmer" | "pulse" | "none";
  className?: string;
  style?: CSSProperties;
}
/** Decorative placeholder; label the loading region once, not every shape. */
export function Skeleton({ variant = "rect", width, height, size, radius, animation = "shimmer", className = "", style }: SkeletonProps) {
  return <span aria-hidden="true" className={`ra-skeleton ra-skeleton-${variant} ra-skeleton-${animation} ${className}`}
    style={{ width: width ?? size, height: height ?? size, borderRadius: radius, ...style }}/>;
}
export interface SkeletonTextProps extends Omit<SkeletonProps, "variant" | "size"> {
  lines?: number;
  gap?: Length;
  lastWidth?: Length;
}
function count(value: number, max = 30) {
  return Math.min(max, Math.max(0, Number.isFinite(value) ? Math.floor(value) : 0));
}
export function SkeletonText({ lines = 3, gap = 8, lastWidth = "65%", width = "100%", height = 12, ...props }: SkeletonTextProps) {
  const total = count(lines);
  return <span aria-hidden="true" className="ra-skeleton-text-group" style={{ width, gap }}>
    {Array.from({length: total}, (_, i) => <Skeleton key={i} {...props} variant="text" height={height}
      width={i === total - 1 && total > 1 ? lastWidth : "100%"}/>)}
  </span>;
}
export function SkeletonImage({ width = "100%", height, aspectRatio = "16 / 9", ...props }: Omit<SkeletonProps, "variant"> & { aspectRatio?: string | number }) {
  return <Skeleton {...props} width={width} height={height ?? "auto"} variant="rect"
    style={{ aspectRatio, ...props.style }}/>;
}
/** A single accessible loading announcement for arbitrary placeholder layouts. */
export function SkeletonGroup({ children, label = "Loading…", className = "", style }: { children: ReactNode; label?: string; className?: string; style?: CSSProperties }) {
  return <div className={`ra-skeleton-group ${className}`} aria-busy="true" style={style}>
    <span role="status" className="ra-skeleton-status">{label}</span>
    <div aria-hidden="true">{children}</div>
  </div>;
}
export interface SkeletonColumn { key: string; className?: string; width?: Length; variant?: SkeletonProps["variant"] }
/** Table-body rows; callers supply a real table header and an accessible busy state. */
export function SkeletonRows({ columns, rows = 5, animation = "shimmer" }: {
  columns: readonly SkeletonColumn[]; rows?: number; animation?: SkeletonProps["animation"];
}) {
  const cells = columns.length ? columns : [{key:"empty"}];
  return <>{Array.from({length:count(rows)}, (_, row) => <tr key={row} aria-hidden="true" className="ra-skeleton-row">
    {cells.map((column, col) => <td key={column.key} className={column.className}>
      <Skeleton animation={animation} variant={column.variant ?? "text"} width={column.width ?? (col === 0 ? "78%" : "62%")}
        height={column.variant === "circle" ? 18 : 12}/>
    </td>)}
  </tr>)}</>;
}
export function SkeletonFields({ count: fields = 4, columns = 1, label = "Loading record…", editor = false }: {
  count?: number; columns?: 1 | 2; label?: string; editor?: boolean;
}) {
  return <SkeletonGroup label={label} className="surface ra-skeleton-fields">
    <div className={`ra-skeleton-field-grid ra-skeleton-field-grid-${columns}`}>
      {Array.from({length:count(fields, 16)}, (_, i) => <div key={i}>
        <Skeleton variant="text" width="35%" height={10}/>
        <Skeleton width={editor ? "100%" : "70%"} height={editor ? 36 : 15}/>
      </div>)}
    </div>
  </SkeletonGroup>;
}
