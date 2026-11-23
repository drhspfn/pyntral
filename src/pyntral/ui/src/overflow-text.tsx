import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { usePopupPosition } from "./popover";

/** Displays the full label only when its rendered text is actually clipped. */
export function OverflowText({ children, className = "" }: { children: string; className?: string }) {
  const anchor = useRef<HTMLSpanElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const label = anchor.current;
    if (!label) return;
    const trigger = label.closest("button, a") ?? label;
    let hover = false;
    let focus = false;
    const update = () => setOpen((hover || focus) && label.scrollWidth > label.clientWidth + 1);
    const enter = () => { hover = true; update(); };
    const leave = () => { hover = false; update(); };
    const focused = () => { focus = trigger.matches(":focus-visible"); update(); };
    const blurred = () => { focus = false; update(); };
    const dismiss = (event: Event) => { if ((event as KeyboardEvent).key === "Escape") setOpen(false); };
    trigger.addEventListener("pointerenter", enter);
    trigger.addEventListener("pointerleave", leave);
    trigger.addEventListener("focus", focused);
    trigger.addEventListener("blur", blurred);
    trigger.addEventListener("keydown", dismiss);
    const observer = new ResizeObserver(update);
    observer.observe(label);
    return () => {
      observer.disconnect();
      trigger.removeEventListener("pointerenter", enter);
      trigger.removeEventListener("pointerleave", leave);
      trigger.removeEventListener("focus", focused);
      trigger.removeEventListener("blur", blurred);
      trigger.removeEventListener("keydown", dismiss);
    };
  }, [children]);
  const position = usePopupPosition(open, anchor, panel,
    { width: 260, align: "start", minHeight: 28, preferredHeight: 100, gap: 7 });
  return <><span ref={anchor} className={`ra-overflow-text ${className}`}>{children}</span>
    {open && createPortal(<div ref={panel} role="tooltip" className="ra-overflow-tooltip" style={position}>{children}</div>, document.body)}</>;
}
