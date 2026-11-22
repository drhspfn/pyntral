/** Small, keyboard accessible operator chooser, independent from Select's value display. */
import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { createPortal } from "react-dom";
import {
  AlignLeft, AlignRight, ArrowDown, ArrowLeftRight, ArrowUp, Check, ChevronDown,
  ChevronLeft, ChevronRight, Equal, EqualNot, Search,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { usePopupPosition } from "./popover";
import type { FilterOperator } from "./filter-state";

export const OPERATOR_LABELS: Record<FilterOperator, string> = {
  eq: "Equals", neq: "Not equal", contains: "Contains", starts_with: "Starts with",
  ends_with: "Ends with", gt: "Greater than", gte: "Greater or equal",
  lt: "Less than", lte: "Less or equal", between: "Between", in: "Include", not_in: "Exclude",
};
const ICONS: Record<FilterOperator, LucideIcon> = {
  eq: Equal, neq: EqualNot, contains: Search, starts_with: AlignLeft, ends_with: AlignRight,
  gt: ChevronRight, gte: ArrowUp, lt: ChevronLeft, lte: ArrowDown,
  between: ArrowLeftRight, in: Check, not_in: EqualNot,
};

export function FilterOperatorButton({ operator, operators, label, onChange }: {
  operator: FilterOperator;
  operators: FilterOperator[];
  label: string;
  onChange: (value: FilterOperator) => void;
}) {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const popupStyle = usePopupPosition(open, trigger, menu, {
    width: 206, align: "end", preferredHeight: 300, minHeight: 135,
  });
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!trigger.current?.contains(event.target as Node) &&
          !menu.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") { setOpen(false); trigger.current?.focus(); }
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);
  const focusItem = (index: number) => {
    menu.current?.querySelectorAll<HTMLButtonElement>("[role=menuitemradio]")[index]?.focus();
  };
  const show = (focus = false) => {
    setOpen(true);
    if (focus) requestAnimationFrame(() => focusItem(Math.max(0, operators.indexOf(operator))));
  };
  const onMenuKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const items = menu.current?.querySelectorAll<HTMLButtonElement>("[role=menuitemradio]");
    if (!items?.length) return;
    const index = [...items].indexOf(document.activeElement as HTMLButtonElement);
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      items[(index + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length].focus();
    }
    if (event.key === "Home" || event.key === "End") {
      event.preventDefault(); items[event.key === "Home" ? 0 : items.length - 1].focus();
    }
  };
  const Icon = ICONS[operator];
  return <>
    <button ref={trigger} type="button" className={`ra-filter-operator-trigger ${open ? "is-open" : ""}`}
      aria-label={`${label}: ${OPERATOR_LABELS[operator]}. Change comparison`}
      title={`${label} · ${OPERATOR_LABELS[operator]}`}
      aria-haspopup="menu" aria-expanded={open}
      onClick={() => open ? setOpen(false) : show()}
      onKeyDown={(event) => {
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
          event.preventDefault(); show(true);
        }
      }}>
      <Icon size={16} strokeWidth={1.9}/><ChevronDown size={12} strokeWidth={2}/>
    </button>
    {open && createPortal(<div ref={menu} role="menu" aria-label={`${label} filter comparison`}
      onKeyDown={onMenuKeyDown} className="ra-filter-operator-menu" data-ra-popover-nested="" style={popupStyle}>
      <div className="ra-filter-menu-caption">Comparison</div>
      {operators.map((candidate) => {
        const CandidateIcon = ICONS[candidate];
        return <button key={candidate} type="button" role="menuitemradio"
          aria-checked={operator === candidate} className={operator === candidate ? "is-selected" : ""}
          onClick={() => { onChange(candidate); setOpen(false); trigger.current?.focus(); }}>
          <CandidateIcon size={15}/><span>{OPERATOR_LABELS[candidate]}</span>
          {operator === candidate && <Check size={15} className="ra-filter-menu-check"/>}
        </button>;
      })}
    </div>, document.body)}
  </>;
}
