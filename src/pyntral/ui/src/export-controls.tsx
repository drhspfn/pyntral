/** Bounded, permission-checked table export; the server revalidates every query. */
import { useState } from "react";
import { Download } from "lucide-react";
import { base } from "./api";
import { useAdminFeedback } from "./feedback";
import { orderedColumns, type TablePreferences } from "./table-prefs";
import type { ResourceDef } from "./types";
import { Select, TextInput, Popover, PopoverTrigger, PopoverContent, PopoverHeader, PopoverFooter } from "./ui";

type Scope = "page" | "filtered" | "range";
type Format = "csv" | "json";

export function ExportControls({ resource, query, offset, total, pageRows, preferences }: {
  resource: ResourceDef; query: string; offset: number; total: number;
  pageRows: number; preferences: TablePreferences;
}) {
  const { toast } = useAdminFeedback();
  const [open, setOpen] = useState(false);
  const [scope, setScope] = useState<Scope>("page");
  const [format, setFormat] = useState<Format>("csv");
  const [columns, setColumns] = useState<"visible" | "all">("visible");
  const [start, setStart] = useState("0");
  const [count, setCount] = useState("1000");
  const [working, setWorking] = useState(false);

  const requestedOffset = scope === "page" ? offset : scope === "filtered" ? 0 : Number(start);
  const requestedLimit = scope === "page" ? pageRows :
    scope === "filtered" ? Math.min(total, 10000) : Number(count);
  const validRange = Number.isSafeInteger(requestedOffset) && requestedOffset >= 0 &&
    Number.isSafeInteger(requestedLimit) && requestedLimit > 0 && requestedLimit <= 10000;
  const rows = validRange ? Math.min(requestedLimit, Math.max(0, total - requestedOffset)) : 0;
  const visibleColumns = orderedColumns(resource.listFields, preferences);
  const selectedColumns = columns === "visible" ? visibleColumns : resource.listFields;

  const download = async () => {
    if (!rows || !validRange || !selectedColumns.length || working) return;
    setWorking(true);
    try {
      const params = new URLSearchParams(query.startsWith("?") ? query.slice(1) : query);
      params.set("format", format);
      params.set("offset", String(requestedOffset));
      params.set("limit", String(requestedLimit));
      params.set("columns", selectedColumns.join(","));
      const response = await fetch(base + `/api/resources/${encodeURIComponent(resource.id)}/export?${params}`,
        { credentials: "same-origin" });
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error?.error?.message || `Export failed (HTTP ${response.status})`);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${resource.id}-export.${format}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast(`Exported ${response.headers.get("X-Export-Rows") ?? rows} records`, { kind: "success" });
      setOpen(false);
    } catch (error) {
      toast(error instanceof Error ? error.message : "Unable to export records", { kind: "error" });
    } finally {
      setWorking(false);
    }
  };

  return <Popover open={open} onOpenChange={setOpen}>
    <PopoverTrigger asChild><button type="button" className="btn subtle"><Download size={15}/> Export</button></PopoverTrigger>
    <PopoverContent width={425} minHeight={250} maxHeight={560} className="ra-export-panel">
      <PopoverHeader><h3>Export records</h3></PopoverHeader>
      <div className="ra-export-field"><span className="ra-export-label">Format</span>
        <Select<Format> value={format} searchable={false} clearable={false}
          onChange={v => { if (typeof v === "string") setFormat(v as Format); }}
          options={[{ value: "csv", label: "CSV" }, { value: "json", label: "JSON" }]}/>
      </div>
      <div className="ra-export-field"><span className="ra-export-label">Rows</span>
        <Select<Scope> value={scope} searchable={false} clearable={false}
          onChange={v => { if (typeof v === "string") setScope(v as Scope); }}
          options={[{ value: "page", label: "Current page" },
            { value: "filtered", label: "All filtered (max 10,000)" },
            { value: "range", label: "Custom range" }]}/>
      </div>
      {scope === "range" && <div className="ra-export-range">
        <label>Skip rows<TextInput type="number" min={0} step={1} value={start}
          onChange={event => setStart(event.target.value)}/></label>
        <label>Take rows<TextInput type="number" min={1} max={10000} step={1} value={count}
          onChange={event => setCount(event.target.value)}/></label>
      </div>}
      <div className="ra-export-field"><span className="ra-export-label">Columns</span>
        <Select<"visible" | "all"> value={columns} searchable={false} clearable={false}
          onChange={v => { if (typeof v === "string") setColumns(v as "visible" | "all"); }}
          options={[{ value: "visible", label: "Only visible columns (in table order)" },
            { value: "all", label: "All available list columns" }]}/>
      </div>
      <p aria-live="polite">{rows} of {total} matching rows · {selectedColumns.length} columns
        {scope === "filtered" && total > 10000 ? " · Limited to first 10,000" : ""}</p>
      <PopoverFooter><button type="button" className="btn primary" disabled={!rows || !selectedColumns.length || working}
        onClick={() => { void download(); }}>{working ? "Exporting…" : `Download ${rows} rows`}</button></PopoverFooter>
    </PopoverContent>
  </Popover>;
}
