/** Derive accent-dependent tokens without overriding explicit application choices. */
export function contrastText(hex: string): "#000000" | "#ffffff" | undefined {
  const match = /^#([\da-f]{3}|[\da-f]{6})$/i.exec(hex.trim());
  if (!match) return undefined;
  const digits = match[1].length === 3 ? [...match[1]].map(char => char + char).join("") : match[1];
  const rgb = [0, 2, 4].map(offset => parseInt(digits.slice(offset, offset + 2), 16) / 255)
    .map(channel => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
  const luminance = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];
  return (luminance + 0.05) / 0.05 >= 1.05 / (luminance + 0.05) ? "#000000" : "#ffffff";
}

export function resolveAccentTokens(tokens: Record<string, string>, mode: "light" | "dark",
  normalizedPrimary?: string): Record<string, string> {
  if (!tokens.primary) return { ...tokens };
  const result = { ...tokens };
  const contrast = contrastText(normalizedPrimary ?? tokens.primary);
  if (result["on-primary"] === undefined && contrast) result["on-primary"] = contrast;
  // Mix toward the opposite pole of the foreground to preserve contrast on hover.
  const foreground = result["on-primary"]?.trim().toLowerCase();
  const target = foreground === "#000000" || foreground === "#000" || foreground === "black"
    ? "white" : foreground === "#ffffff" || foreground === "#fff" || foreground === "white"
      ? "black" : mode === "dark" ? "white" : "black";
  result["primary-hover"] ??= `color-mix(in srgb, var(--ra-primary) 88%, ${target})`;
  result["primary-soft"] ??= "color-mix(in srgb, var(--ra-primary) 13%, var(--ra-surface))";
  result["sidebar-active"] ??= "color-mix(in srgb, var(--ra-primary) 15%, var(--ra-sidebar-bg))";
  return result;
}
