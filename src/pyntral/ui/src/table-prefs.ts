/** Defensive, user-scoped table display preferences (never an authorization layer). */
export interface TablePreferences {
  order: string[];
  hidden: string[];
  density: "comfortable" | "compact";
  pinned: string | null;
  presets: Record<string, Record<string, unknown>>;
}

export function defaultTablePreferences(): TablePreferences {
  return { order: [], hidden: [], density: "comfortable", pinned: null, presets: {} };
}

export function parseTablePreferences(input: unknown, knownFields: string[]): TablePreferences {
  const defaults = defaultTablePreferences();
  if (!input || typeof input !== "object" || Array.isArray(input)) return defaults;
  const raw = input as Record<string, unknown>;
  const validList = (value: unknown) => Array.isArray(value) ?
    [...new Set(value.filter((name): name is string => typeof name === "string" && knownFields.includes(name)))]:[];
  const presets: Record<string, Record<string, unknown>> = {};
  if (raw.presets && typeof raw.presets === "object" && !Array.isArray(raw.presets)) {
    for (const [name, value] of Object.entries(raw.presets).slice(0, 10)) {
      if (name.length > 30 || !value || typeof value !== "object" || Array.isArray(value)) continue;
      if (JSON.stringify(value).length < 10000) presets[name] = value as Record<string, unknown>;
    }
  }
  return {
    order: validList(raw.order), hidden: validList(raw.hidden),
    density: raw.density === "compact" ? "compact" : "comfortable",
    pinned: typeof raw.pinned === "string" && knownFields.includes(raw.pinned) ? raw.pinned : null,
    presets,
  };
}

export function orderedColumns(names: string[], prefs: TablePreferences): string[] {
  return names.filter((name) => !prefs.hidden.includes(name))
    .sort((a, b) => {
      const ai = prefs.order.indexOf(a), bi = prefs.order.indexOf(b);
      return (ai < 0 ? names.indexOf(a) + names.length : ai) -
        (bi < 0 ? names.indexOf(b) + names.length : bi);
    });
}
