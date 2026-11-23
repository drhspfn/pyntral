import type { ComponentType, ReactNode } from "react";
export type FieldKind = "string" | "number" | "integer" | "boolean" | "date" |
  "datetime" | "time" | "enum" | "json" | "array" | "uuid" | "binary";

export type FieldContext = "list" | "create" | "edit" | "show" | "filter";
export interface FieldViewDef {
  visible: boolean; readonly: boolean; required: boolean;
  component?: string | null; order?: number | null;
}
export interface FieldDef {
  name: string;
  label: string;
  kind: FieldKind;
  required: boolean;
  readonly: boolean;
  nullable: boolean;
  primaryKey: boolean;
  sortable?: boolean;
  widget?: string;
  fileUpload?: { multiple: boolean; maxFiles: number; maxSizeBytes: number;
    maxTotalBytes: number; accept: string; preview: boolean; allowPaste: boolean; mockOnly: true } | null;
  help?: string;
  /** SQLAlchemy String.length, Numeric.precision/scale, or an explicit UI width. */
  maxLength?: number | null;
  precision?: number | null;
  scale?: number | null;
  filterWidth?: number | null;
  dependency?: { source: string; bridge: string } | null;
  span?: 1 | 2;
  options?: string[] | { value: string | number; label: string }[];
  filterOperators?: ("eq" | "neq" | "contains" | "starts_with" | "ends_with" |
    "gt" | "gte" | "lt" | "lte" | "between" | "in" | "not_in")[];
  relation?: { resource: string; field: string };
  components: Partial<Record<FieldContext, string>>;
  views?: Partial<Record<FieldContext, FieldViewDef>>;
}
export interface JobDef {
  name: string;
  label: string;
  confirmation?: string | null;
  cancellable: boolean;
}
export interface ActionDef {
  name: string; label: string; variant: string; confirmation?: string | null;
  position: "row" | "detail" | "both";
  kind?: "record" | "resource" | "bulk";
  appearance: "button" | "badge" | "menu";
  component?: string | null; dialog?: string | null; icon?: IconSpec;
}
export interface LayoutSectionDef {
  id: string;
  title: string;
  kind: "section" | "tab" | "accordion";
  fields: string[];
  visibleIf?: { field: string; equals: unknown } | null;
  defaultOpen: boolean;
  columns?: 1 | 2 | null;
}
export interface ResourceDef {
  id: string;
  label: string;
  icon: IconSpec;
  navigationState?: "enabled" | "locked" | "hidden";
  navigation?: string | null;
  navigationOrder?: number;
  primaryKey: string;
  versionField?: string | null;
  uploads?: boolean;
  uploadMaxBytes?: number | null;
  titleField: string;
  pageSize: number;
  showSearch?: boolean;
  crudViews?: Partial<Record<"list" | "create" | "edit" | "show", string>>;
  layouts?: { form: LayoutSectionDef[]; detail: LayoutSectionDef[] };
  formLayout?: "stack" | "grid";
  detailLayout?: "stack" | "grid";
  fields: FieldDef[];
  listFields: string[];
  searchFields: string[];
  relationships: { name: string; resource: string; many: boolean; label: string; selectable: boolean;
    layout: "table" | "cards"; editable?: boolean }[];
  actions: ActionDef[];
  jobs?: JobDef[];
  capabilities: { list: boolean; select: boolean; create: boolean; edit: boolean; delete: boolean; show: boolean };
}
export interface PageDef {
  name: string; label: string; component: string; icon: IconSpec;
  navigation?: string | null; navigationOrder?: number;
}
export type ThemeMode = "light" | "dark";
export type IconSpec = string | { kind: "svg"; svg: string } |
  { kind: "image"; src?: string | null; light?: string | null; dark?: string | null } | null;
export interface SidebarHeaderConfig {
  title: string; subtitle?: string | null; icon: IconSpec; showIcon: boolean; showTitle: boolean;
  showSubtitle: boolean; align: "left" | "center" | "right"; direction: "horizontal" | "vertical";
  divider: boolean; iconSize: number; logoWidth?: number | null; iconBackground: boolean; linkToDashboard: boolean;
}
export interface SidebarFooterConfig { showUser: boolean; showAvatar: boolean; showRoles: boolean; divider: boolean }
export interface SidebarConfig {
  width: number; minWidth: number; maxWidth: number; mobileWidth: number; resizable: boolean;
  showIcons: boolean; iconSize: number; indent: number; maxIndentDepth: number; dashboardIcon: IconSpec;
  header: SidebarHeaderConfig | null; footer: SidebarFooterConfig | null;
  headerComponent?: string | null; footerComponent?: string | null; itemComponent?: string | null;
}
export interface NavigationConfig { groups: { path: string; icon: IconSpec; order: number }[]; showDashboard: boolean; sidebar?: SidebarConfig }
export interface ThemeConfig {
  default: "light" | "dark" | "system";
  animations: boolean;
  tokens: { light?: Record<string, string>; dark?: Record<string, string> };
}
export interface LocalizationConfig { code: string; messages: Record<string, string>; }
export interface Schema {
  realtime?: boolean;
  localization?: LocalizationConfig;
  title: string; resources: ResourceDef[]; pages: PageDef[];
  navigation: NavigationConfig; theme: ThemeConfig;
  bridges: { name: string; description: string; inputSchema: unknown; outputSchema: unknown }[];
}
export interface Principal {
  id: string; username: string; roles: string[]; display_name: string | null;
  email?: string | null; name?: string; role?: string | null;
  attributes?: Record<string, string | number | boolean | null>;
}
export type RecordData = Record<string, unknown>;
export interface CustomFieldProps {
  field: FieldDef;
  value: unknown;
  record: RecordData;
  resource: ResourceDef;
  mode: "list" | "create" | "edit" | "show" | "filter";
  onChange?: (value: unknown) => void;
}
export interface CustomPageProps { schema: Schema; navigate: (url: string) => void; }
export type FieldComponent = ComponentType<CustomFieldProps>;
export type PageComponent = ComponentType<CustomPageProps>;

export interface CustomActionProps {
  schema: Schema;
  resource: ResourceDef;
  record: RecordData;
  action: ActionDef;
  navigate: (url: string) => void;
  invoke: (payload?: RecordData) => Promise<unknown>;
}
export interface CustomThemeProps {
  schema: Schema;
  mode: ThemeMode;
}
export type ActionComponent = ComponentType<CustomActionProps>;
export interface CustomCollectionActionProps {
  schema: Schema;
  resource: ResourceDef;
  action: ActionDef;
  selectedIds: string[];
  navigate: (route: string) => void;
  invoke: (payload?: RecordData) => Promise<unknown>;
}
export type CollectionActionComponent = ComponentType<CustomCollectionActionProps>;
export type ThemeComponent = ComponentType<CustomThemeProps>;

export interface ProfileMenuProps {
  user: Principal;
  schema: Schema;
  navigate: (url: string) => void;
  close: () => void;
}
export type ProfileMenuComponent = ComponentType<ProfileMenuProps>;

export interface ActionDialogProps {
  resource: ResourceDef;
  record: RecordData;
  action: ActionDef;
}
export type ActionDialogComponent = ComponentType<ActionDialogProps>;

export interface AuthState { user: Principal | null; csrf: string | null }

export interface AccessDeniedProps { resource: ResourceDef; currentAdmin: Principal }
export type AccessDeniedComponent = ComponentType<AccessDeniedProps>;

export interface LoginScreenProps { onAuthenticated: (auth: AuthState) => void }
export type LoginScreenComponent = ComponentType<LoginScreenProps>;

export interface CustomCrudProps {
  schema: Schema;
  resource: ResourceDef;
  mode: "list" | "create" | "edit" | "show";
  record?: RecordData;
  navigate: (route: string) => void;
  /** List queries are validated and scoped by the server. */
  loadList: (params?: Record<string, string | number | boolean>) => Promise<{
    items: RecordData[]; total: number; offset: number; limit: number;
  }>;
  save: (payload: RecordData) => Promise<RecordData>;
  remove: () => Promise<void>;
  reload: () => Promise<void>;
}
export type CrudComponent = ComponentType<CustomCrudProps>;

/** Resolve view presentation without weakening backend field authorization. */
export function fieldForView(field: FieldDef, mode: FieldContext): FieldDef {
  const view = field.views?.[mode];
  if (!view) return field;
  return {
    ...field,
    readonly: view.readonly,
    required: view.required,
    components: view.component ? { ...field.components, [mode]: view.component } : field.components,
  };
}
export function viewFields(fields: FieldDef[], mode: FieldContext): FieldDef[] {
  return fields.filter((field) => field.views?.[mode]?.visible !== false)
    .map((field) => fieldForView(field, mode))
    .sort((a, b) => {
      const av = a.views?.[mode]?.order ?? Number.MAX_SAFE_INTEGER;
      const bv = b.views?.[mode]?.order ?? Number.MAX_SAFE_INTEGER;
      return av - bv;
    });
}

/** Custom sidebar regions own presentation; navigation callbacks preserve router guards. */
export interface SidebarRegionProps {
  schema: Schema; config: SidebarConfig; user: Principal; themeMode: ThemeMode;
  navigate: (route: string) => void; close: () => void; children: ReactNode;
}
export type SidebarRegionComponent = ComponentType<SidebarRegionProps>;
export interface SidebarItemProps {
  type: "group" | "resource" | "page" | "dashboard"; id: string; label: string;
  icon: IconSpec; depth: number; active: boolean; locked: boolean; open?: boolean;
  /** Render the content inside the built-in accessible navigation button, not another button. */
  children: ReactNode; schema: Schema;
}
export type SidebarItemComponent = ComponentType<SidebarItemProps>;
