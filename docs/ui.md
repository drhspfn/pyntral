# React components, layout, and theming

[Documentation index](README.md) · [Extensions](extensions.md)

The Pyntral frontend is a React SPA. Its base CSS and reusable components live in `src/pyntral/ui/src/`; custom components are compiled with the same Vite toolchain and can import public aliases such as `@pyntral/ui`.

## Available UI primitives

```tsx
import {
  Button, Badge, Card, TextInput, Textarea, FormField,
  Checkbox, CheckboxGroup, RadioGroup, Switch, ToggleGroup, SortableList,
  SearchInput, Select, AsyncSelect, DatePicker, Calendar, Dialog,
  Tabs, TabList, Tab, TabPanel, Table, DataTable, CodeBlock, JsonView,
  FileUpload, FileRow, Collapsible, OverflowText, Icon, Brand,
  Popover, PopoverTrigger, PopoverContent, PopoverHeader, PopoverFooter, PopoverClose,
} from "@pyntral/ui";
```

| Component | Main props / behavior |
| --- | --- |
| `Button` | `variant` (`primary`, `secondary`, `ghost`, `danger`), `loading`, `startIcon`, `endIcon`, native button attributes. |
| `Badge` | `tone` (`neutral`, `success`, `danger`, `primary`). |
| `Card` | `title`, `description`, `children`. |
| `TextInput`, `Textarea` | Native input/textarea props with theme styles. |
| `FormField` | `label`, `htmlFor`, `hint`, `required`, `span`. |
| `Checkbox` | Controlled `checked`, `onCheckedChange`, optional label/description and `indeterminate` mixed state. |
| `Switch` | Controlled boolean state, native keyboard-operable switch semantics. |
| `CheckboxGroup` | Multiple selected values; optional `minSelected`/`maxSelected` limits. |
| `RadioGroup` | Exclusive choice; native radio-keyboard semantics. |
| `ToggleGroup` | Segmented single-choice radios or multiple-choice checkboxes. |
| `SortableList` | Controlled reorderable list; mouse, touch and pen drag handles, keyboard reordering and Escape cancellation. |
| `SearchInput` | Controlled `value`, `onChange`, `onSearch`, optional search icon / submit button placement. |
| `Select` | Static `options` or `loadOptions(query)`, `multiple`, `searchable`, `maxItems`, `maxSelections`, `popupMinHeight`, `popupMaxHeight`. |
| `AsyncSelect` | Wrapper for server-loaded searchable options. |
| `DatePicker`, `Calendar` | Theme-aware date selection with popup placement. |
| `Dialog` | Reusable dialog primitive; for global actions use `useAdminFeedback().confirm()`. |
| `Tabs`, `TabList`, `Tab`, `TabPanel` | Compound tabs with controlled/uncontrolled state. |
| `Table`, `DataTable` | Shared semantic table shell and typed data grid. |
| `CodeBlock`, `JsonView` | Read-only inline or multiline source and JSON viewers; copy, collapse, format and highlight. |
| `FileUpload`, `FileRow` | Controlled selection, explicit upload callback and file rows. |
| `Collapsible`, `OverflowText` | Disclosure and truncated labels. |
| `Icon`, `Brand` | Shared icon and branding primitives. |
| `Popover` and parts | Compound floating content. |

### Selection example

```tsx
import { Select, type SelectOption } from "@pyntral/ui";
import { useState } from "react";

const options: SelectOption<string>[] = [
  { value: "a", label: "Alpha" }, { value: "b", label: "Beta" },
];
export function TagSelector() {
  const [tags, setTags] = useState<string[]>([]);
  return <Select<string>
    value={tags}
    onChange={(value) => setTags(value as string[])}
    options={options}
    multiple searchable maxItems={3} maxSelections={5}
    placeholder="Choose tags"
  />;
}
```

`maxItems` limits the number of **visible chips**, collapsing the rest into `+N`; `maxSelections` limits how many may be selected. Dropdowns are rendered in viewport-aware portals and may flip vertically when there is insufficient space.

### Accessible choice controls

All five choice atoms are exported through the public `@pyntral/ui` alias and
use native HTML inputs with themed markers. Space toggles a focused checkbox
or switch; arrow keys navigate radio choices. Focus, disabled and mixed
(indeterminate) states work in light and dark modes without extra libraries.

```tsx
import { Checkbox, CheckboxGroup, RadioGroup, Switch, ToggleGroup } from "@pyntral/ui";

<Checkbox checked={enabled} onCheckedChange={setEnabled} label="Enabled" />
<Switch checked={alerts} onCheckedChange={setAlerts} label="Alerts" />
<CheckboxGroup<string> value={channels} onValueChange={setChannels}
  maxSelected={2} options={[
    { value: "email", label: "Email" }, { value: "sms", label: "SMS" },
    { value: "push", label: "Push" },
  ]} />
<RadioGroup<string> value={priority} onValueChange={setPriority}
  options={[{ value: "normal", label: "Normal" }, { value: "high", label: "High" }]} />
<ToggleGroup<string> value={density} onValueChange={setDensity}
  options={[{ value: "compact", label: "Compact" }, { value: "comfortable", label: "Comfortable" }]} />
```

For mutually exclusive selection use `RadioGroup` or single-mode `ToggleGroup`.
Use `CheckboxGroup` for multiple choices with an optional selection cap.
The interactive demo is at **Agents → Insights → Choice controls**.

### Drag-and-drop ordering

`SortableList` is a public controlled atom from `@pyntral/ui`. The built-in
**Columns → Customize table** panel uses the same component. Only its handle
starts a drag; embedded checkboxes and buttons continue to work. Pointer
gestures support mouse, touch and pen. With keyboard focus on a handle, press
Space/Enter to lift, Up/Down to move, Space/Enter to drop, Escape to cancel.
The parent receives the reordered array only after a successful drop.

```tsx
import { useState } from "react";
import { SortableList } from "@pyntral/ui";

export function Steps() {
  const [steps, setSteps] = useState([{id:"review",label:"Review"},{id:"publish",label:"Publish"}]);
  return <SortableList items={steps} getKey={(item) => item.id}
    getLabel={(item) => item.label} renderItem={(item) => <span>{item.label}</span>}
    onReorder={setSteps} ariaLabel="Workflow steps" />;
}
```

Use unique, stable keys (not indexes); callers own persistence. See the
**Agents → Insights → Drag to reorder** interactive demo.

## Global toasts and dialogs

```tsx
import { useAdminFeedback } from "@pyntral/feedback";

function ArchiveButton() {
  const { confirm, toast } = useAdminFeedback();
  const archive = async () => {
    const accepted = await confirm({
      title: "Archive this record?", confirmLabel: "Archive", destructive: true,
    });
    if (!accepted) return;
    try { /* invoke your authenticated API here */
      toast("Archived", { kind: "success" });
    } catch { toast("Archive failed", { kind: "error" }); }
  };
  return <button onClick={archive}>Archive</button>;
}
```

`toast(message, { kind, duration })` supports `success`, `info`, and `error`. `confirm(options)` returns a boolean; `dismiss(id)` is also available. UI actions should use proper mutation invalidation to refresh cached resources after success.

## Theme tokens and modes

```python
admin = Admin(
    app, session_factory=SessionLocal, auth=auth, secret_key=secret,
    default_theme="system", animations=False,
    theme={
        "light": {"primary": "#266d9d", "scrollbar-width": "8px"},
        "dark": {"primary": "#8bbfe3", "scrollbar-thumb": "#435968"},
    },
)
```

The UI prefixes custom variables with `--ra-` (for example, `primary` → `--ra-primary`). Set variables for `light` and `dark` separately; components should reference CSS custom properties rather than hard-coded colors. `default_theme` is `system`, `light`, or `dark`. `animations=False` applies the shared reduced-motion switch.

When `primary` is overridden, the UI derives missing `primary-hover`, `primary-soft` and `sidebar-active` using the accent and current surface tokens. For opaque CSS colors normalized to hex, it chooses black or white `on-primary` using WCAG contrast. Explicit values for any derived token take precedence, including values inherited from the global theme. For translucent or complex CSS colors, specify `on-primary` explicitly. Both button implementations use the hover color for their fill and border; checked controls share `on-primary` for contrast.

Syntax highlighting tokens include `code-keyword`, `code-string`, `code-number`, `code-name`, and `code-comment`. Set them independently in `theme.light` / `theme.dark` using the same prefix-free names. See [code viewers](#codeblock-and-jsonview).

Scrollbar tokens include `scrollbar-width`, `scrollbar-track`, `scrollbar-thumb`, `scrollbar-thumb-hover`, and `scrollbar-radius`; Firefox supports a more limited scrollbar customization than Chromium/WebKit.

Form and detail layout can be `stack` or `grid` on each resource. Custom component classes are free to use these tokens; avoid changing core styles globally when a scoped CSS class suffices.

## Personal table preferences

List views provide a compact anchored **Columns** panel with themed choice
controls for hide/reorder columns, one pinned column, density, and up
to ten named filter presets. Preferences use the local browser's `localStorage`
keyed by the current administrator ID and resource ID; they do not alter
server-side field permissions. Filter presets are **explicitly** saved and may
contain search strings; do not store sensitive searches on shared computers.
Bulk selection can span list pages while the current filters remain unchanged.

## Localization

Configure `Admin(default_locale="en", translations={"fr": {"nav.overview":
"Vue d\'ensemble"}, "de": {"nav.overview": "Übersicht"}}, locale_resolver=callback)`.
The verified principal determines the selected locale; the API exposes only
its code and message dictionary. Core navigation/toolbars/CRUD use translation
keys with English fallback. Calendars format months, weekdays and dates using
the locale; custom components can import `useI18n()` from `@pyntral/i18n`.
Unknown translation keys fall back to their English source text. External
custom login screens may supply their own strings; the standard sign-in UI uses the public login localization dictionary.

## Server-resolved per-user themes

`Admin(theme_resolver=callback)` supports sync or async callbacks taking a
verified `Principal`. Return `{"default": "dark", "tokens": {"dark":
{"primary": "#b2b5ff"}}}` to override the theme for that user.
Only `light` and `dark` token maps are accepted; invalid token key syntax,
non-string values and invalid mode names fail explicitly. Derived accent tokens are resolved after merging global and per-user overrides. All values are
presentation data, never permission/role controls.

## CSV / JSON resource exports

A resource's list toolbar offers CSV or JSON export using the **current search, filters and sort**. Choose the current page, all matching rows (up to 10,000), or a custom skip/take range. Export the current visible columns in their table order or all available list columns.

The authenticated `GET /api/resources/{name}/export` endpoint accepts `format=csv|json`, `offset`, `limit` (1–10,000), optional comma-separated `columns`, and the same `q`, `sort`, `desc`, and `filter.*` parameters as list. Every batch applies resource scoping, list/filter permission checks and per-record field visibility. Unauthorized columns are rejected, and CSV values beginning with spreadsheet formula markers are escaped. Responses disable caching and include `X-Export-Rows`.

This is a bounded, multi-query export rather than a point-in-time database snapshot: concurrent inserts/deletes during an export can alter offset pagination. For large, audit-grade snapshots use a dedicated background job and a consistent transactional read. CSV/JSON **import is intentionally not implemented**; schema validation, permission checks, and all-or-nothing transactions must be designed before exposing writes.

## Localized resource labels

Resource, field, action, job, relationship, page and layout-section labels can be **literal strings** or explicit translation references starting with `@` (for example, `Field(label="@fields.title")`). Define translations in `Admin(translations={"en": {"fields.title": "Title"}, "de": {"fields.title": "Titel"}})`. The server resolves references for the authenticated administrator's locale, falls back to the English dictionary, then to the untranslated key. It never interprets arbitrary literals as keys, and translation does not grant permissions. To change the locale for an administrator, use `locale_resolver` and refetch the schema.

Pyntral ships English source strings plus core French (`fr`) and German (`de`) translations. Other locales remain available through application dictionaries and use English fallback for missing entries. `Admin(translations=...)` overrides bundled messages for matching keys. This initial catalog covers navigation and common list/CRUD commands; other UI strings still require translation-key migration.

## Theme token audit

Core CSS palette, overlay colors, component elevation shadows, and primary-button contrast are defined through `--ra-*` variables instead of component-local color literals. The automated `test_theme_tokens.py` guard rejects hard-coded hex or RGB colors in built-in component declarations. Themes may override those tokens in either light or dark mode. This audit covers the bundled stylesheet, not user-provided TSX extension styles or inline third-party widget styles.

## Compound Popover

Import `Popover`, `PopoverTrigger`, `PopoverContent`, `PopoverHeader`, `PopoverFooter`, and `PopoverClose` from `@pyntral/ui`. Example: `<Popover interaction="click"><PopoverTrigger asChild><button>Options</button></PopoverTrigger><PopoverContent width={360} minHeight={180} maxHeight={520} align="end"><PopoverHeader>Options</PopoverHeader>Content<PopoverFooter>Actions</PopoverFooter></PopoverContent></Popover>`. Supports `open`/`onOpenChange`, `defaultOpen`, `interaction="click"|"hover"|"both"`, delays in milliseconds, outside/Escape dismissal flags, responsive positioning with automatic upward flip, clipped-height scrolling, and nested portalled Select/DatePicker/operator menus. Export, Columns, Filters and the profile menu use this atom.

### Saved filter presets

The Filters popover uses the public searchable `Select` for saved presets (never a native `<select>`). Selecting a preset applies it immediately and resets the pagination offset. The Select remains unselected to make repeated selection possible. The responsive preset toolbar gives the name input more width than the preset dropdown, with a content-width Save button; container queries wrap the button and then stack all controls when the popover is narrow.

## Mobile navigation and unsaved editor changes

On narrow screens, resource heading actions wrap without overflowing. The mobile drawer uses viewport-height containment and touch scrolling, and locks background document scrolling while open. Built-in editors show View record and Delete actions when authorized, return to record details from edit mode, and protect unsaved changes during in-app navigation. The browser's native `beforeunload` prompt handles tab closing/reloading. Custom CRUD overrides remain responsible for their own dirty state and guards.

## Controlled FileUpload (mock-first)

`FileUpload` is a reusable `@pyntral/ui` atom with `files: File[]` and `onFilesChange`. It supports keyboard file selection, drag-and-drop, clipboard paste scoped to the dropzone, MIME/extension `accept`, single/multiple mode, per-file and aggregate byte limits, max count, deduplication, optional raster image thumbnails (PNG/JPEG/GIF/WebP/AVIF), removal, error callbacks and responsive rows. Object URLs are revoked when previews unmount. Files are **not uploaded** by default.

A host may supply `onUpload(file, {signal, onProgress})` and `onUploaded(receipts)` to explicitly own the future upload transport. This atom does not discover remote URLs, call a Bridge, authorize an S3 bucket or persist a database file record on its own. The application must create a scoped, short-lived upload grant through its authenticated backend, enforce max size/type and authorization server-side, upload with explicit network policy (signed headers/origin, expiry, no credentials leakage), then finalize a file entity only after verifying the uploaded object. `onUpload` is sequential and cancellable; its callback is responsible for request timeouts, checksums, retries and revoking unused grants.

The Shop Demo Insights page contains one multi-file picker with previews and one single-file picker without previews. Both use mock selection only.

File validation errors use actionable messages with actual and configured byte sizes, accepted types, selection limits, and duplicate information. The public `formatFileRejection(rejection, constraints)` helper powers the inline accessible error; the Shop mock demo additionally shows the same message through a toast. The callback still returns stable reason codes for custom UX.

### File rows and record attachments

`FileRow` is exported from `@pyntral/ui` for both selected and persisted files. It takes `name`, `size` (bytes), optional `mimeType`, local `file` or remote `previewUrl`, `preview`, download `href`, optional controlled `onRemove`, and `disabled`. Removing a row from `FileUpload` updates its controlled `files` via `onFilesChange`. Consumers may supply `actions` to add their own submit controls. The built-in record attachment panel uses the resource's server-provided upload limit, and lazily previews supported persisted raster images up to 5 MiB via the authorized download endpoint. Other files retain a file icon; failed previews do not prevent downloading.

### Collapsible and truncated labels

```tsx
import { Button, Collapsible, OverflowText } from "@pyntral/ui";

<Collapsible header="Full content" defaultOpen
  actions={open => <Button type="button" onClick={onEdit}>{open ? "Edit" : "Open editor"}</Button>}>
  <p>Content</p>
</Collapsible>
```

`Collapsible` accepts `open` and `onOpenChange` for controlled mode, `defaultOpen` for uncontrolled mode, `disabled`, custom non-interactive `header` content, and separate `actions` that remain available even while closed. Both header and actions may be render functions receiving the current open state. The disclosure is a keyboard-accessible button; the content remains mounted when collapsed. `OverflowText` renders an ellipsized text label and shows a themed tooltip on hover or keyboard focus only when the label is actually clipped. It is used in sidebar navigation. Desktop sidebar width can be adjusted by dragging the separator or using arrow keys when it is focused (Home/End select the limits).

## Sidebar branding and navigation icons

The generic SPA consumes the sidebar configuration directly from the authenticated schema.
The default header now displays `Admin.title` rather than a hard-coded Pyntral brand.
No TSX or frontend rebuild is necessary when using a distribution that supports this API.

```python
from pyntral import Admin, SidebarConfig, SidebarHeader, SidebarFooter, SvgIcon, ImageIcon

admin = Admin(
    app, session_factory=Session, auth=auth, secret_key=secret,
    title="Shop administration",
    sidebar=SidebarConfig(
        width=260, min_width=238, max_width=420, mobile_width=260,
        resizable=True, show_icons=True, icon_size=18,
        indent=9, max_indent_depth=5, dashboard_icon="house",
        header=SidebarHeader(
            title="My Shop", subtitle="Administration panel",
            icon=SvgIcon.from_file("assets/logo.svg"),
            show_icon=True, show_title=True, show_subtitle=True,
            align="left", direction="horizontal", divider=True,
            icon_size=32, logo_width=32, icon_background=False,
            link_to_dashboard=True,
        ),
        footer=SidebarFooter(show_user=True, show_avatar=True, show_roles=True),
    ),
)
```

- `header=None` or `footer=None` hides that built-in region. `SidebarHeader(title=None)` inherits the application title.
- Header alignment supports `left`, `center`, and `right`; direction supports `horizontal` and `vertical`. The independent `show_*` switches allow icon-only or text-only branding.
- For a full-width wordmark, use a vertical header with `show_title=False`, `show_subtitle=False`, `icon_background=False`, and explicit `logo_width`/ `icon_size`. Images retain their aspect ratio.
- The desktop separator is shown only if resizing is enabled and the effective width range permits it. The configured width bounds are constrained to 42% of the desktop viewport when needed. The mobile drawer uses `mobile_width` independently. Width changes are local to the mounted UI.
- `show_icons=False` hides navigation glyphs while preserving disclosure and access-lock indicators. Header icons are controlled independently.
- `Icon` is exported from `@pyntral/ui`: `<Icon icon="shopping-cart" size={18}/>`. It uses the bundled Lucide dynamic catalogue, loading icons on demand; unknown names use a contextual fallback. This also means the distribution includes the catalogue's lazy chunks.
- `SvgIcon` accepts raw SVG or `SvgIcon.from_file(path)`. The XML is validated and displayed in an isolated image context, never as inline DOM or executable markup. SVG colors are the colors authored in the file (not inherited CSS).
- `ImageIcon(src="/static/logo.webp")` uses an existing image route. `ImageIcon(light="/static/logo-dark.svg", dark="/static/logo-light.svg")` follows the UI theme. Relative URLs resolve against the mounted admin base; absolute paths and HTTP(S) URLs also work. The app must serve these files and permit them in its CSP.
- `icon=None` hides a specific navigation/resource/action icon. Use the canonical kebab-case Lucide names for strings.

For fully custom header, footer and item presentation, see [React extensions](extensions.md#sidebar-extensions).

## Login screen customization

The built-in sign-in screen defaults to a single centered card. It shares
`Brand`, `Icon`, `Button`, `Card`, `FormField` and `TextInput` with the
administration interface. It inherits the sidebar logo/title/subtitle unless
a separate `SidebarHeader` is passed as `LoginConfig.brand`.

```python
from pyntral import LoginConfig, SidebarConfig, SidebarHeader, SvgIcon

sidebar = SidebarConfig(
    header=SidebarHeader(title="My workspace", icon=SvgIcon.from_file("assets/logo.svg"))
)
login = LoginConfig(
    layout="centered", max_width=420, card=True,
    brand_position="form", brand_align="center", brand_direction="vertical",
    title="Sign in", subtitle="Use your work account.",
    footer="Internal workspace", show_theme_toggle=True,
    show_password_toggle=True,
)
# Pass sidebar=sidebar and login=login to Admin(...)
```

For a two-column page, use:

```python
login = LoginConfig(
    layout="split", side_position="right", brand_position="side",
    side_title="Manage your workspace", side_description="One place for your operations.",
    form_align="left", card=False, max_width=380,
)
```

On viewports up to 800 px the second panel is hidden and its brand is shown
with the form. The theme switch is available before sign-in and uses the
same local browser preference as the admin header. If no explicit preference
is saved, the public global default theme (or system preference) applies;
after authentication, a per-user theme resolver may override that default.
Logging out removes per-user tokens and reapplies global public tokens.

All normal theme tokens apply before authentication, including `primary`,
`primary-hover`, `on-primary`, `input`, `text`, `border` and `radius`.
Login-specific overrides are optional and fall back to the shared palette:

| Token key passed to Admin(theme=...) | Default fallback |
| --- | --- |
| `login-bg` | bg |
| `login-card-bg` | surface |
| `login-card-border` | border |
| `login-card-radius` | radius |
| `login-card-shadow` | shadow |
| `login-side-bg` | surface |

For example, `theme={"light": {"login-card-radius": "16px"}, "dark": {"login-card-radius": "16px"}}`.
The global theme and login presentation are public; do not include private
tokens or secret-bearing image URLs. Authentication and permission rules
are unchanged.

Standard form labels support `login.title`, `login.subtitle`,
`login.username`, `login.password`, `login.submit`, `login.show_password`,
`login.hide_password`, and `login.toggle_theme` translations. Explicit
non-default label strings take precedence. The default locale is used before
sign-in. Custom `auth.login` extensions receive the public config and theme
controls; see [extensions](extensions.md).

## Tabs and tables

`@pyntral/ui` exports controlled/uncontrolled compound tabs. The standard CRUD
layout also uses these primitives. Arrow Left/Right, Home/End and disabled
tabs are supported; panels have linked ARIA IDs. Use `keepMounted` to retain
inactive component state.

```tsx
import { Tabs, TabList, Tab, TabPanel, DataTable } from "@pyntral/ui";

<Tabs defaultValue="jobs">
  <TabList label="Operations"><Tab value="jobs">Jobs</Tab><Tab value="history">History</Tab></TabList>
  <TabPanel value="jobs">
    <DataTable rows={jobs} getRowKey={row => row.id} columns={[
      { id: "name", header: "Name", cell: row => row.name },
      { id: "status", header: "Status", cell: row => row.status },
    ]}/>
  </TabPanel>
  <TabPanel value="history">History content</TabPanel>
</Tabs>
```

### Tabs props

| Component | Props |
| --- | --- |
| `Tabs` | `children`, `value?`, `defaultValue?`, `onValueChange?`, `className?` |
| `TabList` | `children`, `label?` (default "Tabs"), `className?` |
| `Tab` | `value`, `children`, `disabled?` |
| `TabPanel` | `value`, `children`, `keepMounted?` (false), `className?` |

Each tab and its panel share a unique value within one Tabs group.
Without a valid initial selection, the first enabled tab is selected.
In controlled mode, update value in onValueChange. Inactive panels unmount
by default; keepMounted retains their state.

### Table and DataTable props

| Component | Props |
| --- | --- |
| `Table` | `children` (native thead/tbody), `label?`, `compact?`, `className?`, `style?` |
| `DataTable<Row>` | `rows`, `columns`, `getRowKey`, `label?`, `compact?`, `loading?`, `empty?`, `className?`, `sort?`, `onSortChange?` |
| `DataColumn<Row>` | `id`, `header`, `cell(row)`, `className?`, `sortable?` |

`DataTableProps<Row>`, `DataColumn<Row>`, and `TabsProps` are public types.
The sort callback emits `{ column, direction: "asc" | "desc" }`; sort the rows
or refetch server data and pass the result back. Supply stable row keys and
unique column IDs. Loading replaces rows; empty defaults to "No records".
The table scrolls horizontally on narrow screens.

`Table` is the shared semantic table shell for custom thead/tbody markup.
`DataTable<Row>` accepts rows, typed columns, row keys, loading/empty states,
compact density and controlled sorting. It does not fetch or paginate data
automatically; use application query state and your bridge/API.

## Browser title and favicon

`Admin(title="Solaris Atlas · Admin", favicon=SvgIcon.from_file("logo.svg"))`
sets the browser title and favicon as well as the application title. When
favicon is omitted, a sidebar header SvgIcon is inherited; otherwise the
standard bundled favicon is used. Explicit `Path("logo.svg")`,
`Path("logo.png")` or `Path("logo.ico")` are supported. Files are read at
configuration time and bounded in size. The mount-relative public
`/auth/favicon` route and `/favicon.svg` compatibility route work without
authentication, including under ASGI proxy prefixes. The development client
sets document.title when public login configuration arrives; the production
HTML title is escaped and rendered by the server. No custom middleware or
frontend rebuild is needed to change branding.

## Sidebar search

```python
sidebar = SidebarConfig(show_search=True, search_placeholder="Find a resource or page")
```

Search is disabled by default. When enabled, the field stays above the
scrolling navigation tree. It matches authorized resource/page labels and
IDs and category paths, case-insensitively and accent-insensitively (all search words must match); matching categories include
their descendants and matching leaves retain their ancestors. Search
temporarily expands matching branches and does not alter manual expansion
state. Locked entries remain locked. Clearing the search restores the
tree. It works in the mobile drawer as well. When omitted, the placeholder
uses the current UI locale.

## CodeBlock and JsonView

```tsx
import { CodeBlock, JsonView } from "@pyntral/ui";

<CodeBlock code={source} language="auto" title="Source"
  highlight collapsible copyable maxHeight={320}/>

<JsonView value={response.payload} title="Request payload"
  format formatToggle highlightToggle defaultCollapsed collapsible
  minHeight={80} maxHeight={280} wrap/>

<CodeBlock code="SELECT * FROM products" language="sql" inline/>
```

| Prop | Contract / default |
| --- | --- |
| `code` / `value` | CodeBlock takes source text; JsonView takes an object or serialized JSON string. |
| `language` | auto (default), explicit name/alias or plaintext; JsonView always uses JSON. |
| `title`, `showLanguage` | Optional title, language label visible by default. |
| `inline` | False; true renders a compact code span without toolbar. |
| `highlight`, `highlightToggle` | True / false; optional user-facing toggle. |
| `format`, `formatToggle` | True / true; formatting and toggle only apply to valid JSON. |
| `indent` | 2 spaces; clamped to 0–8. |
| `copyable` | True; copies exactly the displayed text, with clipboard success/error feedback. |
| `collapsible`, `defaultCollapsed` | False / false. |
| `collapsed`, `onCollapsedChange` | Optional controlled collapse state. |
| `wrap` | False; use true for wrapped lines instead of horizontal scrolling. |
| `minHeight`, `maxHeight` | Code body size (px or CSS length); max defaults to 360px. |
| `minWidth`, `maxWidth`, `fontSize`, `className`, `style` | Layout and visual overrides; width defaults to max 100%. |

Both props types are exported. The viewers use the inherited light/dark
palette with optional CSS overrides for `--ra-code-keyword`,
`--ra-code-string`, `--ra-code-number`, `--ra-code-name`, and
`--ra-code-comment`. Highlight.js uses a bounded grammar set (JSON, C#,
JavaScript, TypeScript, Python, SQL, Bash, XML/HTML, CSS, YAML). Auto
detection is heuristic; specify the language for ambiguous snippets.
Raw input is never treated as HTML. JSON formatting preserves numeric
lexemes, duplicate keys and string contents when given the original JSON text;
invalid JSON is displayed unchanged. For JsonView values already parsed as
JavaScript objects, precision or duplicate keys lost during parsing cannot be
recovered. Pass the original serialized text when exact numeric lexemes matter.
Explicit aliases include c#, cs, js, ts, py, sh, html and yml. Unknown languages
remain plain text. Formatting is limited to 100,000 input characters, depth 256
and roughly 1 MiB of formatted output; language detection and highlighting
are skipped above 12,000 and 40,000 characters respectively. Large logs
remain visible and copyable. This is a viewer, not an editor or a general
language formatter. Clipboard copying requires a browser secure context
or localhost. `format` and `highlight` set defaults; their optional toolbar
buttons allow a local override. Inline mode omits the toolbar and collapse.
For controlled collapse, use collapsible with collapsed and onCollapsedChange.
The built-in record detail renderer uses JsonView for JSON
and array fields, while lists keep compact previews. See the
[Insights playground](../admin/Insights.tsx).
