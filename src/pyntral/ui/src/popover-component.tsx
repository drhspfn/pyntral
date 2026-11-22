/** Compound, viewport-aware popover atom for built-in panels and app extensions. */
import {
  cloneElement, createContext, isValidElement, useCallback, useContext, useEffect,
  useId, useRef, useState, type CSSProperties, type HTMLAttributes,
  type MouseEvent, type ReactElement, type ReactNode, type RefObject,
} from "react";
import { createPortal } from "react-dom";
import { usePopupPosition } from "./popover";

type Interaction = "click" | "hover" | "both";
type ContextValue = {
  open: boolean; setOpen: (value: boolean) => void; trigger: RefObject<HTMLSpanElement | null>;
  content: RefObject<HTMLDivElement | null>; id: string; mode: Interaction;
  enter: () => void; leave: () => void; closeOnInteractOutside: boolean; closeOnEscape: boolean;
};
const Context = createContext<ContextValue | null>(null);
function usePopoverContext() {
  const value = useContext(Context);
  if (!value) throw new Error("Popover parts must be nested inside <Popover>");
  return value;
}
export interface PopoverProps {
  children: ReactNode;
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (value: boolean) => void;
  interaction?: Interaction;
  openDelay?: number;
  closeDelay?: number;
  closeOnInteractOutside?: boolean;
  closeOnEscape?: boolean;
}
export function Popover({ children, open: controlled, defaultOpen = false, onOpenChange,
  interaction = "click", openDelay = 120, closeDelay = 180,
  closeOnInteractOutside = true, closeOnEscape = true }: PopoverProps) {
  const [internal, setInternal] = useState(defaultOpen);
  const open = controlled ?? internal;
  const trigger = useRef<HTMLSpanElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const id = useId();
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const current = useRef(open);
  current.current = open;
  const clear = useCallback(() => { if (timer.current !== null) { clearTimeout(timer.current); timer.current = null; } }, []);
  const setOpen = useCallback((next: boolean) => {
    clear();
    if (current.current === next) return;
    current.current = next;
    if (controlled === undefined) setInternal(next);
    onOpenChange?.(next);
  }, [clear, controlled, onOpenChange]);
  const enter = useCallback(() => {
    if (interaction === "click") return;
    clear();
    timer.current = setTimeout(() => setOpen(true), Math.max(0, openDelay));
  }, [interaction, clear, setOpen, openDelay]);
  const leave = useCallback(() => {
    if (interaction === "click") return;
    clear();
    timer.current = setTimeout(() => setOpen(false), Math.max(0, closeDelay));
  }, [interaction, clear, setOpen, closeDelay]);
  useEffect(() => clear, [clear]);
  useEffect(() => {
    if (!open) return;
    const pointer = (event: PointerEvent) => {
      if (!closeOnInteractOutside) return;
      const path = event.composedPath();
      if (path.includes(trigger.current as EventTarget) || path.includes(content.current as EventTarget)) return;
      const target = event.target;
      // Nested Select, Calendar, and operator menus are rendered in independent portals.
      const element = target instanceof Element ? target : target instanceof Node ? target.parentElement : null;
      if (element?.closest("[data-ra-popover-nested]")) return;
      setOpen(false);
    };
    const keydown = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || !closeOnEscape || event.defaultPrevented) return;
      if (document.querySelector("[data-ra-popover-nested]")) return;
      setOpen(false);
      trigger.current?.querySelector<HTMLElement>("button, [tabindex]")?.focus();
    };
    document.addEventListener("pointerdown", pointer);
    document.addEventListener("keydown", keydown);
    return () => { document.removeEventListener("pointerdown", pointer); document.removeEventListener("keydown", keydown); };
  }, [open, setOpen, closeOnInteractOutside, closeOnEscape]);
  return <Context.Provider value={{ open, setOpen, trigger, content, id, mode: interaction,
    enter, leave, closeOnInteractOutside, closeOnEscape }}>{children}</Context.Provider>;
}
export function PopoverTrigger({ children, asChild = false }: {
  children: ReactNode; asChild?: boolean;
}) {
  const { open, setOpen, trigger, id, mode, enter, leave } = usePopoverContext();
  const click = () => { if (mode !== "hover") setOpen(!open); };
  const wrapper = <span ref={trigger} className="ra-popover-trigger" onPointerEnter={enter}
    onPointerLeave={leave} onClick={click} aria-expanded={open} aria-controls={id}>
    {children}
  </span>;
  if (!asChild || !isValidElement(children)) return wrapper;
  // Keep the DOM anchor stable and preserve the consumer's own handlers.
  const element = children as ReactElement<{ onClick?: (event: MouseEvent) => void }>;
  return <span ref={trigger} className="ra-popover-trigger" onPointerEnter={enter}
    onPointerLeave={leave}>{cloneElement(element, {
      "aria-expanded": open, "aria-controls": id,
      onClick: (event: MouseEvent) => { element.props.onClick?.(event); if (!event.defaultPrevented) click(); },
    } as typeof element.props)}</span>;
}
export interface PopoverContentProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  width?: number | "trigger";
  minWidth?: number;
  maxWidth?: number;
  minHeight?: number;
  maxHeight?: number;
  align?: "start" | "end";
  gap?: number;
  padded?: boolean;
}
export function PopoverContent({ children, width = 320, minWidth, maxWidth, minHeight = 160,
  maxHeight = 520, align = "end", gap = 8, padded = true,
  className = "", style, ...rest }: PopoverContentProps) {
  const { open, trigger, content, id, mode, enter, leave } = usePopoverContext();
  const position = usePopupPosition(open, trigger, content,
    { width: width === "trigger" ? "anchor" : width, align, minHeight,
      preferredHeight: maxHeight, gap });
  const viewWidth = typeof position.width === "number" ? position.width : undefined;
  const effectiveWidth = viewWidth !== undefined ? Math.max(0, Math.min(
    viewWidth, maxWidth ?? Infinity)) : undefined;
  const adjustedLeft = typeof position.left === "number" && viewWidth !== undefined &&
    effectiveWidth !== undefined && align === "end"
    ? position.left + viewWidth - effectiveWidth : position.left;
  if (!open) return null;
  return createPortal(<div {...rest} id={id} ref={content}
    className={`ra-popover-content ${padded ? "ra-popover-padded" : ""} ${className}`}
    role={rest.role ?? "dialog"}
    onPointerEnter={(e) => { enter(); rest.onPointerEnter?.(e); }}
    onPointerLeave={(e) => { leave(); rest.onPointerLeave?.(e); }}
    style={{ ...position, left: adjustedLeft, width: effectiveWidth ?? position.width,
      minWidth: minWidth ? Math.min(minWidth, window.innerWidth - 24) : undefined,
      maxWidth: maxWidth ? Math.min(maxWidth, window.innerWidth - 24) : undefined,
      ...style }}
    data-ra-popover-content="" data-ra-popover-mode={mode}>{children}</div>, document.body);
}
export function PopoverHeader({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <header className={`ra-popover-header ${className}`}>{children}</header>;
}
export function PopoverFooter({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <footer className={`ra-popover-footer ${className}`}>{children}</footer>;
}
export function PopoverClose({ children, className = "" }: { children: ReactNode; className?: string }) {
  const { setOpen } = usePopoverContext();
  return <button type="button" className={className} onClick={() => setOpen(false)}>{children}</button>;
}
export function usePopover() {
  const { open, setOpen } = usePopoverContext();
  return { open, setOpen, close: () => setOpen(false) };
}
