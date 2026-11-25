/** Pure, framework-independent filter state transitions and layout heuristics. */
import type { FieldDef } from "./types";

export type FilterOperator = "eq" | "neq" | "contains" | "starts_with" | "ends_with" |
  "gt" | "gte" | "lt" | "lte" | "between" | "in" | "not_in";
export interface FilterState {
  operator?: FilterOperator;
  value?: string;
  from?: string;
  to?: string;
  include?: string[];
  exclude?: string[];
}
export type FilterValues = Record<string, FilterState>;

/** Keep the draft intact when changing a comparison; ranges reuse the scalar value as From. */
export function changeFilterOperator(previous: FilterState, operator: FilterOperator): FilterState {
  if (previous.operator === operator) return previous;
  if (operator === "between") {
    return { ...previous, operator, from: previous.value || previous.from || "", to: previous.to || "" };
  }
  return { ...previous, operator, value: previous.operator === "between"
    ? previous.from || previous.to || previous.value || ""
    : previous.value || previous.from || previous.to || "" };
}

/** Compact by default; explicit SQL constraints refine the width without forcing full columns. */
export function filterControlWidth(field: FieldDef, isRange: boolean): number {
  if (field.filterWidth != null) return Math.max(140, Math.min(560, field.filterWidth));
  const kind = field.kind;
  if (field.relation) return 234;
  if (kind === "enum") return isRange ? 368 : 246;
  if (kind === "boolean") return 164;
  if (kind === "date" || kind === "datetime" || kind === "time") {
    return isRange ? 380 : 214;
  }
  if (kind === "integer" || kind === "number") {
    const digits = field.precision || (field.primaryKey ? 8 : 10);
    const single = Math.min(230, Math.max(158, 110 + digits * 5));
    return isRange ? Math.min(390, Math.max(258, single * 1.7)) : single;
  }
  if (kind === "string") {
    const length = field.maxLength;
    return length != null ? Math.min(320, Math.max(184, 130 + length * 7)) : 236;
  }
  return 218;
}

export function filterOperators(field: FieldDef): FilterOperator[] {
  if (field.filterOperators) return field.filterOperators;
  if (field.relation) return ["eq", "neq"];
  if (field.kind === "enum" || field.kind === "boolean") return ["eq"];
  if (["integer", "number", "date", "datetime", "time"].includes(field.kind))
    return ["eq", "neq", "gt", "gte", "lt", "lte", "between"];
  if (field.kind === "string") return ["eq", "neq", "contains", "starts_with", "ends_with"];
  return ["eq", "neq"];
}

/** Read supported filters from a mount-relative list URL, without trusting unknown fields. */
export function filtersFromSearch(fields: FieldDef[], search: string): FilterValues {
  const values: FilterValues = Object.create(null);
  const params = new URLSearchParams(search);
  for (const field of fields) {
    if (field.views?.filter?.visible === false) continue;
    const operators = filterOperators(field);
    const key = "filter." + field.name;
    const includeExclude = field.kind === "enum" && (operators.includes("in") || operators.includes("not_in"));
    if (includeExclude) {
      const read = (operator: "in" | "not_in"): string[] => {
        const raw = params.get(key + "." + operator);
        if (!raw || !operators.includes(operator)) return [];
        try {
          const items: unknown = JSON.parse(raw);
          return Array.isArray(items) ? items.filter((v): v is string => typeof v === "string") : [];
        } catch { return []; }
      };
      const include = read("in"), exclude = read("not_in");
      if (include.length || exclude.length) values[field.name] = {include,exclude};
      else if (operators.includes("in") && (params.has(key) || params.has(key + ".eq")))
        values[field.name] = {include:[params.get(key + ".eq") ?? params.get(key)!]};
      continue;
    }
    for (const operator of operators) {
      const raw = params.get(key + "." + operator) ?? (operator === "eq" ? params.get(key) : null);
      if (raw === null || raw === "") continue;
      if (operator === "between") {
        try {
          const range = JSON.parse(raw);
          if (typeof range?.from === "string" && typeof range?.to === "string")
            values[field.name] = {operator,from:range.from,to:range.to};
        } catch { /* malformed deep-link range is not applied */ }
      } else if (operator !== "in" && operator !== "not_in") values[field.name] = {operator,value:raw};
      if (Object.hasOwn(values,field.name)) break;
    }
  }
  return values;
}
