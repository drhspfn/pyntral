/** Type-aware filter UI and serialization of SQLAlchemy filter expressions. */
import { useMemo } from "react";
import { fields as customFields } from "virtual:pyntral-extensions";
import { DatePicker, Select, TextInput, type SelectOption } from "./ui";
import { RelationInput } from "./relation";
import { FilterOperatorButton } from "./filter-operator";
import { changeFilterOperator, type FilterOperator, type FilterState, type FilterValues } from "./filter-state";
import type { FieldDef, ResourceDef } from "./types";

export type { FilterOperator, FilterState, FilterValues } from "./filter-state";

export function filterOperators(field: FieldDef): FilterOperator[] {
  if (field.filterOperators) return field.filterOperators;
  if (field.relation) return ["eq", "neq"];
  if (field.kind === "enum" || field.kind === "boolean") return ["eq"];
  if (["integer", "number", "date", "datetime", "time"].includes(field.kind))
    return ["eq", "neq", "gt", "gte", "lt", "lte", "between"];
  if (field.kind === "string") return ["eq", "neq", "contains", "starts_with", "ends_with"];
  return ["eq", "neq"];
}

/** Converts only complete filter expressions; incomplete ranges remain editing drafts. */
export function serializeFilters(fields: FieldDef[], values: FilterValues): Record<string, string> {
  const params: Record<string, string> = {};
  for (const field of fields) {
    const filter = values[field.name];
    if (!filter) continue;
    const supported = filterOperators(field);
    if (field.kind === "enum" && (supported.includes("in") || supported.includes("not_in"))) {
      const include = [...new Set(filter.include || [])];
      const exclude = [...new Set(filter.exclude || [])].filter((entry) => !include.includes(entry));
      if (include.length && supported.includes("in")) params[`filter.${field.name}.in`] = JSON.stringify(include);
      if (exclude.length && supported.includes("not_in")) params[`filter.${field.name}.not_in`] = JSON.stringify(exclude);
      continue;
    }
    const operator = filter.operator && supported.includes(filter.operator) ? filter.operator : supported[0];
    if (!operator) continue;
    if (operator === "between") {
      const start = filter.from, end = filter.to;
      const reversed = start && end && (["number", "integer"].includes(field.kind)
        ? Number(start) > Number(end) : start > end);
      if (start && end && !reversed) params[`filter.${field.name}.between`] = JSON.stringify({ from: start, to: end });
    } else if (filter.value !== undefined && filter.value !== "") {
      params[`filter.${field.name}.${operator}`] = filter.value;
    }
  }
  return params;
}

function FilterValueControl({ field, value, onChange, placeholder, ariaLabel }: {
  field: FieldDef; value: string; onChange: (next: string) => void; placeholder?: string;
  ariaLabel?: string;
}) {
  if (field.relation) return <RelationInput field={field} value={value || null}
    placeholder={placeholder ?? "Search related records…"}
    onChange={(next) => onChange(next == null ? "" : String(next))}/>;
  if (field.kind === "boolean") return <Select<string> value={value || null} searchable={false}
    ariaLabel={ariaLabel}
    onChange={(next) => onChange(String(next ?? ""))} clearable placeholder="True / False"
    options={[{ label: "True", value: "true" }, { label: "False", value: "false" }]}/>;
  if (field.kind === "date" || field.kind === "datetime") return <DatePicker
    ariaLabel={ariaLabel}
    value={value || null} onChange={(next) => onChange(next ?? "")}
    includeTime={field.kind === "datetime"} placeholder={placeholder ?? "Choose a date…"}/>;
  if (field.kind === "time") return <TextInput type="time" value={value} aria-label={ariaLabel}
    onChange={(event) => onChange(event.target.value)} />;
  if (field.kind === "enum") {
    const options: SelectOption<string>[] = (field.options || []).map((option) =>
      typeof option === "string" ? { label: option, value: option } :
        { label: option.label, value: String(option.value) });
    return <Select<string> value={value || null} options={options} onChange={(next) => onChange(String(next ?? ""))}
      ariaLabel={ariaLabel}
      placeholder="Select a value" clearable />;
  }
  const number = field.kind === "integer" || field.kind === "number";
  return <TextInput type={number ? "number" : "text"}
    aria-label={ariaLabel}
    step={field.kind === "integer" ? "1" : field.kind === "number" ? "any" : undefined}
    maxLength={!number && field.kind === "string" ? field.maxLength ?? undefined : undefined}
    placeholder={placeholder ?? (number ? "Number…" : "Type a value…")}
    value={value} onChange={(event) => onChange(event.target.value)}/>;
}

function MultiEnumFilter({ field, value, onChange }: {
  field: FieldDef; value: FilterState; onChange: (next: FilterState) => void;
}) {
  const options = useMemo<SelectOption<string>[]>(() => (field.options || []).map((o) =>
    typeof o === "string" ? { label: o, value: o } : { label: o.label, value: String(o.value) }), [field.options]);
  const include = value.include || [], exclude = value.exclude || [];
  const operators = filterOperators(field);
  return <div className="ra-enum-filter">
    {operators.includes("in") && <div className="ra-enum-filter-item">
      <span>Include</span>
      <Select<string> multiple searchable value={include} placeholder="Include any…"
        options={options}
        selectedOptions={options.filter((o) => include.includes(o.value))}
        onChange={(next) => {
          const selected = Array.isArray(next) ? next : [];
          onChange({ ...value, include: selected, exclude: exclude.filter((item) => !selected.includes(item)) });
        }}/>
    </div>}
    {operators.includes("not_in") && <div className="ra-enum-filter-item">
      <span>Exclude</span>
      <Select<string> multiple searchable value={exclude} placeholder="Exclude any…"
        options={options.filter((o) => !include.includes(o.value))}
        selectedOptions={options.filter((o) => exclude.includes(o.value))}
        onChange={(next) => {
          const selected = Array.isArray(next) ? next : [];
          onChange({ ...value, exclude: selected, include: include.filter((item) => !selected.includes(item)) });
        }}/>
    </div>}
  </div>;
}

export function AdvancedFilterField({ field, resource, value, onChange, navigate }: {
  field: FieldDef; resource: ResourceDef; value: FilterState;
  onChange: (next: FilterState) => void; navigate: (route: string) => void;
}) {
  const Custom = customFields[field.components.filter || field.components.edit || ""];
  if (Custom) return <Custom field={field} resource={resource} record={{}} mode="filter" navigate={navigate}
    value={value.value || null} onChange={(next) => onChange({ ...value, value: next == null ? "" : String(next) })}/>;
  const operators = filterOperators(field);
  if (!operators.length) return null;
  if (field.kind === "enum" && operators.includes("in") && operators.includes("not_in"))
    return <MultiEnumFilter field={field} value={value} onChange={onChange}/>;
  const operator = value.operator && operators.includes(value.operator) ? value.operator : operators[0];
  const showOperator = operators.length > 1;
  const between = operator === "between";
  const reversedRange = between && value.from && value.to && (["number", "integer"].includes(field.kind)
    ? Number(value.from) > Number(value.to) : value.from > value.to);
  return <div className={`ra-filter-editor ${between ? "ra-filter-between" : ""}`}>
    <div className="ra-filter-combo">
      <div className="ra-filter-combo-main">
        {between ? <div className="ra-filter-range">
          <div className="ra-filter-range-input"><span>From</span>
            <FilterValueControl field={field} value={value.from || ""} placeholder="Min" ariaLabel={`${field.label} from`}
              onChange={(next) => onChange({ ...value, operator, from: next })}/></div>
          <div className="ra-filter-range-input"><span>To</span>
            <FilterValueControl field={field} value={value.to || ""} placeholder="Max" ariaLabel={`${field.label} to`}
              onChange={(next) => onChange({ ...value, operator, to: next })}/></div>
        </div> : <FilterValueControl field={field} value={value.value || ""} ariaLabel={field.label}
          onChange={(next) => onChange({ ...value, operator, value: next })}/>}
      </div>
      {showOperator && <FilterOperatorButton label={field.label} operator={operator} operators={operators}
        onChange={(next) => onChange(changeFilterOperator(value, next))}/>}
    </div>
    {reversedRange && <span className="ra-filter-error" role="alert">From must not exceed To.</span>}
  </div>;
}
