declare module "virtual:pyntral-extensions" {
  import type { FieldComponent, PageComponent, ActionComponent, ThemeComponent, ProfileMenuComponent, ActionDialogComponent, AccessDeniedComponent, LoginScreenComponent, CrudComponent, SidebarRegionComponent, SidebarItemComponent } from "@pyntral/types";
  export const fields: Record<string, FieldComponent>;
  export const pages: Record<string, PageComponent>;
  export const actions: Record<string, ActionComponent>;
  export const dialogs: Record<string, ActionDialogComponent>;
  export const profile: Record<string, ProfileMenuComponent>;
  export const themes: Record<string, ThemeComponent>;
  export const access: Record<string, AccessDeniedComponent>;
  export const crud: Record<string, CrudComponent>;
  export const sidebarHeaders: Record<string, SidebarRegionComponent>;
  export const sidebarFooters: Record<string, SidebarRegionComponent>;
  export const sidebarItems: Record<string, SidebarItemComponent>;
  export const auth: Record<string, LoginScreenComponent>;
}
