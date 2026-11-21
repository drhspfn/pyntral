import { useCallback, useEffect, useMemo, useState, type CSSProperties, type FormEvent, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity, ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Boxes,
  ChevronLeft, ChevronRight, CircleAlert, Command, Database, ExternalLink, Filter,
  LayoutDashboard, LoaderCircle, LockKeyhole, LogOut, Menu, MoreHorizontal, Pencil,
  Plus, RefreshCw, Settings2, ShieldCheck, Trash2, Sun, Moon,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { fields as customFields, pages as customPages, actions as customActions, dialogs as customDialogs, themes as customThemes, profile as customProfile, auth as customAuth } from "virtual:pyntral-extensions";
import { SidebarNavigation } from "./navigation";
import { AdminFeedbackProvider, useAdminFeedback } from "./feedback";
import { useDeleteRecord, invalidateResource, type Listing } from "./mutations";
import { DatePicker, FormField, SearchInput, Select, TextInput, Textarea,
  type SelectOption } from "./ui";
import { RelationInput } from "./relation";
import { AdvancedFilterField, serializeFilters, filterOperators, type FilterValues } from "./filters";
import { filterControlWidth } from "./filter-state";
import { applyTheme, resolveMode } from "./theme";
import { CurrentAdminProvider } from "./currentAdmin";
import { api, base, buildQuery, getAuth, setCsrf } from "./api";
import type {
  ActionDef, AuthState, CustomFieldProps, FieldDef, RecordData, ResourceDef, Schema, ThemeMode,
} from "./types";

const customProfileMenu = customProfile.menu;
const ProfileMenuExtension = customProfile.menu;

const icons: Record<string, LucideIcon> = {
  database: Database, "layout-dashboard": LayoutDashboard, boxes: Boxes,
  activity: Activity, "shield-check": ShieldCheck, "settings-2": Settings2,
};

function useNavigation() {
  const [url, setUrl] = useState(() => window.location.pathname);
  useEffect(() => {
    const update = () => setUrl(window.location.pathname);
    window.addEventListener("popstate", update);
    return () => window.removeEventListener("popstate", update);
  }, []);
  const navigate = useCallback((route: string) => {
    const full = `${base}/${route.replace(/^\//, "")}`.replace(/\/$/, "/");
    if (full !== window.location.pathname) history.pushState(null, "", full);
    setUrl(full);
    window.scrollTo(0, 0);
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
  return <>
    <div className="page-heading"><div><h1>Overview</h1><p>{schema.title}</p></div></div>
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

function TableContent({ resource, data, navigate, selectable = false, selection = [], onSelectionChange }: { resource: ResourceDef; data: Listing;
  navigate: (route: string) => void; selectable?: boolean; selection?: string[];
  onSelectionChange?: (selected: string[]) => void;
}) {
  const columns = resource.listFields.map((name) => resource.fields.find((field) => field.name === name)).filter((x): x is FieldDef => !!x);
  const { requestDelete } = useDeleteRecord(resource);
  const keys = data.items.map((row) => String(row[resource.primaryKey]));
  return <div><div className="table-scroll"><table className="data-table"><thead><tr>
    {selectable && <th><input type="checkbox" aria-label="Select all visible records"
      checked={keys.length > 0 && keys.every((key) => selection.includes(key))}
      onChange={(event) => onSelectionChange?.(event.target.checked ? Array.from(new Set([...selection, ...keys])) : selection.filter((key) => !keys.includes(key)))}/></th>}
    {columns.map((field) => <th key={field.name}>{field.label}</th>)}<th className="actions-head">ACTION</th>
  </tr></thead><tbody>
    {data.items.map((row) => <tr key={String(row[resource.primaryKey])}>
      {selectable && <td><input type="checkbox" aria-label={`Select record ${String(row[resource.primaryKey])}`}
        checked={selection.includes(String(row[resource.primaryKey]))} onChange={(event) => {
          const key = String(row[resource.primaryKey]);
          onSelectionChange?.(event.target.checked ? [...selection, key] : selection.filter((value) => value !== key));
        }}/></td>}
      {columns.map((field, idx) => <td key={field.name} className={idx === 0 ? "strong-cell" : ""}>
        {idx === 0 && resource.capabilities.show ? <button className="cell-link" onClick={() => navigate(`resources/${resource.id}/${encodeURIComponent(String(row[resource.primaryKey]))}`)}>
          <FieldValue resource={resource} field={field} value={row[field.name]} record={row} mode="list" /></button> :
          <FieldValue resource={resource} field={field} value={row[field.name]} record={row} mode="list" />}
      </td>)}
      <td className="actions-cell"><div className="row-actions">
        {resource.capabilities.show && <button title="View" aria-label="View record" onClick={() => navigate(`resources/${resource.id}/${encodeURIComponent(String(row[resource.primaryKey]))}`)}><ExternalLink size={16}/></button>}
        {resource.capabilities.edit && <button title="Edit" aria-label="Edit record" onClick={() => navigate(`resources/${resource.id}/${encodeURIComponent(String(row[resource.primaryKey]))}/edit`)}><Pencil size={15}/></button>}
        {resource.capabilities.delete && <button type="button" title="Delete" aria-label="Delete record"
          onClick={() => { void requestDelete(row[resource.primaryKey]); }}><Trash2 size={15}/></button>}
        {resource.actions.filter((a) => a.position !== "detail" && (data.actionsByRecord?.[String(row[resource.primaryKey])] || []).includes(a.name))
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

function ResourceList({ resource, navigate }: { resource: ResourceDef; navigate: (route: string) => void }) {
  const [text, setText] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [sort, setSort] = useState(resource.primaryKey);
  const [desc, setDesc] = useState(true);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [filters, setFilters] = useState<FilterValues>({});
  const [appliedFilters, setAppliedFilters] = useState<FilterValues>({});
  const activeFilterCount = Object.keys(serializeFilters(resource.fields, filters)).length;
  useEffect(() => { const t = setTimeout(() => { setSearch(text); setOffset(0); }, 260); return () => clearTimeout(t); }, [text]);
  useEffect(() => { const t = setTimeout(() => setAppliedFilters(filters), 240); return () => clearTimeout(t); }, [filters]);
  const query = buildQuery({ offset, limit: resource.pageSize,
    q: resource.showSearch ? search : undefined, sort, desc,
    ...serializeFilters(resource.fields, appliedFilters) });
  const records = useQuery({ queryKey: ["list", resource.id, query],
    queryFn: () => api<Listing>(`/api/resources/${resource.id}${query}`) });
  return <>
    <div className="page-heading"><div><div className="eyebrow">DATA / {resource.id.toUpperCase()}</div>
      <h1>{resource.label}</h1><p>View, organize, and manage your records.</p></div>
      {resource.capabilities.create && <button className="btn primary" onClick={() => navigate(`resources/${resource.id}/new`)}><Plus size={17}/> New record</button>}
    </div>
    <div className="surface">
      <div className="table-toolbar">
        {resource.showSearch && <SearchInput value={text} onChange={setText}
          className="ra-list-search" aria-label="Search records"
          placeholder={resource.searchFields.length ? `Search ${resource.label.toLowerCase()}…` : "Search not configured"}
          disabled={!resource.searchFields.length} />}
        <div className="toolbar-buttons"><button className={`btn subtle ra-filter-toggle ${filtersOpen ? "selected" : ""}`} aria-expanded={filtersOpen}
          onClick={() => setFiltersOpen(!filtersOpen)}><Filter size={16}/> Filters
          <span className={`ra-filter-count ${activeFilterCount === 0 ? "is-empty" : ""}`} aria-hidden={activeFilterCount === 0}>{activeFilterCount || "0"}</span></button>
          <button className="btn subtle" onClick={() => records.refetch()} title="Refresh"><RefreshCw size={16}/></button></div>
      </div>
      {filtersOpen && <div className="filters-panel">
        <div className="ra-filter-heading"><span className="filter-caption">REFINE RESULTS</span>
          <span className="ra-filter-hint">Choose a comparison using the icon beside each field</span></div>
        <div className="filters-fields">{resource.fields.filter((f) => filterOperators(f).length > 0).map((field) =>
          <div className={`ra-filter-field ${Object.keys(serializeFilters([field], { [field.name]: filters[field.name] || {} })).length ? "is-active" : ""}`}
            key={field.name} style={{ "--ra-filter-width": `${filterControlWidth(field,
              filters[field.name]?.operator === "between" ||
              (field.kind === "enum" && filterOperators(field).includes("in") && filterOperators(field).includes("not_in")))}px` } as CSSProperties}>
            <span className="ra-filter-label">{field.label}</span>
            <AdvancedFilterField field={field} resource={resource} value={filters[field.name] || {}}
              onChange={(value) => { setFilters((old) => ({ ...old, [field.name]: value })); setOffset(0); }}/>
          </div>)}</div>
        <button className="link-btn" onClick={() => setFilters({})}>Clear filters</button>
      </div>}
      <div className="sortbar"><span>{records.data ? `${records.data.total} total records` : "Records"}</span>
        <div className="sort-controls">Sort by <div className="ra-sort-select"><Select searchable={false} clearable={false} ariaLabel="Sort column" value={sort}
          onChange={(value) => { if (typeof value === "string") setSort(value); }}
          options={resource.fields.map((field) => ({ value: field.name, label: field.label }))}/></div>
          <button title="Toggle sort order" onClick={() => setDesc(!desc)}>{desc ? <ArrowDown size={16}/> : <ArrowUp size={16}/>}</button></div></div>
      {records.isLoading ? <Loading label="Loading records…" /> : records.error ? <Alert error={records.error} /> :
        records.data?.items.length ? <><TableContent resource={resource} data={records.data} navigate={navigate}/>
          <Pager offset={offset} total={records.data.total} limit={resource.pageSize} onOffset={setOffset}/></> :
        <Empty title="No records found" description={search ? "Try another search term or clear your filters." : "This resource has no records yet."} />}
    </div>
  </>;
}

function InputField({ field, resource, record, value, onChange }: {
  field: FieldDef; resource: ResourceDef; record: RecordData; value: unknown;
  onChange: (value: unknown) => void;
}) {
  const id = `field-${field.name}`;
  const custom = field.components.edit;
  const Comp = custom ? customFields[custom] : undefined;
  const props: CustomFieldProps = { field, resource, record, value, onChange, mode: "edit" };
  let input: ReactNode;
  if (Comp) input = <Comp {...props} />;
  else if (field.relation) input = <RelationInput field={field} value={value} onChange={onChange} />;
  else if (field.kind === "boolean") input = <label className="check-field"><input id={id} type="checkbox" checked={Boolean(value)}
    onChange={(e) => onChange(e.target.checked)}/><span>Enabled</span></label>;
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
  else input = <TextInput id={id} type={["integer", "number"].includes(field.kind) ? "number" : "text"}
    step={field.kind === "integer" ? "1" : "any"} required={field.required}
    value={value == null ? "" : String(value)} placeholder={`Enter ${field.label.toLowerCase()}`}
    onChange={(e) => onChange(e.target.value)} />;
  return <FormField label={field.label} htmlFor={id} required={field.required} span={field.span ?? 1} hint={field.help}>
    {input}
  </FormField>;
}

function RecordEditor({ resource, id, navigate, notify }: {
  resource: ResourceDef; id?: string; navigate: (route: string) => void;
  notify: (text: string) => void;
}) {
  const client = useQueryClient();
  const isNew = id === undefined;
  const record = useQuery({ queryKey: ["record", resource.id, id], enabled: !isNew,
    queryFn: () => api<{ record: RecordData }>(`/api/resources/${resource.id}/${encodeURIComponent(id!)}`) });
  const feedback = useAdminFeedback();
  const [values, setValues] = useState<RecordData>({});
  const [dirty, setDirty] = useState(false);
  useEffect(() => { if (record.data?.record) { setValues(record.data.record); setDirty(false); } }, [record.data]);
  const mutation = useMutation({
    mutationFn: async () => {
      const payload: RecordData = {};
      for (const field of resource.fields.filter((f) => !f.readonly)) {
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
        { method: isNew ? "POST" : "PATCH", body: JSON.stringify(payload) });
    },
    onSuccess: async (result) => {
      await client.invalidateQueries({ queryKey: ["list", resource.id] });
      await client.invalidateQueries({ queryKey: ["stats"] });
      notify(isNew ? "Record created successfully" : "Changes saved successfully");
      navigate(`resources/${resource.id}/${encodeURIComponent(String(result.record[resource.primaryKey]))}`);
    },
    onError: (error: unknown) => feedback.toast(error instanceof Error ? error.message : "Could not save record", { kind: "error" }),
  });
  const visibleFields = resource.fields.filter((f) => !f.readonly);
  return <>
    <button className="back-link" onClick={() => navigate(`resources/${resource.id}`)}><ArrowLeft size={16}/> Back to {resource.label}</button>
    <div className="page-heading"><div><div className="eyebrow">{resource.label.toUpperCase()} / {isNew ? "CREATE" : "EDIT"}</div>
      <h1>{isNew ? `New ${resource.label.replace(/s$/, "")}` : "Edit record"}</h1><p>Provide the details below and save your changes.</p></div></div>
    {!isNew && record.isLoading ? <Loading/> : record.error ? <Alert error={record.error}/> :
      <form className="editor-grid" onSubmit={(e: FormEvent) => { e.preventDefault(); mutation.mutate(); }}>
        <div className="surface editor-card"><div className="editor-card-title"><h2>Record details</h2><p>Fields marked with * are required.</p></div>
          <div className={`field-grid ra-layout-${resource.formLayout || "stack"}`}>{visibleFields.length ? visibleFields.map((field) => <InputField
            key={field.name} field={field} resource={resource} record={values}
            value={values[field.name] ?? (field.kind === "boolean" ? false : "")}
            onChange={(v) => { setValues((old) => ({ ...old, [field.name]: v })); setDirty(true); }} />) :
            <p className="muted">No editable fields</p>}</div>
          {mutation.error != null && <Alert error={mutation.error} />}
          <div className="form-actions"><button type="button" className="btn subtle" onClick={() => navigate(`resources/${resource.id}`)}>Cancel</button>
            <button className="btn primary" type="submit" disabled={mutation.isPending || (!isNew && !dirty)}>
              {mutation.isPending && <LoaderCircle className="spin" size={16}/>} {isNew ? "Create record" : "Save changes"}<ArrowRight size={16}/></button></div>
        </div>
        <aside className="editor-aside"><div className="surface hint-card"><div className="hint-icon"><ShieldCheck size={18}/></div>
          <strong>Data integrity</strong><p>Validation and access control are enforced by the Python backend, not by the form.</p></div></aside>
      </form>}
  </>;
}

function RelatedRecords({ resource, identifier, relation, target, navigate }: {
  resource: ResourceDef; identifier: string;
  relation: ResourceDef["relationships"][number]; target: ResourceDef;
  navigate: (route: string) => void;
}) {
  const [offset, setOffset] = useState(0);
  const [text, setText] = useState("");
  const [search, setSearch] = useState("");
  const [selection, setSelection] = useState<string[]>([]);
  useEffect(() => { const t = window.setTimeout(() => { setSearch(text); setOffset(0); }, 250);
    return () => window.clearTimeout(t); }, [text]);
  const limit = 10;
  const rows = useQuery({ queryKey: ["related", resource.id, identifier, relation.name, target.id, offset, search], queryFn: () =>
    api<Listing>(`/api/resources/${resource.id}/${encodeURIComponent(identifier)}/relationships/${relation.name}${buildQuery({ offset, limit, q: search })}`),
  });
  const onSelection = relation.selectable ? setSelection : undefined;
  return <div className="relation-section"><div className="relation-header"><h3>{relation.label}</h3>
    <span className="count">{rows.data?.total ?? "…"} records</span></div>
    <div className="ra-related-toolbar">
      <SearchInput value={text} onChange={setText} aria-label={`Search ${relation.label}`}
        placeholder={`Search ${relation.label.toLowerCase()}…`}/>
      {relation.selectable && <span className="ra-related-selected">{selection.length} selected</span>}
    </div>
    {rows.isLoading ? <Loading/> : rows.error ? <Alert error={rows.error}/> : rows.data?.items.length ? <>
      {relation.layout === "cards" ? <div className="ra-related-cards">{rows.data.items.map((row) => {
        const id = String(row[target.primaryKey]);
        return <article className="ra-related-card" key={id}>
          {relation.selectable && <label className="ra-related-card-check"><input type="checkbox" checked={selection.includes(id)}
            onChange={(e) => onSelection?.(e.target.checked ? [...selection, id] : selection.filter((entry) => entry !== id))} /> Select</label>}
          <button type="button" onClick={() => navigate(`resources/${target.id}/${encodeURIComponent(id)}`)}>
            {String(row[target.titleField] ?? id)}</button>
          <small>#{id}</small>
        </article>;
      })}</div> : <TableContent resource={target} data={rows.data} navigate={navigate} selectable={relation.selectable}
          selection={selection} onSelectionChange={onSelection} />}
      {rows.data.total > limit && <Pager offset={offset} total={rows.data.total} limit={limit} onOffset={setOffset}/>}</> :
      <div className="muted relation-empty">No related records</div>}
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
        {resource.capabilities.delete && <button className="btn danger" disabled={deleting} onClick={() => { void requestDelete(id); }}><Trash2 size={16}/> Delete</button>}
      </div>
    </div>
    {record.isLoading ? <Loading/> : record.error ? <Alert error={record.error} /> : record.data && <>
      <div className="surface detail-card"><div className="editor-card-title"><h2>Details</h2><p>Data from the SQLAlchemy resource</p></div>
        <dl className={`details-grid ra-layout-${resource.detailLayout || "stack"}`}>{resource.fields.map((field) => <div key={field.name} className={`detail-item ${field.span === 2 ? "ra-field-wide" : ""}`}>
          <dt>{field.label}</dt><dd><FieldValue resource={resource} field={field}
            record={record.data!.record} value={record.data!.record[field.name]} mode="show" /></dd>
        </div>)}</dl>
      </div>
      {!!resource.actions.length && <div className="record-extra-actions">
        {resource.actions.filter((action) => action.position !== "row" && record.data.actions.includes(action.name))
          .map((action) => <RecordAction key={action.name} resource={resource} record={record.data!.record}
            action={action} navigate={navigate}/>)}
      </div>}
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

function MainLayout({ schema, user, onLogout, navigate, route, children, themeMode, toggleTheme }: {
  schema: Schema; user: NonNullable<AuthState["user"]>; onLogout: () => void;
  navigate: (route: string) => void; route: string; children: ReactNode;
  themeMode: ThemeMode; toggleTheme: () => void;
}) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const navigateAndClose = (url: string) => { navigate(url); setDrawerOpen(false); };
  return <div className="app-shell">
    {drawerOpen && <div className="mobile-backdrop" onClick={() => setDrawerOpen(false)}/>}
    <aside className={`sidebar ${drawerOpen ? "open" : ""}`}>
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
        <div className="ra-profile-wrap">
          <button className="ra-profile-trigger" onClick={() => setProfileOpen((value) => !value)}
            aria-expanded={profileOpen} aria-label="Account menu" aria-haspopup="menu">
            <span className="topbar-avatar">{user.username.slice(0, 2).toUpperCase()}</span>
          </button>
          {profileOpen && <><button className="ra-profile-dismiss" aria-label="Close account menu" onClick={() => setProfileOpen(false)}/>
            <div className="ra-profile-menu" role="menu">
              <div className="ra-profile-header"><strong>{user.display_name || user.username}</strong>
                <span>{user.roles.join(", ") || "Member"}</span></div>
              {customProfileMenu && <ProfileMenuExtension user={user} schema={schema} navigate={(url) => {
                navigateAndClose(url); setProfileOpen(false); }} close={() => setProfileOpen(false)}/>}
              <button role="menuitem" onClick={() => { setProfileOpen(false); onLogout(); }}><LogOut size={16}/> Sign out</button>
            </div></>}
        </div></div></header>
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
      return first ? <ResourceList resource={first} navigate={navigate}/> : <Empty title="No resources"/>;
    }
    const segments = route.split("/").map(decodeURIComponent);
    if (segments[0] === "resources") {
      const resource = data.resources.find((r) => r.id === segments[1]);
      if (!resource) return <Empty title="Resource not found" description="This resource isn't available to your account."/>;
      if (!resource.capabilities.list) return <div className="empty"><LockKeyhole size={24}/><strong>Access denied</strong>
        <p>This resource is not available to your account.</p></div>;
      if (segments.length === 2) return <ResourceList key={resource.id} resource={resource} navigate={navigate}/>;
      if (segments[2] === "new" && segments.length === 3 && resource.capabilities.create) return <RecordEditor resource={resource} navigate={navigate} notify={setNotice}/>;
      if (segments.length === 4 && segments[3] === "edit" && resource.capabilities.edit) return <RecordEditor key={segments[2]} resource={resource} id={segments[2]} navigate={navigate} notify={setNotice}/>;
      if (segments.length === 5 && segments[3] === "actions") {
        const action = resource.actions.find((a) => a.name === segments[4] && a.component);
        if (action) return <ActionView key={`${segments[2]}-${action.name}`} resource={resource} schema={data}
          id={segments[2]} action={action} navigate={navigate}/>;
      }
      if (segments.length === 3 && resource.capabilities.show) return <RecordShow key={segments[2]} schema={data} resource={resource} id={segments[2]} navigate={navigate}/>;
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
  return <CurrentAdminProvider currentAdmin={auth.data.user}><MainLayout schema={schema.data} user={auth.data.user} route={route} navigate={navigate} onLogout={logout}
    themeMode={themeMode} toggleTheme={toggleTheme}>
    {ThemeExtension && <ThemeExtension schema={schema.data} mode={themeMode}/>}
    {content}
  </MainLayout></CurrentAdminProvider>;
}

export function App() { return <AdminFeedbackProvider><AdminApp/></AdminFeedbackProvider>; }
