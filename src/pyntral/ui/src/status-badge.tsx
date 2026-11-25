import type { BadgeTone } from "./types";
import { statusTone, statusLabel } from "./field-presentation-state";
export interface StatusBadgeProps {
  value: string | number | null | undefined;
  tones?: Readonly<Record<string, BadgeTone>>;
  labels?: Readonly<Record<string, string>>;
  defaultTone?: BadgeTone;
  autoTone?: boolean;
  dot?: boolean;
  className?: string;
}
export function StatusBadge({ value, tones, labels, defaultTone = "neutral", autoTone = true, dot = true, className = "" }: StatusBadgeProps) {
  if (value == null || value === "") return <span className="muted">—</span>;
  const text = String(value);
  const tone = statusTone(text, tones, defaultTone, autoTone);
  return <span className={`ra-badge ra-badge-${tone} ra-status-badge ${className}`}>
    {dot && <span className="ra-status-dot" aria-hidden="true"/>}
    {statusLabel(text, labels)}
  </span>;
}
