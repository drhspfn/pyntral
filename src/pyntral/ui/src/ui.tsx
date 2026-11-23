/** Public UI primitives. Import from @pyntral/ui in customer TSX extensions. */
import {
  forwardRef, useEffect, useId, useMemo, useRef, useState,
  type CSSProperties, type InputHTMLAttributes, type KeyboardEvent,
  type ReactNode, type TextareaHTMLAttributes,
} from "react";
import { createPortal } from "react-dom";
import { usePopupPosition } from "./popover";
import { useI18n } from "./i18n";
import { CalendarDays, Check, ChevronDown, ChevronLeft, ChevronRight, LoaderCircle, Search, X } from "lucide-react";

export { FilterOperatorButton } from "./filter-operator";
export { Checkbox, CheckboxGroup, RadioGroup, Switch, ToggleGroup } from "./controls";
export { SortableList } from "./sortable";
import { Button } from "./button";
export { Button } from "./button";
export type { ButtonProps, ButtonVariant } from "./button";
export { FileUpload } from "./file-upload";
export { FileRow } from "./file-row";
export { Icon } from "./icon";
export { Brand } from "./brand";
export type { BrandProps } from "./brand";
export type { IconProps } from "./icon";
export type { FileRowProps } from "./file-row";
export { Collapsible } from "./collapsible";
export type { CollapsibleProps } from "./collapsible";
export { OverflowText } from "./overflow-text";
export { formatFileRejection } from "./file-upload-state";
export type { FileUploadProps, FileUploadReceipt, FileUploadContext } from "./file-upload";
export { Popover, PopoverTrigger, PopoverContent, PopoverHeader, PopoverFooter, PopoverClose, usePopover } from "./popover-component";
export type { PopoverProps, PopoverContentProps } from "./popover-component";
export type { SortableListProps } from "./sortable";
export type { CheckboxProps, CheckboxGroupProps, ChoiceOption, RadioGroupProps, SwitchProps, ToggleGroupProps } from "./controls";
export type { FilterOperator } from "./filter-state";

export function Badge({ children, tone = "neutral", className = "" }: {
  children: ReactNode; tone?: "neutral" | "success" | "danger" | "primary"; className?: string;
}) {
  return <span className={`ra-badge ra-badge-${tone} ${className}`}>{children}</span>;
}
export function Card({ children, title, description, className = "" }: {
  children: ReactNode; title?: ReactNode; description?: ReactNode; className?: string;
}) {
  return <section className={`ra-card ${className}`}>
    {(title || description) && <header className="ra-card-header">
      {title && <strong>{title}</strong>}{description && <small>{description}</small>}
    </header>}{children}</section>;
}
export const TextInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function TextInput({
  className = "", ...props
}, ref) {
  return <input {...props} ref={ref} className={`ra-input ${className}`} />;
});
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea({
  className = "", ...props
}, ref) {
  return <textarea {...props} ref={ref} className={`ra-input ra-textarea ${className}`} />;
});
export function FormField({ label, htmlFor, hint, required, children, span = 1 }: {
  label: string; htmlFor?: string; hint?: ReactNode; required?: boolean;
  children: ReactNode; span?: 1 | 2;
}) {
  return <div className={`ra-form-field ${span === 2 ? "ra-field-wide" : ""}`}>
    <label htmlFor={htmlFor}>{label}{required && <span className="required"> *</span>}</label>
    {children}{hint && <small>{hint}</small>}
  </div>;
}
export function SearchInput({ value, onChange, onSearch, showIcon = true, showSubmit = false,
  submitPosition = "inside", placeholder = "Search…", loading = false, disabled = false,
  className = "", ...props }: {
  value: string; onChange: (value: string) => void; onSearch?: (value: string) => void;
  showIcon?: boolean; showSubmit?: boolean; submitPosition?: "inside" | "outside";
  placeholder?: string; loading?: boolean; disabled?: boolean; className?: string;
} & Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "onSubmit" | "onSearch">) {
  const searchButton = <Button type="submit" variant="ghost" aria-label="Submit search" loading={loading} disabled={disabled}
    className="ra-search-submit" endIcon={<ChevronRight size={17}/>} />;
  return <form className={`ra-search ${className}`} onSubmit={(event) => { event.preventDefault(); onSearch?.(value); }}>
    <div className="ra-search-field">{showIcon && <Search size={17} aria-hidden="true"/>}
      <input {...props} type="search" value={value} onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder} disabled={disabled}/>
      {showSubmit && submitPosition === "inside" && searchButton}
    </div>{showSubmit && submitPosition === "outside" && searchButton}
  </form>;
}

export interface SelectOption<T extends string | number = string | number> {
  value: T;
  label: string;
  disabled?: boolean;
}
export interface SelectProps<T extends string | number = string | number> {
  value: T | null | T[];
  onChange: (value: T | null | T[]) => void;
  options?: SelectOption<T>[];
  loadOptions?: (query: string) => Promise<SelectOption<T>[]>;
  selectedOptions?: SelectOption<T>[];
  multiple?: boolean;
  searchable?: boolean;
  maxItems?: number; // Maximum visible chips, remainder collapsed into +N (not selection limit).
  maxSelections?: number;
  placeholder?: string;
  disabled?: boolean;
  clearable?: boolean;
  id?: string;
  ariaLabel?: string;
  emptyLabel?: string;
  className?: string;
  popupMinHeight?: number;
  popupMaxHeight?: number;
}
/** One implementation for static and debounced remote search, including relationships. */
export function Select<T extends string | number = string | number>({
  value, onChange, options = [], loadOptions, selectedOptions = [], multiple = false,
  searchable = true, maxItems = 3, maxSelections, placeholder = "Choose…",
  disabled = false, clearable = true, id, ariaLabel, emptyLabel = "No results", className = "",
  popupMinHeight = 160, popupMaxHeight = 320,
}: SelectProps<T>) {
  const generatedId = useId();
  const listId = `${id || generatedId}-options`;
  const root = useRef<HTMLDivElement>(null);
  const textRef = useRef<HTMLInputElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const [opened, setOpened] = useState(false);
  const popupStyle = usePopupPosition(opened, root, panel,
    { width: "anchor", minHeight: popupMinHeight, preferredHeight: popupMaxHeight });
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [remote, setRemote] = useState<SelectOption<T>[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [retries, setRetries] = useState(0);
  const [active, setActive] = useState(0);
  const [width, setWidth] = useState(300);
  const [remembered, setRemembered] = useState<SelectOption<T>[]>([]);
  const selected = useMemo(() => value == null ? [] : Array.isArray(value) ? value : [value], [value]);
  useEffect(() => {
    const observer = new ResizeObserver((entries) => { if (entries[0]) setWidth(entries[0].contentRect.width); });
    if (root.current) observer.observe(root.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    const onPointer = (event: PointerEvent) => {
      if (root.current && !root.current.contains(event.target as Node) &&
          !panel.current?.contains(event.target as Node)) setOpened(false);
    };
    document.addEventListener("pointerdown", onPointer);
    return () => document.removeEventListener("pointerdown", onPointer);
  }, []);
  useEffect(() => { const timer = window.setTimeout(() => setQuery(search), 230); return () => window.clearTimeout(timer); }, [search]);
  useEffect(() => {
    if (!loadOptions || !opened) return;
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    loadOptions(query).then((result) => { if (!cancelled) setRemote(result); })
      .catch((error: unknown) => { if (!cancelled) { setRemote([]);
        setLoadError(error instanceof Error ? error.message : "Unable to load options"); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [loadOptions, query, opened, retries]);
  const candidateOptions = loadOptions ? remote : options.filter((o) => !searchable || o.label.toLowerCase().includes(search.toLowerCase()));
  const map = new Map<string, SelectOption<T>>();
  [...options, ...selectedOptions, ...remembered, ...remote].forEach((o) => map.set(String(o.value), o));
  const badges = selected.map((entry) => map.get(String(entry)) || { value: entry, label: String(entry) });
  // Fit pills to the *available* width, in addition to the explicitly configured ceiling.
  const chipBudget = Math.max(60, width - 72);
  let visibleCount = 0;
  let used = 0;
  for (const badge of badges.slice(0, Math.max(1, maxItems))) {
    const estimate = Math.min(155, 34 + badge.label.length * 6.5);
    const rest = badges.length - visibleCount - 1;
    if (visibleCount > 0 && used + estimate + (rest > 0 ? 36 : 0) > chipBudget) break;
    used += estimate + 4;
    visibleCount++;
  }
  const emit = (v: T) => {
    const picked = candidateOptions.find((o) => String(o.value) === String(v));
    if (picked) setRemembered((old) => [...old.filter((o) => String(o.value) !== String(v)), picked]);
    if (multiple) {
      const has = selected.some((item) => String(item) === String(v));
      if (!has && maxSelections !== undefined && selected.length >= maxSelections) return;
      onChange(has ? selected.filter((item) => String(item) !== String(v)) : [...selected, v]);
      textRef.current?.focus();
    } else { onChange(v); setOpened(false); setSearch(""); }
  };
  const toggle = () => { if (disabled) return; setOpened((current) => !current); setActive(0); };
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (disabled) return;
    if (event.key === "Escape") { setOpened(false); return; }
    if ((event.key === "Enter" || event.key === " ") && !opened) {
      event.preventDefault(); setOpened(true); textRef.current?.focus(); return;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setOpened(true);
      setActive((n) => Math.max(0, Math.min(candidateOptions.length - 1, n + (event.key === "ArrowDown" ? 1 : -1))));
    }
    if (event.key === "Enter" && opened && candidateOptions[active] && !candidateOptions[active].disabled) {
      event.preventDefault(); emit(candidateOptions[active].value);
    }
  };
  return <div ref={root} className={`ra-select ${disabled ? "ra-select-disabled" : ""} ${className}`} onKeyDown={onKeyDown}>
    <div id={id} className={`ra-select-control ${opened ? "ra-select-open" : ""}`} role="combobox"
      aria-haspopup="listbox" aria-controls={listId} aria-expanded={opened} aria-label={ariaLabel || placeholder}
      tabIndex={disabled ? -1 : 0} onClick={() => { if (!opened) { setOpened(true); textRef.current?.focus(); } }}>
      {multiple ? <div className="ra-select-chips">
        {badges.slice(0, visibleCount).map((o) => <span className="ra-select-chip" key={String(o.value)} title={o.label}>
          <span>{o.label}</span><button type="button" aria-label={`Remove ${o.label}`} onClick={(e) => {
            e.stopPropagation(); onChange(selected.filter((entry) => String(entry) !== String(o.value)));
          }}><X size={12}/></button></span>)}
        {badges.length > visibleCount && <span className="ra-select-overflow" title={badges.slice(visibleCount).map((o) => o.label).join(", ")}>+{badges.length - visibleCount}</span>}
      </div> : selected.length > 0 && (!opened || !searchable) ? <span className="ra-select-single">{badges[0]?.label}</span> : null}
      {searchable && opened ? <input ref={textRef} className="ra-select-search" autoFocus value={search}
        onChange={(e) => { setSearch(e.target.value); setActive(0); }}
        placeholder="Search…" aria-label={`Search ${ariaLabel || placeholder}`}/> : null}
      {!selected.length && !opened && <span className="ra-select-placeholder">{placeholder}</span>}
      <span className="ra-select-icons">
        {loading && <LoaderCircle size={14} className="spin" />}
        {clearable && selected.length > 0 && !disabled && <button type="button" aria-label="Clear selection" onClick={(event) => {
          event.stopPropagation(); onChange(multiple ? [] : null);
        }}><X size={14}/></button>}
        <button type="button" aria-label="Toggle options" disabled={disabled} onClick={(event) => { event.stopPropagation(); toggle(); }}>
          <ChevronDown size={16}/></button>
      </span>
    </div>
    {opened && !disabled && createPortal(<div ref={panel} className="ra-select-menu" data-ra-popover-nested="" style={popupStyle}
      id={listId} role="listbox" aria-multiselectable={multiple}>
      {loadError && <div className="ra-select-empty" role="alert">{loadError} <button type="button" onClick={() => setRetries((n) => n + 1)}>Retry</button></div>}
      {!loading && !loadError && candidateOptions.length === 0 && <div className="ra-select-empty">{emptyLabel}</div>}
      {candidateOptions.map((o, i) => {
        const checked = selected.some((v) => String(v) === String(o.value));
        return <button type="button" key={String(o.value)} role="option" aria-selected={checked}
          className={`ra-select-option ${i === active ? "ra-select-active" : ""}`} disabled={o.disabled}
          onMouseEnter={() => setActive(i)} onClick={() => emit(o.value)}>
          {multiple && <span className={`ra-select-check ${checked ? "checked" : ""}`}>{checked && <Check size={13}/>}</span>}
          <span className="ra-option-label">{o.label}</span>{!multiple && checked && <Check size={15} className="ra-select-mark"/>}
        </button>;
      })}
    </div>, document.body)}
  </div>;
}
export function AsyncSelect<T extends string | number = string | number>(props: SelectProps<T> & {
  loadOptions: (query: string) => Promise<SelectOption<T>[]>;
}) { return <Select {...props}/>; }

export function Calendar({ value, onChange, min, max }: {
  value: string | null; onChange: (isoDate: string) => void; min?: string; max?: string;
}) {
  const { locale } = useI18n();
  const initial = value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T12:00:00`) : new Date();
  const [month, setMonth] = useState(() => new Date(initial.getFullYear(), initial.getMonth(), 1));
  useEffect(() => {
    if (value && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
      const parsed = new Date(`${value}T12:00:00`);
      setMonth(new Date(parsed.getFullYear(), parsed.getMonth(), 1));
    }
  }, [value]);
  const year = month.getFullYear(), mo = month.getMonth();
  const startOffset = (new Date(year, mo, 1).getDay() + 6) % 7;
  const days = new Date(year, mo + 1, 0).getDate();
  const dayCells = Array.from({ length: Math.ceil((startOffset + days) / 7) * 7 }, (_, i) => i - startOffset + 1);
  const iso = (day: number) => `${year}-${String(mo + 1).padStart(2,"0")}-${String(day).padStart(2,"0")}`;
  const today = new Date();
  const todayIso = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,"0")}-${String(today.getDate()).padStart(2,"0")}`;
  return <div className="ra-calendar">
    <div className="ra-calendar-head"><Button variant="ghost" aria-label="Previous month" onClick={() => setMonth(new Date(year, mo - 1, 1))} startIcon={<ChevronLeft size={17}/>}/>
      <strong>{month.toLocaleDateString(locale, { month: "long", year: "numeric" })}</strong>
      <Button variant="ghost" aria-label="Next month" onClick={() => setMonth(new Date(year, mo + 1, 1))} startIcon={<ChevronRight size={17}/>}/></div>
    <div className="ra-calendar-days">{Array.from({length:7}, (_,i) =>
      new Date(Date.UTC(2024, 0, i+1)).toLocaleDateString(locale, {weekday:"short"}))
      .map((day, i) => <span key={i}>{day}</span>)}
      {dayCells.map((day, index) => day > 0 && day <= days ? <button key={index} type="button"
        className={`${value === iso(day) ? "selected" : ""} ${todayIso === iso(day) ? "today" : ""}`}
        disabled={(min !== undefined && iso(day) < min) || (max !== undefined && iso(day) > max)}
        aria-label={iso(day)} aria-pressed={value === iso(day)} onClick={() => onChange(iso(day))}>{day}</button> : <span key={index}/>)}
    </div>
  </div>;
}
export function DatePicker({ value, onChange, includeTime = false, min, max, id, ariaLabel,
  popupMinHeight = 300, placeholder = "Choose a date…" }: {
  value: string | null; onChange: (value: string | null) => void; includeTime?: boolean;
  min?: string; max?: string; placeholder?: string; id?: string; ariaLabel?: string;
  popupMinHeight?: number;
}) {
  const { locale } = useI18n();
  const [open, setOpen] = useState(false);
  const container = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const popupStyle = usePopupPosition(open, container, panel,
    { width: 330, minHeight: popupMinHeight, preferredHeight: 440 });
  const parsed = value && includeTime ? new Date(value) : null;
  const valid = parsed && !Number.isNaN(parsed.getTime());
  const date = valid ? `${parsed!.getFullYear()}-${String(parsed!.getMonth() + 1).padStart(2, "0")}-${String(parsed!.getDate()).padStart(2,"0")}` : value?.slice(0, 10) || null;
  const time = valid ? `${String(parsed!.getHours()).padStart(2,"0")}:${String(parsed!.getMinutes()).padStart(2,"0")}` : value?.slice(11, 16) || "12:00";
  const serialize = (day: string, timePart: string) => includeTime ? new Date(`${day}T${timePart}:00`).toISOString() : day;
  useEffect(() => {
    const handler = (event: PointerEvent) => {
      if (container.current && !container.current.contains(event.target as Node) &&
          !panel.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", handler);
    return () => document.removeEventListener("pointerdown", handler);
  }, []);
  return <div className="ra-date-picker" ref={container}>
    <Button id={id} type="button" className="ra-date-trigger" aria-expanded={open} aria-label={ariaLabel} variant="secondary"
      startIcon={<CalendarDays size={16}/>} onClick={() => setOpen(!open)}>
      {value ? (valid ? parsed!.toLocaleString(locale) : value) : placeholder}</Button>
    {value && <button type="button" className="ra-date-clear" title="Clear date" onClick={() => onChange(null)}><X size={14}/></button>}
    {open && createPortal(<div ref={panel} className="ra-date-popover" data-ra-popover-nested="" style={popupStyle}><Calendar value={date} min={min?.slice(0,10)} max={max?.slice(0,10)}
      onChange={(day) => { onChange(serialize(day, time)); if (!includeTime) setOpen(false); }}/>
      {includeTime && <div className="ra-date-time"><label>Time <input type="time" value={time}
        onChange={(event) => { if (date) onChange(serialize(date, event.target.value)); }}/></label>
        <Button type="button" variant="primary" onClick={() => setOpen(false)}>Done</Button></div>}
    </div>, document.body)}
  </div>;
}
export function Dialog({ open, onClose, title, children, footer, width = 480 }: {
  open: boolean; onClose: () => void; title: ReactNode; children: ReactNode;
  footer?: ReactNode; width?: number;
}) {
  useEffect(() => {
    if (!open) return;
    const handler = (event: globalThis.KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);
  if (!open) return null;
  return <div className="ra-dialog-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
    <section className="ra-dialog" role="dialog" aria-modal="true" aria-label={typeof title === "string" ? title : "Dialog"}
      style={{ maxWidth: width } as CSSProperties}>
      <div className="ra-dialog-head"><h2>{title}</h2><Button variant="ghost" aria-label="Close dialog" onClick={onClose} startIcon={<X size={18}/>}/></div>
      <div className="ra-dialog-content">{children}</div>{footer && <footer className="ra-dialog-actions">{footer}</footer>}
    </section>
  </div>;
}
