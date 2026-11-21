# React components, layout, and theming

[Documentation index](README.md) · [Extensions](extensions.md)

The Pyntral frontend is a React SPA. Its base CSS and reusable components live in `src/pyntral/ui/src/`; custom components are compiled with the same Vite toolchain and can import public aliases such as `@pyntral/ui`.

## Available UI primitives

```tsx
import {
  Button, Badge, Card, TextInput, Textarea, FormField,
  Checkbox, CheckboxGroup, RadioGroup, Switch, ToggleGroup, SortableList,
  SearchInput, Select, AsyncSelect, DatePicker, Calendar, Dialog,
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

Configure `Admin(default_locale="en", translations={"ru": {"nav.overview":
"Обзор", "table.filters": "Фильтры"}}, locale_resolver=callback)`.
The verified principal determines the selected locale; the API exposes only
its code and message dictionary. Core navigation/toolbars/CRUD use translation
keys with English fallback. Calendars format months, weekdays and dates using
the locale; custom components can import `useI18n()` from `@pyntral/i18n`.
Unknown translation keys fall back to their English source text. External
login screens must provide their own localized strings.

## Server-resolved per-user themes

`Admin(theme_resolver=callback)` supports sync or async callbacks taking a
verified `Principal`. Return `{"default": "dark", "tokens": {"dark":
{"primary": "#b2b5ff"}}}` to override the theme for that user.
Only `light` and `dark` token maps are accepted; unrecognized token names,
non-string values and invalid mode names fail explicitly. All values are
presentation data, never permission/role controls.

## CSV / JSON resource exports

A resource's list toolbar offers CSV or JSON export using the **current search, filters and sort**. Choose the current page, all matching rows (up to 10,000), or a custom skip/take range. Export the current visible columns in their table order or all available list columns.

The authenticated `GET /api/resources/{name}/export` endpoint accepts `format=csv|json`, `offset`, `limit` (1–10,000), optional comma-separated `columns`, and the same `q`, `sort`, `desc`, and `filter.*` parameters as list. Every batch applies resource scoping, list/filter permission checks and per-record field visibility. Unauthorized columns are rejected, and CSV values beginning with spreadsheet formula markers are escaped. Responses disable caching and include `X-Export-Rows`.

This is a bounded, multi-query export rather than a point-in-time database snapshot: concurrent inserts/deletes during an export can alter offset pagination. For large, audit-grade snapshots use a dedicated background job and a consistent transactional read. CSV/JSON **import is intentionally not implemented**; schema validation, permission checks, and all-or-nothing transactions must be designed before exposing writes.

## Localized resource labels

Resource, field, action, job, relationship, page and layout-section labels can be **literal strings** or explicit translation references starting with `@` (for example, `Field(label="@fields.title")`). Define translations in `Admin(translations={"en": {"fields.title": "Title"}, "ru": {"fields.title": "Заголовок"}})`. The server resolves references for the authenticated administrator's locale, falls back to the English dictionary, then to the untranslated key. It never interprets arbitrary literals as keys, and translation does not grant permissions. To change the locale for an administrator, use `locale_resolver` and refetch the schema.

Pyntral bundles basic core UI translations for `ru`, `es`, and `fr`, and uses the caller-provided English fallback for other locales or missing entries. `Admin(translations=...)` overrides bundled messages for matching keys. This initial catalog covers navigation and common list/CRUD commands; other UI strings still require translation-key migration.
