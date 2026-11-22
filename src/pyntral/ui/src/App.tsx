import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type FormEvent, type ReactNode, type ComponentType } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity, ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Boxes,
  ChevronLeft, ChevronRight, CircleAlert, Command, Database, ExternalLink, Filter,
  LayoutDashboard, LoaderCircle, LockKeyhole, LogOut, Menu, MoreHorizontal, Pencil,
  Plus, RefreshCw, Settings2, ShieldCheck, Trash2, Sun, Moon,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { fields as customFields, pages as customPages, actions as customActions, dialogs as customDialogs, crud as customCrud, themes as customThemes, profile as customProfile, auth as customAuth } from "virtual:pyntral-extensions";
import { SidebarNavigation } from "./navigation";
import { AdminFeedbackProvider, useAdminFeedback } from "./feedback";
import { useDeleteRecord, invalidateResource, type Listing } from "./mutations";
import { AsyncSelect, Checkbox, DatePicker, FormField, SearchInput, Select, TextInput, Textarea,
  type SelectOption } from "./ui";
import { RelationInput } from "./relation";
import { AdvancedFilterField, serializeFilters, filterOperators, type FilterValues } from "./filters";
import { filterControlWidth } from "./filter-state";
import { applyTheme, resolveMode } from "./theme";
import { CurrentAdminProvider, useCurrentAdmin } from "./currentAdmin";
import { I18nProvider, useI18n } from "./i18n";
import { defaultTablePreferences, parseTablePreferences, orderedColumns, type TablePreferences } from "./table-prefs";
import { TableSettings } from "./table-settings";
import { Popover, PopoverTrigger, PopoverContent } from "./popover-component";
import { ExportControls } from "./export-controls";
import { mayLeavePage, registerNavigationBlocker } from "./navigation-guard";
import { api, base, buildQuery, getAuth, setCsrf } from "./api";
import type {
  ActionDef, AuthState, CustomFieldProps, CustomCrudProps, CustomCollectionActionProps, FieldDef, JobDef, RecordData, ResourceDef, Schema, ThemeMode,
} from "./types";
import { viewFields } from "./types";

const customProfileMenu = customProfile.menu;
const ProfileMenuExtension = customProfile.menu;

const icons: Record<string, LucideIcon> = {
  database: Database, "layout-dashboard": LayoutDashboard, boxes: Boxes,
  activity: Activity, "shield-check": ShieldCheck, "settings-2": Settings2,
};

function useNavigation() {
  const [url, setUrl] = useState(() => window.location.pathname);
  const locationRef = useRef(window.location.pathname);
  const navigatingRef = useRef(false);
  useEffect(() => {
    const onPopState = () => {
      const destination = window.location.pathname;
      const previous = locationRef.current;
      if (destination === previous) return;
      // Restore the displayed URL until the discard confirmation resolves.
      history.pushState(null, "", previous);
      if (navigatingRef.current) return;
      navigatingRef.current = true;
      void mayLeavePage().then((allowed) => {
        if (!allowed) return;
        history.replaceState(null, "", destination);
        locationRef.current = destination;
        setUrl(destination);
        window.scrollTo(0, 0);
      }).finally(() => { navigatingRef.current = false; });
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);
  const navigate = useCallback((route: string) => {
    const full = `${base}/${route.replace(/^\//, "")}`.replace(/\/$/, "/");
    if (full === locationRef.current || navigatingRef.current) return;
    navigatingRef.current = true;
    void mayLeavePage().then((allowed) => {
      if (!allowed) return;
      history.pushState(null, "", full);
      locationRef.current = full;
      setUrl(full);
      window.scrollTo(0, 0);
    }).finally(() => { navigatingRef.current = false; });
  }, []);
  return { route: url.startsWith(base) ? url.slice(base.length).replace(/^\//, "") : "", navigate };
}

function Loading({ label = "Loading…" }: { label?: string }) {
  return <div className="loading"><LoaderCircle className="spin" size={20} /><span>{label}</span></div>;
}
function Alert({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : "An unexpected error occurred";
  return <div className="alert" role="alert"><CircleAlert size={17} /><span>{message}</span></div>;
}
function Empty({ title, description }: { title: string; description?: string }) {
  return <div className="empty"><div className="empty-icon"><Boxes size={25} /></div>
    <strong>{title}</strong>{description && <p>{description}</p>}</div>;
}
function pretty(value: unknown, kind?: string): ReactNode {
  if (value === null || value === undefined || value === "") return <span className="muted">—</span>;
  if (typeof value === "boolean") return <span className={`pill ${value ? "positive" : "quiet"}`}>
    <span className="pill-dot" />{value ? "Active" : "Inactive"}</span>;
  if (kind === "datetime" || kind === "date") {
    const date = new Date(String(value));
    return isNaN(date.getTime()) ? String(value) : date.toLocaleString(undefined,
      kind === "date" ? { dateStyle: "medium" } : { dateStyle: "medium", timeStyle: "short" });
  }
  if (typeof value === "object") return <code className="table-code">{JSON.stringify(value)}</code>;
  return String(value);
}
function FieldValue({ resource, field, value, record, mode }: {
  resource: ResourceDef; field: FieldDef; value: unknown; record: RecordData;
  mode: "list" | "show";
}) {
  const custom = field.components[mode];
  const Comp = custom ? customFields[custom] : undefined;
  if (Comp) return <Comp field={field} value={value} record={record} resource={resource} mode={mode} />;
  return <>{pretty(value, field.kind)}</>;
}

function Login({ onSignedIn }: { onSignedIn: (state: AuthState) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const login = useMutation({
    mutationFn: () => api<AuthState>("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
    onSuccess: (state) => { setCsrf(state.csrf); onSignedIn(state); },
  });
  return <div className="login-page">
    <div className="login-side">
      <div className="brand"><div className="brand-mark"><Command size={23} /></div><strong>Pyntral</strong></div>
      <div className="login-side-content"><div className="eyebrow">BUILT FOR BUILDERS</div>
        <h1>Everything under<br /><em>your control.</em></h1>
        <p>Manage your data, shape your workflows, and move faster with an admin interface built around your models.</p>
        <div className="login-mini"><ShieldCheck size={17} /> Secure workspace · Powered by Python + React</div>
      </div><div className="login-side-footer">Pyntral / 0.1.0b1</div>
    </div>
    <div className="login-panel"><form className="login-form" onSubmit={(e) => { e.preventDefault(); login.mutate(); }}>
      <div className="login-icon"><LockKeyhole size={24} /></div>
      <div className="eyebrow">WELCOME BACK</div>
      <h2>Sign in to your workspace</h2>
      <p className="login-subtitle">Use your administrator account to continue.</p>
      {login.error && <Alert error={login.error} />}
      <label htmlFor="username">Username</label>
      <input id="username" autoComplete="username" autoFocus required value={username}
        onChange={(e) => setUsername(e.target.value)} placeholder="Your username" />
      <label htmlFor="password">Password</label>
      <input id="password" type="password" autoComplete="current-password" required
        value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
      <button className="btn primary login-submit" type="submit" disabled={login.isPending}>
        {login.isPending ? <LoaderCircle className="spin" size={17} /> : <>Continue <ArrowRight size={17} /></>}
      </button>
      <div className="login-note"><ShieldCheck size={15} /> Protected by signed sessions and CSRF validation</div>
    </form></div>
  </div>;
}

function Overview({ schema, navigate }: { schema: Schema; navigate: (route: string) => void }) {
  const { t } = useI18n();
  return <>
    <div className="page-heading"><div><h1>{t("nav.overview", "Overview")}</h1><p>{schema.title}</p></div></div>
    <div className="section-head"><h2>Resources</h2></div>
    {schema.resources.some((r) => r.capabilities.list) ? <div className="resource-grid">
      {schema.resources.filter((r) => r.capabilities.list).map((resource) => {
        const Icon = icons[resource.icon] || Database;
        return <button key={resource.id} className="resource-card" onClick={() => navigate(`resources/${resource.id}`)}>
          <div className="resource-icon"><Icon size={18}/></div><strong>{resource.label}</strong>
          <ArrowRight size={15}/>
        </button>;
      })}
    </div> : <Empty title="No resources" description="Register a SQLAlchemy resource to begin."/>}
  </>;
}

function RecordAction({ resource, record, action, navigate }: {
  resource: ResourceDef; record: RecordData; action: ActionDef;
  navigate: (route: string) => void;
}) {
  const client = useQueryClient();
  const feedback = useAdminFeedback();
  const DialogContent = action.dialog ? customDialogs[action.dialog] : undefined;
  const id = encodeURIComponent(String(record[resource.primaryKey]));
  const execute = useMutation({ mutationFn: () => api<{ result: unknown }>(
    `/api/resources/${resource.id}/${id}/actions/${action.name}`,
    { method: "POST", body: JSON.stringify({}) }),
    onSuccess: async () => {
      await invalidateResource(client, resource.id);
      feedback.toast(`${action.label} completed`, { kind: "success" });
    },
    onError: (reason: unknown) => feedback.toast(reason instanceof Error ? reason.message : "Action failed", { kind: "error" }),
  });
  const click = () => {
    if (action.component) { navigate(`resources/${resource.id}/${id}/actions/${action.name}`); return; }
    if (action.confirmation || DialogContent) {
      void feedback.confirm({ title: action.label, message: action.confirmation ?? undefined,
        content: DialogContent ? <DialogContent resource={resource} record={record} action={action}/> : undefined,
        confirmLabel: "Continue", destructive: action.variant === "danger" })
        .then((ok) => { if (ok) execute.mutate(); });
      return;
    }
    execute.mutate();
  };
  const style = action.appearance === "badge" ? "action-badge" : "action-button";
  return <span className="action-wrapper">
    {action.appearance === "menu" ? <details className="record-action-menu"><summary title={action.label}><MoreHorizontal size={16}/></summary>
      <button type="button" onClick={(e) => { e.currentTarget.closest("details")?.removeAttribute("open"); click(); }}>{action.label}</button>
    </details> : <button type="button" className={`${style} ${action.variant === "danger" ? "danger-text" : ""}`}
      disabled={execute.isPending} onClick={click} title={action.label}>
      {execute.isPending ? <LoaderCircle size={13} className="spin"/> : null}{action.label}</button>}
  </span>;
}

function TableContent({ resource, data, navigate, selectable = false, selection = [], onSelectionChange, preferences }: { resource: ResourceDef; data: Listing;
  navigate: (route: string) => void; selectable?: boolean; selection?: string[];
  onSelectionChange?: (selected: string[]) => void; preferences?: TablePreferences;
}) {
  const names = preferences ? orderedColumns(resource.listFields, preferences) : resource.listFields;
  const columns = viewFields(resource.fields, "list").filter((field) => names.includes(field.name))
    .sort((a, b) => names.indexOf(a.name) - names.indexOf(b.name));
  const { requestDelete } = useDeleteRecord(resource);
  const keys = data.items.map((row) => String(row[resource.primaryKey]));
  return <div className={preferences?.density === "compact" ? "ra-table-compact" : ""}
    style={{ "--ra-pin-left": selectable ? "46px" : "0px" } as CSSProperties}>
    <div className="table-scroll"><table className="data-table"><thead><tr>
    {selectable && <th className="ra-select-cell"><Checkbox aria-label="Select all visible records"
      checked={keys.length > 0 && keys.every((key) => selection.includes(key))}
      indeterminate={keys.some((key) => selection.includes(key)) && !keys.every((key) => selection.includes(key))}
      onCheckedChange={(checked) => onSelectionChange?.(checked ? Array.from(new Set([...selection, ...keys])) : selection.filter((key) => !keys.includes(key)))}/></th>}
    {columns.map((field) => <th key={field.name} className={preferences?.pinned === field.name ? "ra-column-pinned" : ""}>
      {field.label}</th>)}<th className="actions-head">ACTION</th>
  </tr></thead><tbody>
    {data.items.map((row) => <tr key={String(row[resource.primaryKey])}>
      {selectable && <td className="ra-select-cell"><Checkbox aria-label={`Select record ${String(row[resource.primaryKey])}`}
        checked={selection.includes(String(row[resource.primaryKey]))} onCheckedChange={(checked) => {
          const key = String(row[resource.primaryKey]);
          onSelectionChange?.(checked ? Array.from(new Set([...selection, key])) : selection.filter((value) => value !== key));
        }}/></td>}
      {columns.map((field, idx) => <td key={field.name}
        className={`${idx === 0 ? "strong-cell" : ""} ${preferences?.pinned === field.name ? "ra-column-pinned" : ""}`}>
        {idx === 0 && resource.capabilities.show ? <button className="cell-link" onClick={() => navigate(`resources/${resource.id}/${encodeURIComponent(String(row[resource.primaryKey]))}`)}>
          <FieldValue resource={resource} field={field} value={row[field.name]} record={row} mode="list" /></button> :
          <FieldValue resource={resource} field={field} value={row[field.name]} record={row} mode="list" />}
      </td>)}
      <td className="actions-cell"><div className="row-actions">
        {resource.capabilities.show && <button title="View" aria-label="View record" onClick={() => navigate(`resources/${resource.id}/${encodeURIComponent(String(row[resource.primaryKey]))}`)}><ExternalLink size={16}/></button>}
        {resource.capabilities.edit && <button title="Edit" aria-label="Edit record" onClick={() => navigate(`resources/${resource.id}/${encodeURIComponent(String(row[resource.primaryKey]))}/edit`)}><Pencil size={15}/></button>}
        {resource.capabilities.delete && <button type="button" title="Delete" aria-label="Delete record"
          onClick={() => { void requestDelete(row[resource.primaryKey], resource.versionField ? row[resource.versionField] : undefined); }}><Trash2 size={15}/></button>}
        {resource.actions.filter((a) => (a.kind ?? "record") === "record" && a.position !== "detail" && (data.actionsByRecord?.[String(row[resource.primaryKey])] || []).includes(a.name))
          .map((action) => <RecordAction key={action.name} resource={resource} record={row} action={action} navigate={navigate}/>)}
      </div></td>
    </tr>)}
  </tbody></table></div></div>;
}
function Pager({ offset, total, limit, onOffset }: { offset: number; total: number; limit: number; onOffset: (n: number) => void }) {
  return <div className="pager"><span>Showing <strong>{total === 0 ? 0 : offset + 1}–{Math.min(offset + limit, total)}</strong> of <strong>{total}</strong> records</span>
    <div className="pager-actions"><button disabled={offset === 0} title="Previous page" onClick={() => onOffset(Math.max(0, offset - limit))}><ChevronLeft size={18} /></button>
      <span>{Math.floor(offset / limit) + 1} / {Math.max(1, Math.ceil(total / limit))}</span>
      <button disabled={offset + limit >= total} title="Next page" onClick={() => onOffset(offset + limit)}><ChevronRight size={18} /></button></div></div>;
}

/** Scoped resource/bulk commands. No client-side trust in selected IDs. */
function CollectionAction({ schema, resource, action, selected, navigate, clearSelection }: {
  schema: Schema; resource: ResourceDef; action: ActionDef; selected: string[];
  navigate: (route: string) => void; clearSelection: () => void;
}) {
  const feedback = useAdminFeedback();
  const client = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const bulk = action.kind === "bulk";
  const invoke = async (payload: RecordData = {}) => {
    const body = bulk ? { ...payload, ids: selected } : payload;
    const result = await api<{ result: unknown }>(`/api/resources/${resource.id}/actions/${action.name}`,
      { method: "POST", body: JSON.stringify(body) });
    await invalidateResource(client, resource.id);
    clearSelection();
    feedback.toast(`${action.label} completed`, { kind: "success" });
    setExpanded(false);
    return result.result;
  };
  const Custom = action.component
    ? (customActions[action.component] as unknown as ComponentType<CustomCollectionActionProps>)
    : undefined;
  const run = async () => {
    if (Custom) { setExpanded((previous) => !previous); return; }
    if (action.confirmation && !await feedback.confirm({ title: action.label,
      message: action.confirmation, destructive: action.variant === "danger" })) return;
    try { await invoke(); }
    catch (error) { feedback.toast(error instanceof Error ? error.message : "Action failed", { kind: "error" }); }
  };
  return <div className="ra-collection-action">
    <button type="button" className={`btn ${action.variant === "danger" ? "danger" : "subtle"}`}
      disabled={bulk && selected.length === 0} onClick={() => { void run(); }}>{action.label}</button>
    {expanded && Custom && <div className="surface ra-collection-panel">
      <button type="button" className="btn subtle" onClick={() => setExpanded(false)}>Close</button>
      <Custom schema={schema} resource={resource} action={action} selectedIds={selected}
        navigate={navigate} invoke={invoke}/>
    </div>}
  </div>;
}

interface BackgroundJobState {
  id: string; status: "queued" | "running" | "completed" | "failed" | "cancelled" | "timed_out";
  progress: number; message: string; cancellable: boolean;
}

function BackgroundJobButton({ resource, job }: { resource: ResourceDef; job: JobDef }) {
  const feedback = useAdminFeedback();
  const [jobId, setJobId] = useState<string | null>(null);
  const details = useQuery({
    queryKey: ["job", jobId], enabled: jobId !== null,
    queryFn: () => api<{ job: BackgroundJobState }>(`/api/jobs/${encodeURIComponent(jobId!)}`),
    refetchInterval: (query) => ["queued", "running"].includes(query.state.data?.job.status ?? "") ? 800 : false,
  });
  const start = useMutation({
    mutationFn: () => api<{ job: BackgroundJobState }>(
      `/api/resources/${resource.id}/jobs/${encodeURIComponent(job.name)}`,
      { method: "POST", body: JSON.stringify({}) }),
    onSuccess: (data) => { setJobId(data.job.id); feedback.toast(`${job.label} started`, { kind: "info" }); },
    onError: (error: unknown) => feedback.toast(error instanceof Error ? error.message : "Could not start job", { kind: "error" }),
  });
  const cancel = useMutation({
    mutationFn: () => api(`/api/jobs/${encodeURIComponent(jobId!)}`, { method: "DELETE" }),
    onSuccess: () => { void details.refetch(); feedback.toast("Cancellation requested", { kind: "info" }); },
    onError: (error: unknown) => feedback.toast(error instanceof Error ? error.message : "Could not cancel job", { kind: "error" }),
  });
  const status = details.data?.job;
  const running = status?.status === "queued" || status?.status === "running";
  return <div className="ra-background-job">
    <button type="button" className="btn subtle" disabled={start.isPending || running}
      onClick={() => { void (async () => {
        if (job.confirmation && !await feedback.confirm({ title: job.label, message: job.confirmation })) return;
        start.mutate();
      })(); }}>{start.isPending ? "Starting…" : job.label}</button>
    {status && <div className="ra-job-status" role="status" aria-live="polite">
      <span>{status.status}: {status.progress}%{status.message ? ` — ${status.message}` : ""}</span>
      <progress aria-label={`${job.label} progress`} max={100} value={status.progress}/>
      {running && status.cancellable && <button type="button" className="btn subtle"
        disabled={cancel.isPending} onClick={() => cancel.mutate()}>Cancel</button>}
    </div>}
    {details.error && <span role="alert">Unable to load job progress</span>}
  </div>;
}

function ResourceList({ resource, navigate, schema }: { resource: ResourceDef; schema: Schema; navigate: (route: string) => void }) {
  const { t } = useI18n();
  const [text, setText] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [sort, setSort] = useState(resource.primaryKey);
  const [desc, setDesc] = useState(true);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [selection, setSelection] = useState<string[]>([]);
  const admin = useCurrentAdmin();
  const prefKey = `pyntral:table:${admin.id}:${resource.id}`;
  const [preferences, setPreferences] = useState<TablePreferences>(() => {
    try { return parseTablePreferences(JSON.parse(localStorage.getItem(prefKey) || "null"), resource.listFields); }
    catch { return defaultTablePreferences(); }
  });
  const [columnsOpen, setColumnsOpen] = useState(false);

  const [presetName, setPresetName] = useState("");
  useEffect(() => { try { localStorage.setItem(prefKey, JSON.stringify(preferences)); } catch { /* storage may be disabled */ } }, [prefKey, preferences]);
  const [filters, setFilters] = useState<FilterValues>({});
  const [appliedFilters, setAppliedFilters] = useState<FilterValues>({});
  const activeFilterCount = Object.keys(serializeFilters(resource.fields, filters)).length;
  useEffect(() => { const t = setTimeout(() => { setSearch(text); setOffset(0); }, 260); return () => clearTimeout(t); }, [text]);
  useEffect(() => { const t = setTimeout(() => setAppliedFilters(filters), 240); return () => clearTimeout(t); }, [filters]);
  const query = buildQuery({ offset, limit: resource.pageSize,
    q: resource.showSearch ? search : undefined, sort, desc,
    ...serializeFilters(resource.fields, appliedFilters) });
  const selectionScope = JSON.stringify({ q: search, filters: appliedFilters });
  useEffect(() => setSelection([]), [selectionScope, resource.id]);
  const records = useQuery({ queryKey: ["list", resource.id, query],
    queryFn: () => api<Listing>(`/api/resources/${resource.id}${query}`) });
  return <>
    <div className="page-heading"><div><div className="eyebrow">DATA / {resource.id.toUpperCase()}</div>
      <h1>{resource.label}</h1><p>{t("resources.description", "View, organize, and manage your records.")}</p></div>
      <div className="heading-actions">
        {(resource.jobs ?? []).map((job) => <BackgroundJobButton key={job.name} resource={resource} job={job}/>)}
        {resource.actions.filter((action) => action.kind === "resource").map((action) =>
          <CollectionAction key={action.name} schema={schema} resource={resource} action={action}
            selected={[]} navigate={navigate} clearSelection={() => undefined}/>)}
        {resource.capabilities.create && <button className="btn primary" onClick={() => navigate(`resources/${resource.id}/new`)}><Plus size={17}/> {t("actions.new", "New record")}</button>}
      </div>
    </div>
    <div className="surface ra-table-surface">
      <div className="table-toolbar">
        {resource.showSearch && <SearchInput value={text} onChange={setText}
          className="ra-list-search" aria-label="Search records"
          placeholder={resource.searchFields.length ? `Search ${resource.label.toLowerCase()}…` : "Search not configured"}
          disabled={!resource.searchFields.length} />}
        <div className="toolbar-buttons"><ExportControls resource={resource} query={query} offset={offset}
          total={records.data?.total ?? 0} pageRows={records.data?.items.length ?? 0} preferences={preferences}/>
          <Popover open={columnsOpen} onOpenChange={setColumnsOpen}>
            <PopoverTrigger asChild><button className={"btn subtle " + (columnsOpen ? "selected" : "")}
              type="button" title="Table columns and density">{t("table.columns", "Columns")}</button></PopoverTrigger>
            <PopoverContent width={455} maxHeight={610} minHeight={240} padded={false} className="ra-columns-popover">
              <TableSettings columns={resource.listFields.map((name) => ({
                name, label: resource.fields.find((field) => field.name === name)?.label ?? name,
              }))} preferences={preferences} onChange={setPreferences} onClose={() => setColumnsOpen(false)}/>
            </PopoverContent>
          </Popover>
          <Popover open={filtersOpen} onOpenChange={setFiltersOpen}>
            <PopoverTrigger asChild><button className={`btn subtle ra-filter-toggle ${filtersOpen ? "selected" : ""}`} type="button">
              <Filter size={16}/> {t("table.filters", "Filters")}
              <span className={`ra-filter-count ${activeFilterCount === 0 ? "is-empty" : ""}`} aria-hidden={activeFilterCount === 0}>{activeFilterCount || "0"}</span>
            </button></PopoverTrigger>
            <PopoverContent width={620} maxHeight={650} minHeight={260} padded={false} className="ra-filters-popover">
              <div className="filters-panel">
        <div className="ra-filter-heading"><span className="filter-caption">REFINE RESULTS</span>
          <span className="ra-filter-hint">Choose a comparison using the icon beside each field</span></div>
        <div className="filters-fields">{viewFields(resource.fields, "filter").filter((f) => filterOperators(f).length > 0).map((field) =>
          <div className={`ra-filter-field ${Object.keys(serializeFilters([field], { [field.name]: filters[field.name] || {} })).length ? "is-active" : ""}`}
            key={field.name} style={{ "--ra-filter-width": `${filterControlWidth(field,
              filters[field.name]?.operator === "between" ||
              (field.kind === "enum" && filterOperators(field).includes("in") && filterOperators(field).includes("not_in")))}px` } as CSSProperties}>
            <span className="ra-filter-label">{field.label}</span>
            <AdvancedFilterField field={field} resource={resource} value={filters[field.name] || {}}
              onChange={(value) => { setFilters((old) => ({ ...old, [field.name]: value })); setOffset(0); }}/>
          </div>)}</div>
        <button className="link-btn" onClick={() => setFilters({})}>{t("table.clear_filters", "Clear filters")}</button>
        <div className="ra-filter-presets">
          <div className="ra-filter-preset-select">
            <span className="ra-filter-preset-label">Saved filters</span>
            <Select<string> ariaLabel="Load saved filters" searchable clearable
              placeholder="Choose preset…" value={null}
              onChange={(value) => {
                if (typeof value !== "string") return;
                const saved = preferences.presets[value];
                if (saved) { setFilters(saved as FilterValues); setOffset(0); }
              }}
              options={Object.keys(preferences.presets).map((name) => ({ value: name, label: name }))}/>
          </div>
          <div className="ra-filter-preset-name">
            <TextInput aria-label="Preset name" placeholder="Preset name" value={presetName}
              onChange={event => setPresetName(event.target.value)} maxLength={30}/>
          </div>
          <button type="button" className="btn subtle ra-filter-preset-save"
            disabled={!presetName.trim() || Object.keys(preferences.presets).length >= 10}
            onClick={() => { const name = presetName.trim(); if (!name) return;
              setPreferences(prev => ({ ...prev, presets: {...prev.presets, [name]: filters} })); setPresetName(""); }}>Save preset</button>
        </div>
      </div>
            </PopoverContent>
          </Popover>
          <button className="btn subtle" onClick={() => records.refetch()} title="Refresh"><RefreshCw size={16}/></button></div>
      </div>
      <div className="sortbar"><span>{records.data ? `${records.data.total} total records` : "Records"}</span>
        <div className="sort-controls">{t("table.sort_by", "Sort by")} <div className="ra-sort-select"><Select searchable={false} clearable={false} ariaLabel="Sort column" value={sort}
          onChange={(value) => { if (typeof value === "string") setSort(value); }}
          options={viewFields(resource.fields, "list").filter((field) => field.sortable !== false)
            .map((field) => ({ value: field.name, label: field.label }))}/></div>
          <button title="Toggle sort order" onClick={() => setDesc(!desc)}>{desc ? <ArrowDown size={16}/> : <ArrowUp size={16}/>}</button></div></div>
      {!!resource.actions.some((action) => action.kind === "bulk") && <div className="ra-bulk-bar" aria-live="polite">
        <span>{selection.length} selected</span>
        {resource.actions.filter((action) => action.kind === "bulk").map((action) =>
          <CollectionAction key={action.name} schema={schema} resource={resource} action={action}
            selected={selection} navigate={navigate} clearSelection={() => setSelection([])}/>)}
      </div>}
      {records.isLoading ? <Loading label="Loading records…" /> : records.error ? <Alert error={records.error} /> :
        records.data?.items.length ? <><TableContent resource={resource} data={records.data} navigate={navigate}
            selectable={resource.actions.some((action) => action.kind === "bulk")}
            selection={selection} onSelectionChange={setSelection} preferences={preferences}/>
          <Pager offset={offset} total={records.data.total} limit={resource.pageSize} onOffset={setOffset}/></> :
        <Empty title="No records found" description={search ? "Try another search term or clear your filters." : "This resource has no records yet."} />}
    </div>
  </>;
}

function InputField({ field, resource, record, value, onChange, mode = "edit" }: {
  field: FieldDef; resource: ResourceDef; record: RecordData; value: unknown;
  onChange: (value: unknown) => void; mode?: "create" | "edit";
}) {
  const id = `field-${field.name}`;
  const custom = field.components[mode] || field.components.edit;
  const Comp = custom ? customFields[custom] : undefined;
  const props: CustomFieldProps = { field, resource, record, value, onChange, mode };
  const source = field.dependency?.source;
  const sourceValue = source ? record[source] : undefined;
  const dynamicOptions = useQuery({
    queryKey: ["field-options", resource.id, field.name, field.dependency?.bridge, sourceValue],
    enabled: !!field.dependency && sourceValue !== undefined && sourceValue !== null && sourceValue !== "",
    queryFn: async () => api<{ result: { options: SelectOption<string | number>[] } }>(
      `/api/bridge/${encodeURIComponent(field.dependency!.bridge)}`,
      { method: "POST", body: JSON.stringify({ [field.dependency!.source]: sourceValue }) }),
    staleTime: 30_000,
  });
  let input: ReactNode;
  if (Comp) input = <Comp {...props} />;
  else if (field.dependency) input = <div>
    <Select id={id} options={dynamicOptions.data?.result.options ?? []} searchable
      value={value == null || value === "" ? null : String(value)}
      placeholder={sourceValue == null || sourceValue === "" ? `Choose ${source} first` : "Choose an option"}
      disabled={sourceValue == null || sourceValue === "" || dynamicOptions.isLoading || !!dynamicOptions.error}
      onChange={(next) => onChange(next)} />
    {dynamicOptions.error && <span role="alert" className="muted">Unable to load options</span>}
  </div>;
  else if (field.relation) input = <RelationInput field={field} value={value} onChange={onChange} />;
  else if (field.kind === "boolean") input = <Checkbox id={id} label="Enabled" checked={Boolean(value)}
    onCheckedChange={onChange}/>;
  else if (field.options?.length) {
    const options: SelectOption<string | number>[] = field.options.map((o) => typeof o === "string"
      ? { label: o, value: o } : o);
    input = <Select id={id} options={options} searchable value={value == null ? null : String(value)}
      placeholder="Choose an option" onChange={(v) => onChange(v)} />;
  }
  else if (["date", "datetime"].includes(field.kind)) input = <DatePicker id={id} value={value == null || value === "" ? null : String(value)}
    onChange={onChange} includeTime={field.kind === "datetime"}/>;
  else if (["json", "array"].includes(field.kind)) input = <Textarea id={id} rows={5} spellCheck={false}
    value={typeof value === "string" ? value : value == null ? "" : JSON.stringify(value, null, 2)}
    onChange={(e) => onChange(e.target.value)} placeholder="Valid JSON" />;
  else input = <TextInput id={id} type={["integer", "number"].includes(field.kind) ? "number" : field.widget === "email" ? "email" : "text"}
    step={field.kind === "integer" ? "1" : "any"} required={field.required}
    value={value == null ? "" : String(value)} placeholder={`Enter ${field.label.toLowerCase()}`}
    onChange={(e) => onChange(e.target.value)} />;
  return <FormField label={field.label} htmlFor={id} required={field.required} span={field.span ?? 1} hint={field.help}>
    {input}
  </FormField>;
}

/** Server-defined section/tab/accordion layout, without frontend ACL decisions. */
function StructuredFields({ resource, mode, fields, values, render }: {
  resource: ResourceDef; mode: "form" | "detail"; fields: FieldDef[];
  values: RecordData; render: (field: FieldDef) => ReactNode;
}) {
  const sections = resource.layouts?.[mode] ?? [];
  const visible = (section: typeof sections[number]) =>
    !section.visibleIf || values[section.visibleIf.field] === section.visibleIf.equals;
  const tabs = sections.filter((section) => section.kind === "tab" && visible(section));
  const [selectedTab, setSelectedTab] = useState<string | null>(null);
  const [accordionOpen, setAccordionOpen] = useState<Record<string, boolean>>({});
  const current = tabs.find((section) => section.id === selectedTab) ?? tabs[0];
  const assigned = new Set(sections.flatMap((section) => section.fields));
  const gridClass = `field-grid ra-layout-${mode === "form" ? resource.formLayout || "stack" : resource.detailLayout || "stack"}`;
  const content = (names: string[], columns?: 1 | 2 | null) => <div className={columns ? `field-grid ra-layout-${columns === 1 ? "stack" : "grid"}` : gridClass}>{fields.filter((field) => names.includes(field.name))
    .map((field) => <div key={field.name} className="ra-layout-field">{render(field)}</div>)}</div>;
  if (!sections.length) return content(fields.map((field) => field.name));
  const trailing = fields.filter((field) => !assigned.has(field.name));
  return <div className="ra-layout-sections">
    {tabs.length > 0 && <div className="ra-layout-tabs" role="tablist" aria-label="Record sections">
      {tabs.map((section) => <button key={section.id} type="button" role="tab"
        aria-selected={current?.id === section.id} onClick={() => setSelectedTab(section.id)}>
        {section.title}</button>)}
    </div>}
    {current && <section role="tabpanel" className="ra-layout-panel" aria-label={current.title}>
      {content(current.fields, current.columns)}</section>}
    {sections.filter((section) => section.kind !== "tab" && visible(section)).map((section) =>
      section.kind === "accordion" ? <details className="ra-layout-group" key={section.id}
        open={accordionOpen[section.id] ?? section.defaultOpen}
        onToggle={(event) => { const open = event.currentTarget.open;
          setAccordionOpen((previous) => previous[section.id] === open ? previous : { ...previous, [section.id]: open }); }}>
        <summary>{section.title}</summary>{content(section.fields, section.columns)}
      </details> : <section className="ra-layout-group" key={section.id}>
        <h3>{section.title}</h3>{content(section.fields, section.columns)}
      </section>)}
    {trailing.length > 0 && <section className="ra-layout-group">
      <h3>Other details</h3>{content(trailing.map((field) => field.name))}</section>}
  </div>;
}

function RecordEditor({ resource, id, navigate, notify }: {
  resource: ResourceDef; id?: string; navigate: (route: string) => void;
  notify: (text: string) => void;
}) {
  const client = useQueryClient();
  const { t } = useI18n();
  const isNew = id === undefined;
  const record = useQuery({ queryKey: ["record", resource.id, id], enabled: !isNew,
    queryFn: () => api<{ record: RecordData }>(`/api/resources/${resource.id}/${encodeURIComponent(id!)}`) });
  const feedback = useAdminFeedback();
  const [values, setValues] = useState<RecordData>({});
  const [dirty, setDirty] = useState(false);
  const skipGuard = useRef(false);
  const { requestDelete, isPending: deleting } = useDeleteRecord(resource,
    () => { skipGuard.current = true; navigate(`resources/${resource.id}`); });
  useEffect(() => { if (record.data?.record) { setValues(record.data.record); setDirty(false); } }, [record.data]);
  useEffect(() => {
    if (!dirty || skipGuard.current) return;
    const unregister = registerNavigationBlocker(() =>
      skipGuard.current ? Promise.resolve(true) : feedback.confirm({
        title: "Unsaved changes",
        message: "You have unsaved changes. Leave this page and discard them?",
        confirmLabel: "Discard changes",
        cancelLabel: "Keep editing",
        destructive: true,
      }));
    const warnUnload = (event: BeforeUnloadEvent) => {
      if (skipGuard.current) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warnUnload);
    return () => { unregister(); window.removeEventListener("beforeunload", warnUnload); };
  }, [dirty, feedback]);
  const mutation = useMutation({
    mutationFn: async () => {
      const payload: RecordData = {};
      for (const field of viewFields(resource.fields, isNew ? "create" : "edit").filter((f) => !f.readonly)) {
        let value = values[field.name];
        if (value === undefined || value === "") {
          if (isNew) continue;
          if (field.nullable && value === "") value = null;
          else if (value === undefined) continue;
        }
        if (typeof value === "string" && ["json", "array"].includes(field.kind)) {
          try { value = JSON.parse(value); }
          catch { throw new Error(`${field.label}: invalid JSON`); }
        }
        if (typeof value === "string" && ["integer", "number"].includes(field.kind) && value !== "") {
          value = Number(value);
          if (!Number.isFinite(value)) throw new Error(`${field.label}: invalid number`);
        }
        if (field.kind === "integer" && typeof value === "number" && !Number.isInteger(value))
          throw new Error(`${field.label}: an integer is required`);
        if (isNew || JSON.stringify(value) !== JSON.stringify(record.data?.record?.[field.name])) payload[field.name] = value;
      }
      return api<{ record: RecordData }>(`/api/resources/${resource.id}${isNew ? "" : `/${encodeURIComponent(id!)}`}`,
        { method: isNew ? "POST" : "PATCH", body: JSON.stringify(payload),
          headers: !isNew && resource.versionField ? { "If-Match": String(record.data?.record?.[resource.versionField]) } : undefined });
    },
    onSuccess: async (result) => {
      await client.invalidateQueries({ queryKey: ["list", resource.id] });
      await client.invalidateQueries({ queryKey: ["stats"] });
      skipGuard.current = true;
      setDirty(false);
      notify(isNew ? "Record created successfully" : "Changes saved successfully");
      navigate(`resources/${resource.id}/${encodeURIComponent(String(result.record[resource.primaryKey]))}`);
    },
    onError: (error: unknown) => feedback.toast(error instanceof Error ? error.message : "Could not save record", { kind: "error" }),
  });
  const visibleFields = viewFields(resource.fields, isNew ? "create" : "edit").filter((f) => !f.readonly);
  return <>
    <button className="back-link" onClick={() => navigate(isNew ? `resources/${resource.id}` : `resources/${resource.id}/${encodeURIComponent(id)}`)}><ArrowLeft size={16}/> {isNew ? `Back to ${resource.label}` : "Back to record"}</button>
    <div className="page-heading"><div><div className="eyebrow">{resource.label.toUpperCase()} / {isNew ? "CREATE" : "EDIT"}</div>
      <h1>{isNew ? `New ${resource.label.replace(/s$/, "")}` : "Edit record"}</h1><p>Provide the details below and save your changes.</p></div>
      {!isNew && <div className="heading-actions">
        {resource.capabilities.show && <button type="button" className="btn subtle"
          onClick={() => navigate(`resources/${resource.id}/${encodeURIComponent(id)}`)}>
          <ExternalLink size={16}/> View record</button>}
        {resource.capabilities.delete && <button type="button" className="btn danger"
          disabled={deleting || mutation.isPending || !record.data?.record}
          onClick={() => { void requestDelete(id, resource.versionField
            ? record.data?.record?.[resource.versionField] : undefined); }}>
          <Trash2 size={16}/> Delete</button>}
      </div>}</div>
    {!isNew && record.isLoading ? <Loading/> : record.error ? <Alert error={record.error}/> :
      <form className="editor-grid" onSubmit={(e: FormEvent) => { e.preventDefault(); mutation.mutate(); }}>
        <div className="surface editor-card"><div className="editor-card-title"><h2>Record details</h2><p>Fields marked with * are required.</p></div>
          {visibleFields.length ? <StructuredFields resource={resource} mode="form" fields={visibleFields}
            values={values} render={(field) => <InputField field={field} resource={resource}
              record={values} mode={isNew ? "create" : "edit"}
              value={values[field.name] ?? (field.kind === "boolean" ? false : "")}
              onChange={(v) => { setValues((old) => {
                const next: RecordData = { ...old, [field.name]: v };
                for (const dependent of resource.fields) {
                  if (dependent.dependency?.source === field.name) next[dependent.name] = "";
                }
                return next;
              }); setDirty(true); }} />}/>
            : <p className="muted">No editable fields</p>}
          {mutation.error != null && <Alert error={mutation.error} />}
          <div className="form-actions"><button type="button" className="btn subtle" onClick={() => navigate(isNew ? `resources/${resource.id}` : `resources/${resource.id}/${encodeURIComponent(id)}`)}>Cancel</button>
            <button className="btn primary" type="submit" disabled={mutation.isPending || (!isNew && !dirty)}>
              {mutation.isPending && <LoaderCircle className="spin" size={16}/>} {isNew ? t("actions.create", "Create record") : t("actions.save", "Save changes")}<ArrowRight size={16}/></button></div>
        </div>
      </form>}
  </>;
}

function RelatedRecords({ resource, identifier, relation, target, navigate }: {
  resource: ResourceDef; identifier: string;
  relation: ResourceDef["relationships"][number]; target: ResourceDef;
  navigate: (route: string) => void;
}) {
  const client = useQueryClient();
  const feedback = useAdminFeedback();
  const [offset, setOffset] = useState(0);
  const [text, setText] = useState("");
  const [search, setSearch] = useState("");
  const [selection, setSelection] = useState<string[]>([]);
  const [attachId, setAttachId] = useState<string | number | null>(null);
  const [creating, setCreating] = useState(false);
  const [newValues, setNewValues] = useState<RecordData>({});
  useEffect(() => { const t = window.setTimeout(() => { setSearch(text); setOffset(0); }, 250);
    return () => window.clearTimeout(t); }, [text]);
  const limit = 10;
  const url = `/api/resources/${resource.id}/${encodeURIComponent(identifier)}/relationships/${relation.name}`;
  const rows = useQuery({ queryKey: ["related", resource.id, identifier, relation.name, target.id, offset, search], queryFn: () =>
    api<Listing>(`${url}${buildQuery({ offset, limit, q: search })}`),
  });
  const loadOptions = useCallback(async (q: string) => {
    const response = await api<{ items: SelectOption<string | number>[] }>(
      `/api/resources/${target.id}/options${buildQuery({ q })}`);
    return response.items;
  }, [target.id]);
  const mutateLink = useMutation({
    mutationFn: async ({ operation, payload }: { operation: "attach" | "detach" | "create"; payload: RecordData }) =>
      api(`${url}/${operation}`, { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["related", resource.id, identifier] });
      await invalidateResource(client, target.id);
      setAttachId(null); setSelection([]); setCreating(false); setNewValues({});
      feedback.toast("Relationship updated", { kind: "success" });
    },
    onError: (error: unknown) => feedback.toast(error instanceof Error ? error.message : "Relationship update failed", { kind: "error" }),
  });
  const unlinkSelected = async () => {
    if (!await feedback.confirm({ title: "Unlink records?", message: `Detach ${selection.length} selected records without deleting them?`, destructive: true })) return;
    try {
      for (const id of selection) {
        await api(`${url}/detach`, { method: "POST", body: JSON.stringify({ id }) });
      }
      await client.invalidateQueries({ queryKey: ["related", resource.id, identifier] });
      setSelection([]);
      feedback.toast("Records unlinked", { kind: "success" });
    } catch (error) {
      await client.invalidateQueries({ queryKey: ["related", resource.id, identifier] });
      feedback.toast(error instanceof Error ? error.message : "Could not unlink records", { kind: "error" });
    }
  };
  const selectable = relation.selectable || !!relation.editable;
  const onSelection = selectable ? setSelection : undefined;
  return <div className="relation-section"><div className="relation-header"><h3>{relation.label}</h3>
    <span className="count">{rows.data?.total ?? "…"} records</span></div>
    <div className="ra-related-toolbar">
      <SearchInput value={text} onChange={setText} aria-label={`Search ${relation.label}`}
        placeholder={`Search ${relation.label.toLowerCase()}…`}/>
      {selectable && <span className="ra-related-selected">{selection.length} selected</span>}
      {relation.editable && selection.length > 0 && <button className="btn danger" type="button"
        onClick={() => { void unlinkSelected(); }}>Unlink selected</button>}
    </div>
    {relation.editable && <div className="ra-relation-editor">
      <div className="ra-attach-picker"><AsyncSelect<string | number> value={attachId}
        ariaLabel={`Link ${target.label}`} loadOptions={loadOptions} searchable clearable
        onChange={(value) => setAttachId(Array.isArray(value) ? value[0] ?? null : value)}
        placeholder={`Find ${target.label.toLowerCase()}…`}/></div>
      <button className="btn subtle" type="button" disabled={attachId == null || mutateLink.isPending}
        onClick={() => attachId != null && mutateLink.mutate({ operation: "attach", payload: { id: attachId } })}>Link existing</button>
      {target.capabilities.create && <button className="btn subtle" type="button" onClick={() => setCreating((state) => !state)}>
        {creating ? "Cancel" : "Create and link"}</button>}
    </div>}
    {creating && relation.editable && <form className="ra-relation-create surface" onSubmit={(event) => {
      event.preventDefault(); mutateLink.mutate({ operation: "create", payload: newValues });
    }}>
      <h4>Create {target.label.replace(/s$/, "")}</h4>
      <div className="field-grid ra-layout-stack">{viewFields(target.fields, "create").filter((field) => !field.readonly).map((field) =>
        <InputField key={field.name} field={field} resource={target} record={newValues} mode="create"
          value={newValues[field.name] ?? (field.kind === "boolean" ? false : "")}
          onChange={(value) => setNewValues((old) => ({ ...old, [field.name]: value }))}/>)}</div>
      <button className="btn primary" type="submit" disabled={mutateLink.isPending}>Create and link</button>
    </form>}
    {rows.isLoading ? <Loading/> : rows.error ? <Alert error={rows.error}/> : rows.data?.items.length ? <>
      {relation.layout === "cards" ? <div className="ra-related-cards">{rows.data.items.map((row) => {
        const id = String(row[target.primaryKey]);
        return <article className="ra-related-card" key={id}>
          {selectable && <div className="ra-related-card-check"><Checkbox label="Select" checked={selection.includes(id)}
            onCheckedChange={(checked) => onSelection?.(checked ? [...selection, id] : selection.filter((entry) => entry !== id))}/></div>}
          <button type="button" onClick={() => navigate(`resources/${target.id}/${encodeURIComponent(id)}`)}>
            {String(row[target.titleField] ?? id)}</button>
          <small>#{id}</small>
        </article>;
      })}</div> : <TableContent resource={target} data={rows.data} navigate={navigate} selectable={selectable}
          selection={selection} onSelectionChange={onSelection} />}
      {rows.data.total > limit && <Pager offset={offset} total={rows.data.total} limit={limit} onOffset={setOffset}/>}</> :
      <div className="muted relation-empty">No related records</div>}
  </div>;
}
function ResourceUploads({ resource, identifier }: { resource: ResourceDef; identifier: string }) {
  const client = useQueryClient();
  const feedback = useAdminFeedback();
  const [file, setFile] = useState<File | null>(null);
  const url = `/api/resources/${resource.id}/${encodeURIComponent(identifier)}/uploads`;
  const rows = useQuery({ queryKey: ["uploads", resource.id, identifier], queryFn: () =>
    api<{ items: { id: string; filename: string; size_bytes: number }[] }>(url) });
  const send = useMutation({
    mutationFn: (upload: File) => api(url, { method: "POST", body: upload,
      headers: { "X-Filename": encodeURIComponent(upload.name), "Content-Type": upload.type || "application/octet-stream" } }),
    onSuccess: async () => { setFile(null); await client.invalidateQueries({ queryKey: ["uploads", resource.id, identifier] });
      feedback.toast("Attachment uploaded", { kind: "success" }); },
    onError: (error: unknown) => feedback.toast(error instanceof Error ? error.message : "Upload failed", { kind: "error" }),
  });
  const remove = useMutation({
    mutationFn: (uploadId: string) => api(`/api/uploads/${encodeURIComponent(uploadId)}`, { method: "DELETE" }),
    onSuccess: async () => { await client.invalidateQueries({ queryKey: ["uploads", resource.id, identifier] });
      feedback.toast("Attachment removed", { kind: "success" }); },
  });
  return <div className="surface relationship-card">
    <h3>Attachments</h3>
    {rows.isLoading && <Loading label="Loading attachments" />}
    {rows.error && <Alert error={rows.error}/>}
    {rows.data?.items.map((asset) => <div className="ra-upload-item" key={asset.id}>
      <a href={`${base}/api/uploads/${encodeURIComponent(asset.id)}`} download>{asset.filename}</a>
      <small>{asset.size_bytes} bytes</small>
      {resource.capabilities.edit && <button className="btn subtle" disabled={remove.isPending} onClick={() =>
        void feedback.confirm({title:"Remove attachment?",destructive:true}).then(ok => {if(ok)remove.mutate(asset.id);})}>Remove</button>}
    </div>)}
    {resource.capabilities.edit && <form className="ra-upload-form" onSubmit={(event) => {
      event.preventDefault(); if (file) send.mutate(file); }}>
      <input type="file" aria-label="Choose attachment" onChange={(event) => setFile(event.target.files?.[0] ?? null)}/>
      <button type="submit" className="btn primary" disabled={!file || send.isPending}>Upload</button>
    </form>}
  </div>;
}

function RecordShow({ resource, id, schema, navigate }: {
  resource: ResourceDef; id: string; schema: Schema; navigate: (route: string) => void;
}) {
  const record = useQuery({ queryKey: ["record", resource.id, id],
    queryFn: () => api<{ record: RecordData; actions: string[] }>(`/api/resources/${resource.id}/${encodeURIComponent(id)}`) });
  const { requestDelete, isPending: deleting } = useDeleteRecord(resource,
    () => navigate(`resources/${resource.id}`));
  const related = resource.relationships.filter((relation) => schema.resources.some((r) => r.id === relation.resource));
  return <>
    <button className="back-link" onClick={() => navigate(`resources/${resource.id}`)}><ArrowLeft size={16}/> Back to {resource.label}</button>
    <div className="page-heading"><div><div className="eyebrow">{resource.label.toUpperCase()} / RECORD</div>
      <h1>{record.data ? String(record.data.record[resource.titleField] ?? `Record ${id}`) : `Record ${id}`}</h1>
      <p>Record details and connected relationships.</p></div>
      <div className="heading-actions">
        {resource.capabilities.edit && <button className="btn subtle" onClick={() => navigate(`resources/${resource.id}/${encodeURIComponent(id)}/edit`)}><Pencil size={16}/> Edit</button>}
        {resource.capabilities.delete && <button className="btn danger" disabled={deleting} onClick={() => { void requestDelete(id, resource.versionField ? record.data?.record?.[resource.versionField] : undefined); }}><Trash2 size={16}/> Delete</button>}
      </div>
    </div>
    {record.isLoading ? <Loading/> : record.error ? <Alert error={record.error} /> : record.data && <>
      <div className="surface detail-card"><div className="editor-card-title"><h2>Details</h2><p>Data from the SQLAlchemy resource</p></div>
        <StructuredFields resource={resource} mode="detail" fields={viewFields(resource.fields, "show")}
          values={record.data.record} render={(field) => <div className={`detail-item ${field.span === 2 ? "ra-field-wide" : ""}`}>
            <dt>{field.label}</dt><dd><FieldValue resource={resource} field={field}
              record={record.data!.record} value={record.data!.record[field.name]} mode="show" /></dd>
          </div>} />
      </div>
      {!!resource.actions.length && <div className="record-extra-actions">
        {resource.actions.filter((action) => (action.kind ?? "record") === "record" && action.position !== "row" && record.data.actions.includes(action.name))
          .map((action) => <RecordAction key={action.name} resource={resource} record={record.data!.record}
            action={action} navigate={navigate}/>)}
      </div>}
      {resource.uploads && <ResourceUploads resource={resource} identifier={id} />}
      {related.map((relation) => <div key={relation.name} className="surface relationship-card">
        <RelatedRecords resource={resource} identifier={id} relation={relation}
          target={schema.resources.find((r) => r.id === relation.resource)!} navigate={navigate}/></div>)}
    </>}
  </>;
}

function ActionView({ resource, schema, id, action, navigate }: {
  resource: ResourceDef; schema: Schema; id: string; action: ActionDef;
  navigate: (route: string) => void;
}) {
  const client = useQueryClient();
  const record = useQuery({ queryKey: ["record", resource.id, id],
    queryFn: () => api<{ record: RecordData; actions: string[] }>(`/api/resources/${resource.id}/${encodeURIComponent(id)}`) });
  const Custom = action.component ? customActions[action.component] : undefined;
  const feedback = useAdminFeedback();
  const invoke = async (payload: RecordData = {}) => {
    // Custom components own their confirmation UI, and may call feedback.confirm themselves.
    // A configured default confirmation remains the safe fallback.
    if (action.confirmation && !await feedback.confirm({ title: action.label,
      message: action.confirmation, destructive: action.variant === "danger" })) return;
    const response = await api<{ result: unknown }>(`/api/resources/${resource.id}/${encodeURIComponent(id)}/actions/${action.name}`,
      { method: "POST", body: JSON.stringify(payload) });
    await invalidateResource(client, resource.id);
    feedback.toast(`${action.label} completed`, { kind: "success" });
    return response.result;
  };
  if (record.isPending) return <Loading/>;
  if (record.error) return <Alert error={record.error}/>;
  if (!record.data?.actions.includes(action.name)) return <Alert error={new Error("Action unavailable for this record")}/>;
  if (!Custom) return <Alert error={new Error(`Action component '${action.component}' not registered`)}/>;
  return <section className="action-view">
    <button className="back-link" onClick={() => navigate(`resources/${resource.id}/${encodeURIComponent(id)}`)}><ArrowLeft size={16}/> Back to record</button>
    <div className="page-heading"><h1>{action.label}</h1></div>
    <Custom schema={schema} resource={resource} record={record.data.record} action={action} navigate={navigate} invoke={invoke}/>
  </section>;
}

/** An override replaces the complete CRUD screen, not merely its fields. */
function ResourceRoute({ schema, resource, mode, id, navigate, notify }: {
  schema: Schema; resource: ResourceDef; mode: "list" | "create" | "edit" | "show";
  id?: string; navigate: (route: string) => void; notify?: (message: string) => void;
}) {
  const client = useQueryClient();
  const feedback = useAdminFeedback();
  const customId = resource.crudViews?.[mode];
  const Custom = customId ? customCrud[customId] : undefined;
  const record = useQuery({ queryKey: ["record", resource.id, id],
    enabled: !!Custom && !!id,
    queryFn: () => api<{ record: RecordData }>(`/api/resources/${resource.id}/${encodeURIComponent(id!)}`),
  });
  if (!Custom) {
    if (mode === "list") return <ResourceList resource={resource} schema={schema} navigate={navigate}/>;
    if (mode === "show") return <RecordShow resource={resource} schema={schema} id={id!} navigate={navigate}/>;
    return <RecordEditor resource={resource} id={id} navigate={navigate} notify={notify ?? (() => undefined)}/>;
  }
  const loadList: CustomCrudProps["loadList"] = async (params = {}) =>
    api<{ items: RecordData[]; total: number; offset: number; limit: number }>(
      `/api/resources/${resource.id}${buildQuery(params)}`);
  const save: CustomCrudProps["save"] = async (payload) => {
    if (mode !== "create" && mode !== "edit") throw new Error("This screen cannot save records");
    const result = await api<{ record: RecordData }>(
      `/api/resources/${resource.id}${mode === "edit" ? `/${encodeURIComponent(id!)}` : ""}`,
      { method: mode === "edit" ? "PATCH" : "POST", body: JSON.stringify(payload),
        headers: mode === "edit" && resource.versionField && record.data?.record
          ? { "If-Match": String(record.data.record[resource.versionField]) } : undefined });
    await invalidateResource(client, resource.id);
    feedback.toast("Record saved", { kind: "success" });
    return result.record;
  };
  const remove: CustomCrudProps["remove"] = async () => {
    if (!id || !resource.capabilities.delete) throw new Error("Delete is not available");
    if (!await feedback.confirm({ title: "Delete record?", message: "This action cannot be undone.", destructive: true })) return;
    await api(`/api/resources/${resource.id}/${encodeURIComponent(id)}`,
      { method: "DELETE", headers: resource.versionField && record.data?.record
        ? { "If-Match": String(record.data.record[resource.versionField]) } : undefined });
    await invalidateResource(client, resource.id);
    navigate(`resources/${resource.id}`);
  };
  if (record.isPending && id) return <Loading/>;
  if (record.error) return <Alert error={record.error}/>;
  return <Custom schema={schema} resource={resource} mode={mode} record={record.data?.record}
    navigate={navigate} loadList={loadList} save={save} remove={remove}
    reload={async () => { await invalidateResource(client, resource.id); }}/>
}

function MainLayout({ schema, user, onLogout, navigate, route, children, themeMode, toggleTheme }: {
  schema: Schema; user: NonNullable<AuthState["user"]>; onLogout: () => void;
  navigate: (route: string) => void; route: string; children: ReactNode;
  themeMode: ThemeMode; toggleTheme: () => void;
}) {
  const { t } = useI18n();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  useEffect(() => {
    if (!drawerOpen) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previous; };
  }, [drawerOpen]);
  const navigateAndClose = (url: string) => { navigate(url); setDrawerOpen(false); };
  return <div className="app-shell">
    {drawerOpen && <div className="mobile-backdrop" onClick={() => setDrawerOpen(false)}/>}
    <aside className={`sidebar ${drawerOpen ? "open" : ""}`} aria-label="Workspace sidebar">
      <button className="brand brand-button" onClick={() => navigateAndClose("")}><div className="brand-mark"><Command size={21}/></div>
        <strong>Pyntral</strong></button>
      <div className="workspace-title" title={schema.title}>{schema.title}</div>
      <SidebarNavigation schema={schema} route={route} navigate={navigateAndClose}/>
      <div className="sidebar-bottom"><div className="user-card"><div className="user-avatar">{user.username.slice(0, 2).toUpperCase()}</div>
          <div className="user-name"><strong>{user.display_name || user.username}</strong><span>{user.roles.join(", ") || "Member"}</span></div>
          </div></div>
    </aside>
    <div className="main-column"><header className="topbar"><div className="topbar-left">
      <button className="mobile-menu" onClick={() => setDrawerOpen(true)} aria-label="Open menu"><Menu size={21}/></button>
      <span className="topbar-breadcrumb">Workspace <ChevronRight size={14}/> <strong>{route ? route.split("/")[1] || "Dashboard" : "Overview"}</strong></span></div>
      <div className="topbar-right"><button onClick={toggleTheme} aria-label="Toggle theme" title="Toggle theme"
        className="topbar-icon">{themeMode === "light" ? <Moon size={18}/> : <Sun size={18}/>}</button>
        <Popover open={profileOpen} onOpenChange={setProfileOpen}>
          <PopoverTrigger asChild><button type="button" className="ra-profile-trigger" aria-label="Account menu">
            <span className="topbar-avatar">{user.username.slice(0, 2).toUpperCase()}</span>
          </button></PopoverTrigger>
          <PopoverContent width={275} maxHeight={450} minHeight={110} padded={false} role="menu" className="ra-profile-menu">
              <div className="ra-profile-header"><strong>{user.display_name || user.username}</strong>
                <span>{user.roles.join(", ") || "Member"}</span></div>
              {customProfileMenu && <ProfileMenuExtension user={user} schema={schema} navigate={(url) => {
                navigateAndClose(url); setProfileOpen(false); }} close={() => setProfileOpen(false)}/>}
              <button role="menuitem" onClick={() => { setProfileOpen(false); onLogout(); }}><LogOut size={16}/> {t("nav.sign_out", "Sign out")}</button>
          </PopoverContent>
        </Popover></div></header>
      <main className="main-content page-enter" key={route}>{children}</main>
    </div>
  </div>;
}

function AdminApp() {
  const client = useQueryClient();
  const { route, navigate } = useNavigation();
  const auth = useQuery({ queryKey: ["auth"], queryFn: getAuth, retry: false, staleTime: 15_000 });
  const schema = useQuery({ queryKey: ["schema", auth.data?.user?.id], enabled: !!auth.data?.user,
    queryFn: () => api<Schema>("/api/schema") });
  const feedback = useAdminFeedback();
  useEffect(() => {
    if (!auth.data?.user || !schema.data?.realtime) return;
    const source = new EventSource(`${base}/api/realtime`, { withCredentials: true });
    source.addEventListener("invalidate", () => {
      void client.invalidateQueries({ queryKey: ["list"] });
      void client.invalidateQueries({ queryKey: ["related"] });
      void client.invalidateQueries({ queryKey: ["record"] });
      void client.invalidateQueries({ queryKey: ["stats"] });
    });
    return () => source.close();
  }, [auth.data?.user?.id, schema.data?.realtime, client]);
  const setNotice = useCallback((message: string) => feedback.toast(message, { kind: "success" }), [feedback]);
  const [preferredTheme, setPreferredTheme] = useState(() => localStorage.getItem("pyntral-theme") || "system");
  const [systemDark, setSystemDark] = useState(() => window.matchMedia("(prefers-color-scheme: dark)").matches);
  const themeMode: ThemeMode = preferredTheme === "system" ? (schema.data?.theme?.default === "system" || !schema.data?.theme
    ? (systemDark ? "dark" : "light") : resolveMode(schema.data.theme.default)) : resolveMode(preferredTheme);
  useEffect(() => {
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const update = () => setSystemDark(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  useEffect(() => { if (!schema.data) return; return applyTheme(schema.data, themeMode); }, [schema.data, themeMode]);
  const toggleTheme = () => {
    const next = themeMode === "light" ? "dark" : "light";
    localStorage.setItem("pyntral-theme", next);
    setPreferredTheme(next);
  };
  const logout = async () => { try { await api("/auth/logout", { method: "POST" }); } finally {
    setCsrf(null); client.clear(); client.setQueryData(["auth"], { user: null, csrf: null }); navigate(""); } };
  const content = useMemo(() => {
    const data = schema.data;
    if (!data) return null;
    if (!route && data.navigation?.showDashboard !== false) return <Overview schema={data} navigate={navigate}/>;
    if (!route) {
      const first = data.resources.find((r) => r.capabilities.list);
       return first ? <ResourceList schema={data} resource={first} navigate={navigate}/> : <Empty title="No resources"/>;
    }
    const segments = route.split("/").map(decodeURIComponent);
    if (segments[0] === "resources") {
      const resource = data.resources.find((r) => r.id === segments[1]);
      if (!resource) return <Empty title="Resource not found" description="This resource isn't available to your account."/>;
      if (!resource.capabilities.list) return <div className="empty"><LockKeyhole size={24}/><strong>Access denied</strong>
        <p>This resource is not available to your account.</p></div>;
      if (segments.length === 2) return <ResourceRoute key={resource.id + ":list"} schema={data} resource={resource} mode="list" navigate={navigate}/>;
      if (segments[2] === "new" && segments.length === 3 && resource.capabilities.create) return <ResourceRoute schema={data} resource={resource} mode="create" navigate={navigate} notify={setNotice}/>;
      if (segments.length === 4 && segments[3] === "edit" && resource.capabilities.edit) return <ResourceRoute key={segments[2] + ":edit"} schema={data} resource={resource} mode="edit" id={segments[2]} navigate={navigate} notify={setNotice}/>;
      if (segments.length === 5 && segments[3] === "actions") {
        const action = resource.actions.find((a) => a.name === segments[4] && a.component);
        if (action) return <ActionView key={`${segments[2]}-${action.name}`} resource={resource} schema={data}
          id={segments[2]} action={action} navigate={navigate}/>;
      }
      if (segments.length === 3 && resource.capabilities.show) return <ResourceRoute key={segments[2] + ":show"} schema={data} resource={resource} mode="show" id={segments[2]} navigate={navigate}/>;
    }
    if (segments[0] === "pages") {
      const page = data.pages.find((p) => p.name === segments[1]);
      const Custom = page ? customPages[page.component] : undefined;
      if (Custom) return <Custom schema={data} navigate={navigate}/>;
      if (page) return <Alert error={new Error(`Custom page component "${page.component}" not registered`)}/>;
    }
    return <Empty title="Page not found" description="Check the URL or choose a resource in the sidebar."/>;
  }, [route, schema.data, navigate]);

  if (auth.isPending) return <div className="fullscreen-loading"><Loading label="Starting workspace…"/></div>;
  if (auth.error) return <div className="fullscreen-loading"><Alert error={auth.error}/><button className="btn subtle" onClick={() => auth.refetch()}>Retry</button></div>;
  if (!auth.data?.user) {
    const authenticated = (state: AuthState) => {
      setCsrf(state.csrf);
      client.setQueryData(["auth"], state);
      client.invalidateQueries({ queryKey: ["schema"] });
    };
    const CustomLogin = customAuth.login;
    return CustomLogin ? <CustomLogin onAuthenticated={authenticated}/> : <Login onSignedIn={authenticated}/>;
  }
  if (schema.isPending) return <div className="fullscreen-loading"><Loading label="Loading workspace…"/></div>;
  if (schema.error || !schema.data) return <div className="fullscreen-loading"><Alert error={schema.error}/><button className="btn subtle" onClick={() => schema.refetch()}>Retry</button></div>;
  const ThemeExtension = customThemes.global;
  return <CurrentAdminProvider currentAdmin={auth.data.user}><I18nProvider config={schema.data.localization}><MainLayout schema={schema.data} user={auth.data.user} route={route} navigate={navigate} onLogout={logout}
    themeMode={themeMode} toggleTheme={toggleTheme}>
    {ThemeExtension && <ThemeExtension schema={schema.data} mode={themeMode}/>}
    {content}
  </MainLayout></I18nProvider></CurrentAdminProvider>;
}

export function App() { return <AdminFeedbackProvider><AdminApp/></AdminFeedbackProvider>; }
