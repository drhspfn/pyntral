import { createContext, useContext, useId, useState, useLayoutEffect, useRef, type ReactNode, type KeyboardEvent } from "react";

type State = { id: string; value: string; select: (value: string) => void };
const Context = createContext<State | null>(null);
function useTabs() { const state = useContext(Context); if (!state) throw new Error("Tabs parts require Tabs"); return state; }
export interface TabsProps {
  children: ReactNode; value?: string; defaultValue?: string;
  onValueChange?: (value: string) => void; className?: string;
}
export function Tabs({ children, value, defaultValue = "", onValueChange, className = "" }: TabsProps) {
  const [internal, setInternal] = useState(defaultValue);
  const id = useId();
  const selected = value ?? internal;
  return <Context.Provider value={{ id, value: selected, select: next => {
    if (next === selected) return;
    if (value === undefined) setInternal(next);
    onValueChange?.(next);
  } }}><div className={`ra-tabs ${className}`}>{children}</div></Context.Provider>;
}
export function TabList({ children, label = "Tabs", className = "" }: { children: ReactNode; label?: string; className?: string }) {
  const { select, value } = useTabs();
  const list = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const enabled = Array.from(list.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]:not(:disabled)') ?? [])
      .filter(tab => tab.closest('[role="tablist"]') === list.current);
    if (enabled.length && !enabled.some(tab => tab.dataset.value === value)) select(enabled[0].dataset.value!);
  }, [children, value, select]);
  function keydown(event: KeyboardEvent<HTMLDivElement>) {
    const tabs = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]:not(:disabled)'))
      .filter(tab => tab.closest('[role="tablist"]') === event.currentTarget);
    const index = tabs.indexOf(event.target as HTMLButtonElement);
    if (index < 0 || !tabs.length) return;
    const next = event.key === "ArrowRight" ? tabs[(index + 1) % tabs.length] :
      event.key === "ArrowLeft" ? tabs[(index + tabs.length - 1) % tabs.length] :
      event.key === "Home" ? tabs[0] : event.key === "End" ? tabs[tabs.length - 1] : undefined;
    if (!next) return;
    event.preventDefault(); select(next.dataset.value!); next.focus();
  }
  return <div ref={list} role="tablist" aria-label={label} className={`ra-layout-tabs ${className}`} onKeyDown={keydown}>{children}</div>;
}
export function Tab({ value, children, disabled = false }: { value: string; children: ReactNode; disabled?: boolean }) {
  const tabs = useTabs(), selected = tabs.value === value, suffix = encodeURIComponent(value);
  return <button type="button" role="tab" data-value={value} id={`${tabs.id}-tab-${suffix}`}
    aria-controls={`${tabs.id}-panel-${suffix}`} aria-selected={selected} tabIndex={selected ? 0 : -1}
    disabled={disabled} onClick={() => tabs.select(value)}>{children}</button>;
}
export function TabPanel({ value, children, keepMounted = false, className = "" }: {
  value: string; children: ReactNode; keepMounted?: boolean; className?: string;
}) {
  const tabs = useTabs(), selected = tabs.value === value, suffix = encodeURIComponent(value);
  return <section role="tabpanel" id={`${tabs.id}-panel-${suffix}`} aria-labelledby={`${tabs.id}-tab-${suffix}`}
    hidden={!selected} className={`ra-layout-panel ${className}`} tabIndex={0}>
    {(selected || keepMounted) && children}
  </section>;
}
