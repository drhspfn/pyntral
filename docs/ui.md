# React components, layout, and theming

[Documentation index](README.md) · [Extensions](extensions.md)

The Pyntral frontend is a React SPA. Its base CSS and reusable components live in `src/pyntral/ui/src/`; custom components are compiled with the same Vite toolchain and can import public aliases such as `@pyntral/ui`.

## Available UI primitives

```tsx
import {
  Button, Badge, Card, TextInput, Textarea, FormField,
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

List views provide hide/reorder columns, one pinned column, density, and up
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
