/** Shared relation picker: edit forms and filters must resolve the same visible label. */
import { useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, buildQuery } from "./api";
import { AsyncSelect, type SelectOption } from "./ui";
import type { FieldDef } from "./types";

export function RelationInput({ field, value, onChange, placeholder }: {
  field: FieldDef; value: unknown; onChange: (value: unknown) => void; placeholder?: string;
}) {
  const resourceId = field.relation!.resource;
  const selected = value == null || value === "" ? null : String(value);
  const selectedLabel = useQuery({
    queryKey: ["options", resourceId, "selected", selected], enabled: selected !== null,
    queryFn: () => api<{ items: SelectOption<string | number>[] }>(
      `/api/resources/${resourceId}/options${buildQuery({ ids: selected! })}`),
  });
  const loadOptions = useCallback(async (q: string) => {
    const response = await api<{ items: SelectOption<string | number>[] }>(
      `/api/resources/${resourceId}/options${buildQuery({ q })}`);
    return response.items;
  }, [resourceId]);
  return <AsyncSelect<string | number> id={`field-${field.name}`} value={selected}
    selectedOptions={selectedLabel.data?.items ?? []} loadOptions={loadOptions}
    placeholder={placeholder ?? (field.nullable ? "None" : "Choose a record")}
    ariaLabel={`Search ${field.label}`} searchable clearable
    onChange={(next) => {
      const raw = Array.isArray(next) ? next[0] : next;
      onChange(raw == null ? null : field.kind === "integer" ? Number(raw) : raw);
    }}/>
}
