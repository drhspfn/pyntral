/** Accessible sortable list atom for mouse, pen, touch and keyboard. */
import { useId, useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from "react";
import { GripVertical } from "lucide-react";
import { moveSortableItem, sameSortableOrder } from "./sortable-state";

export interface SortableListProps<T> {
  items: readonly T[];
  getKey: (item: T) => string;
  getLabel?: (item: T) => string;
  renderItem: (item: T, index: number) => ReactNode;
  onReorder: (items: T[]) => void;
  ariaLabel: string;
  className?: string;
  itemClassName?: (item: T) => string;
  disabled?: boolean;
}
interface Drag<T> {
  key: string;
  mode: "pointer" | "keyboard";
  pointerId?: number;
  order: T[];
}
/**
 * Only the handle initiates dragging. Capturing pointers on the stable list
 * root preserves the gesture when keyed React rows move. Changes are committed
 * on drop, never during a preview; Escape / pointercancel discards the preview.
 */
export function SortableList<T>({
  items, getKey, getLabel = getKey, renderItem, onReorder, ariaLabel,
  className = "", itemClassName, disabled = false,
}: SortableListProps<T>) {
  const root = useRef<HTMLDivElement>(null);
  const drag = useRef<Drag<T> | null>(null);
  const [preview, setPreview] = useState<T[] | null>(null);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [announcement, announce] = useState("");
  const instructionsId = useId();
  const rendered = preview ?? items;
  const reset = () => { drag.current = null; setPreview(null); setActiveKey(null); };
  const finish = (commit: boolean) => {
    const active = drag.current;
    if (!active) return;
    if (commit && !sameSortableOrder(items, active.order, getKey)) {
      onReorder([...active.order]);
      const index = active.order.findIndex((item) => getKey(item) === active.key);
      announce(getLabel(active.order[index]) + ", position " + (index + 1) + " of " + active.order.length);
    } else if (!commit) announce("Reordering cancelled.");
    reset();
  };
  const lift = (event: PointerEvent<HTMLButtonElement>, item: T) => {
    if (disabled || drag.current || !event.isPrimary || event.button !== 0) return;
    const list = root.current;
    if (!list) return;
    event.preventDefault();
    event.currentTarget.focus();
    list.setPointerCapture(event.pointerId);
    drag.current = {key: getKey(item), mode: "pointer", pointerId: event.pointerId, order: [...items]};
    setPreview([...items]);
    setActiveKey(getKey(item));
  };
  const movePointer = (event: PointerEvent<HTMLDivElement>) => {
    const active = drag.current;
    const list = root.current;
    if (!active || active.mode !== "pointer" || active.pointerId !== event.pointerId || !list) return;
    const bounds = list.getBoundingClientRect();
    if (list.scrollHeight > list.clientHeight) {
      if (event.clientY < bounds.top + 26) list.scrollTop -= 12;
      if (event.clientY > bounds.bottom - 26) list.scrollTop += 12;
    }
    const hovered = document.elementFromPoint(event.clientX, event.clientY)?.closest<HTMLElement>("[data-ra-sortable-key]");
    if (!hovered || !list.contains(hovered)) return;
    const from = active.order.findIndex((item) => getKey(item) === active.key);
    const to = active.order.findIndex((item) => getKey(item) === hovered.dataset.raSortableKey);
    if (from < 0 || to < 0 || from === to) return;
    const next = moveSortableItem(active.order, from, to);
    active.order = next;
    setPreview(next);
  };
  const dropPointer = (event: PointerEvent<HTMLDivElement>) => {
    const active = drag.current;
    if (!active || active.mode !== "pointer" || active.pointerId !== event.pointerId) return;
    if (root.current?.hasPointerCapture(event.pointerId)) root.current.releasePointerCapture(event.pointerId);
    finish(true);
  };
  const cancelPointer = (event: PointerEvent<HTMLDivElement>) => {
    const active = drag.current;
    if (active?.mode === "pointer" && active.pointerId === event.pointerId) finish(false);
  };
  const keyDown = (event: KeyboardEvent<HTMLButtonElement>, item: T) => {
    if (disabled) return;
    const key = getKey(item);
    const active = drag.current;
    if (event.key === "Escape" && active?.mode === "keyboard" && active.key === key) {
      event.preventDefault(); finish(false); return;
    }
    if (event.key === " " || event.key === "Enter") {
      if (active && (active.mode !== "keyboard" || active.key !== key)) return;
      event.preventDefault();
      if (active) { finish(true); return; }
      drag.current = {key, mode: "keyboard", order: [...items]};
      setPreview([...items]);
      setActiveKey(key);
      announce(getLabel(item) + " picked up. Arrow keys move; Space or Enter drops; Escape cancels.");
      return;
    }
    if (!active || active.mode !== "keyboard" || active.key !== key ||
        (event.key !== "ArrowUp" && event.key !== "ArrowDown")) return;
    event.preventDefault();
    const from = active.order.findIndex((row) => getKey(row) === key);
    const to = from + (event.key === "ArrowUp" ? -1 : 1);
    if (to < 0 || to >= active.order.length) return;
    const next = moveSortableItem(active.order, from, to);
    active.order = next;
    setPreview(next);
    announce(getLabel(item) + ", position " + (to + 1) + " of " + next.length);
  };
  return <div ref={root} role="list" aria-label={ariaLabel}
    className={"ra-sortable-list " + className} onPointerMove={movePointer}
    onPointerUp={dropPointer} onPointerCancel={cancelPointer}>
    <span id={instructionsId} className="ra-visually-hidden">
      Press Space or Enter on the handle to pick up, Up or Down to move,
      Space or Enter to drop, and Escape to cancel.
    </span>
    {rendered.map((item, index) => {
      const key = getKey(item);
      const lifting = key === activeKey;
      return <div key={key} data-ra-sortable-key={key} role="listitem"
        className={"ra-sortable-item " + (lifting ? "is-dragging " : "") + (itemClassName?.(item) ?? "")}>
        <button type="button" className="ra-sortable-handle" disabled={disabled}
          title={"Reorder " + getLabel(item)} aria-label={"Reorder " + getLabel(item)}
          aria-describedby={instructionsId} aria-pressed={lifting}
          onPointerDown={(event) => lift(event, item)}
          onKeyDown={(event) => keyDown(event, item)}>
          <GripVertical size={16} aria-hidden="true"/>
        </button>
        {renderItem(item, index)}
      </div>;
    })}
    <span className="ra-visually-hidden" role="status" aria-live="polite" aria-atomic="true">{announcement}</span>
  </div>;
}
