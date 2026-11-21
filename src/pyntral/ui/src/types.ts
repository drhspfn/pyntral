import type { ComponentType } from "react";
export type FieldKind = "string" | "number" | "integer" | "boolean" | "date" |
  "datetime" | "time" | "enum" | "json" | "array" | "uuid" | "binary";

export interface FieldDef {
  name: string;
  label: string;
  kind: FieldKind;
  required: boolean;
  readonly: boolean;
  nullable: boolean;
  primaryKey: boolean;
  widget?: string;
  help?: string;
  /** SQLAlchemy String.length, Numeric.precision/scale, or an explicit UI width. */
  maxLength?: number | null;
  precision?: number | null;
  scale?: number | null;
  filterWidth?: number | null;
  span?: 1 | 2;
  options?: string[] | { value: string | number; label: string }[];
  filterOperators?: ("eq" | "neq" | "contains" | "starts_with" | "ends_with" |
    "gt" | "gte" | "lt" | "lte" | "between" | "in" | "not_in")[];
  relation?: { resource: string; field: string };
  components: Partial<Record<"list" | "edit" | "show" | "filter", string>>;
}
export interface ActionDef {
  name: string; label: string; variant: string; confirmation?: string | null;
  position: "row" | "detail" | "both";
  appearance: "button" | "badge" | "menu";
  component?: string | null; dialog?: string | null; icon?: string | null;
}
export interface ResourceDef {
  id: string;
  label: string;
  icon: string;
  navigationState?: "enabled" | "locked" | "hidden";
  navigation?: string | null;
  navigationOrder?: number;
  primaryKey: string;
  titleField: string;
  pageSize: number;
  showSearch?: boolean;
  formLayout?: "stack" | "grid";
  detailLayout?: "stack" | "grid";
  fields: FieldDef[];
  listFields: string[];
  searchFields: string[];
  relationships: { name: string; resource: string; many: boolean; label: string; selectable: boolean; layout: "table" | "cards" }[];
  actions: ActionDef[];
  capabilities: { list: boolean; select: boolean; create: boolean; edit: boolean; delete: boolean; show: boolean };
}
export interface PageDef {
  name: string; label: string; component: string; icon: string;
  navigation?: string | null; navigationOrder?: number;
}
export type ThemeMode = "light" | "dark";
export interface NavigationConfig { groups: { path: string; icon: string; order: number }[]; showDashboard: boolean }
export interface ThemeConfig {
  default: "light" | "dark" | "system";
  animations: boolean;
  tokens: { light?: Record<string, string>; dark?: Record<string, string> };
}
export interface Schema {
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
  mode: "list" | "edit" | "show" | "filter";
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
