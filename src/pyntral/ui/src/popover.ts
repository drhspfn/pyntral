/** Viewport-aware overlays shared by Select and DatePicker.
 * Panels are portalled to document.body to escape card clipping/stacking contexts.
 */
import { useLayoutEffect, useState, type CSSProperties, type RefObject } from "react";

export interface PopupOptions {
  width?: "anchor" | number;
  align?: "start" | "end";
  minHeight?: number;
  preferredHeight?: number;
  gap?: number;
}

export function computePopupPlacement(
  rect: Pick<DOMRect, "top" | "bottom" | "left" | "width">,
  viewport: { width: number; height: number },
  measuredHeight: number,
  options: PopupOptions = {},
): CSSProperties {
  const margin = 12;
  const gap = options.gap ?? 5;
  const width = Math.min(viewport.width - margin * 2, options.width === "anchor" || options.width == null
    ? rect.width : options.width);
  const below = Math.max(0, viewport.height - margin - rect.bottom - gap);
  const above = Math.max(0, rect.top - margin - gap);
  const desired = Math.max(1, Math.min(options.preferredHeight ?? 320, measuredHeight));
  const minimum = options.minHeight ?? 180;
  // Prefer the side with sufficient room for the minimum; otherwise choose the roomier side.
  const placeAbove = below < Math.min(desired, minimum) && above > below;
  const room = placeAbove ? above : below;
  const height = Math.max(0, Math.min(desired, room));
  const top = placeAbove ? rect.top - gap - height : rect.bottom + gap;
  const anchorLeft = options.align === "end" ? rect.left + rect.width - width : rect.left;
  const left = Math.max(margin, Math.min(anchorLeft, viewport.width - margin - width));
  return { position: "fixed", top, left, width, maxHeight: Math.max(0, room),
    overflowY: "auto", zIndex: 1100 };
}

export function usePopupPosition(
  open: boolean,
  anchor: RefObject<HTMLElement | null>,
  panel: RefObject<HTMLElement | null>,
  options: PopupOptions = {},
): CSSProperties {
  const [style, setStyle] = useState<CSSProperties>({ position: "fixed", visibility: "hidden" });
  const width = options.width, minHeight = options.minHeight;
  const preferredHeight = options.preferredHeight, gap = options.gap, align = options.align;
  useLayoutEffect(() => {
    if (!open) return;
    let frame = 0;
    const update = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        if (!anchor.current || !panel.current) return;
        const measured = Math.max(panel.current.scrollHeight, panel.current.offsetHeight, 40);
        setStyle(computePopupPlacement(anchor.current.getBoundingClientRect(),
          { width: window.innerWidth, height: window.innerHeight }, measured,
          { width, minHeight, preferredHeight, gap, align }));
      });
    };
    update();
    window.addEventListener("scroll", update, true);
    window.addEventListener("resize", update);
    window.visualViewport?.addEventListener("resize", update);
    const observer = new ResizeObserver(update);
    if (anchor.current) observer.observe(anchor.current);
    if (panel.current) observer.observe(panel.current);
    return () => { cancelAnimationFrame(frame); observer.disconnect();
      window.removeEventListener("scroll", update, true);
      window.removeEventListener("resize", update);
      window.visualViewport?.removeEventListener("resize", update); };
  }, [open, anchor, panel, width, minHeight, preferredHeight, gap, align]);
  return style;
}
