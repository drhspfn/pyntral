import type { Schema, ThemeMode } from "./types";

export function resolveMode(selection: string): ThemeMode {
  if (selection === "light" || selection === "dark") return selection;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** Set custom CSS variables globally. Components should use var(--ra-*), not hard-coded values. */
export function applyTheme(schema: Schema, mode: ThemeMode): () => void {
  const root = document.documentElement;
  root.dataset.theme = mode;
  root.classList.toggle("no-motion", schema.theme?.animations === false);
  const tokens = schema.theme?.tokens?.[mode] || {};
  const installed: string[] = [];
  for (const [key, value] of Object.entries(tokens)) {
    if (!/^[a-z][a-z0-9-]*$/.test(key) || typeof value !== "string") continue;
    const cssName = `--ra-${key}`;
    root.style.setProperty(cssName, value);
    installed.push(cssName);
  }
  return () => { installed.forEach((key) => root.style.removeProperty(key)); };
}
