/** Compact, accessible table preferences shared by built-in resource lists. */
import { ArrowDown, ArrowUp, GripVertical, Pin, PinOff, RotateCcw, X } from "lucide-react";
import type { Dispatch, SetStateAction } from "react";
import { Checkbox, ToggleGroup } from "./controls";
import { orderedColumns, moveColumn, setColumnVisible, type TablePreferences, defaultTablePreferences } from "./table-prefs";

export interface TableSettingsProps {
  columns: { name: string; label: string }[];
  preferences: TablePreferences;
  onChange: Dispatch<SetStateAction<TablePreferences>>;
  onClose: () => void;
}
export function TableSettings({ columns, preferences, onChange, onClose }: TableSettingsProps) {
  const names = columns.map((field) => field.name);
  const order = orderedColumns(names, { ...preferences, hidden: [] });
  const labelByName = new Map(columns.map((field) => [field.name, field.label]));
  const visibleCount = names.length - preferences.hidden.filter((name) => names.includes(name)).length;
  const move = (name: string, direction: -1 | 1) => onChange((prev) => moveColumn(names, prev, name, direction));
  return <section className="ra-table-settings" aria-label="Table preferences">
    <header className="ra-table-settings-head">
      <div><h3>Customize table</h3><p>Choose which fields appear in your list.</p></div>
      <button className="ra-control-icon" type="button" onClick={onClose} aria-label="Close column settings" title="Close">
        <X size={17}/>
      </button>
    </header>
    <div className="ra-table-settings-body">
      <div className="ra-settings-section-title"><strong>Visible columns</strong>
        <span>{visibleCount} of {names.length}</span></div>
      <div className="ra-columns-list" role="group" aria-label="Column visibility and order">
        {order.map((name, index) => {
          const checked = !preferences.hidden.includes(name);
          const pinned = preferences.pinned === name;
          return <div className={"ra-column-option " + (pinned ? "is-pinned" : "")} key={name}>
            <GripVertical className="ra-column-grip" size={15} aria-hidden="true"/>
            <Checkbox checked={checked} label={labelByName.get(name) ?? name}
              disabled={checked && visibleCount === 1}
              onCheckedChange={(next) => onChange((prev) => setColumnVisible(names, prev, name, next))}/>
            <div className="ra-column-controls">
              <button type="button" className="ra-control-icon" disabled={index === 0}
                onClick={() => move(name, -1)} title={"Move " + name + " up"} aria-label={"Move " + name + " up"}><ArrowUp size={15}/></button>
              <button type="button" className="ra-control-icon" disabled={index === order.length - 1}
                onClick={() => move(name, 1)} title={"Move " + name + " down"} aria-label={"Move " + name + " down"}><ArrowDown size={15}/></button>
              <button type="button" className={"ra-control-icon " + (pinned ? "is-active" : "")}
                disabled={!checked} aria-pressed={pinned} title={(pinned ? "Unpin " : "Pin ") + name}
                aria-label={(pinned ? "Unpin " : "Pin ") + name}
                onClick={() => onChange((prev) => ({ ...prev, pinned: prev.pinned === name ? null : name }))}>
                {pinned ? <PinOff size={15}/> : <Pin size={15}/>}
              </button>
            </div>
          </div>;
        })}
      </div>
      <div className="ra-density-section"><div><strong>Row density</strong><small>Adjust vertical spacing</small></div>
        <ToggleGroup<string> value={preferences.density} ariaLabel="Row density" options={[
          { value: "comfortable", label: "Comfortable" }, { value: "compact", label: "Compact" },
        ]} onValueChange={(v) => { if (v === "comfortable" || v === "compact") onChange((prev) => ({ ...prev, density: v })); }}/>
      </div>
    </div>
    <footer className="ra-table-settings-footer"><button className="ra-reset-settings" type="button"
      onClick={() => onChange(defaultTablePreferences())}><RotateCcw size={14}/> Reset to defaults</button>
      <span>Saved for your account</span>
    </footer>
  </section>;
}
