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
