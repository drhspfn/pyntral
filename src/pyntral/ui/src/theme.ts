import type { Schema, ThemeMode } from "./types";
import { resolveAccentTokens } from "./theme-state";

export function resolveMode(selection: string): ThemeMode {
  if (selection === "light" || selection === "dark") return selection;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** Set custom CSS variables globally. Components should use var(--ra-*), not hard-coded values. */
export function applyTheme(schema: Pick<Schema, "theme">, mode: ThemeMode): () => void {
  const root = document.documentElement;
  root.dataset.theme = mode;
  root.classList.toggle("no-motion", schema.theme?.animations === false);
  const explicit = schema.theme?.tokens?.[mode] || {};
  // Canvas normalizes ordinary opaque CSS colors (rgb, hsl, named colors) to hex.
  // Complex/transparent colors can always supply an explicit on-primary token.
  let normalized: string | undefined;
  if (explicit.primary && CSS.supports("color", explicit.primary) && !/var\(|currentcolor|inherit|initial|unset|revert/i.test(explicit.primary)) {
    const context = document.createElement("canvas").getContext("2d");
    if (context) { context.fillStyle = explicit.primary; normalized = context.fillStyle; }
  }
  const tokens = resolveAccentTokens(explicit, mode, normalized);
  const installed: string[] = [];
  for (const [key, value] of Object.entries(tokens)) {
    if (!/^[a-z][a-z0-9-]*$/.test(key) || typeof value !== "string") continue;
    const cssName = `--ra-${key}`;
    root.style.setProperty(cssName, value);
    installed.push(cssName);
  }
  return () => { installed.forEach((key) => root.style.removeProperty(key)); };
}
