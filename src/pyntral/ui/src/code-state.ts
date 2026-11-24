/** JSON formatting is lossless for large integers, duplicate keys and numeric lexemes:
 * validate with JSON.parse, then only adjust insignificant whitespace outside strings.
 */
export function formatJson(source: string, indent = 2): string | null {
  try { JSON.parse(source); } catch { return null; }
  const width = Math.max(0, Math.min(8, Number.isFinite(indent) ? Math.floor(indent) : 2));
  let depth = 0, quoted = false, escaped = false, out = "";
  const newline = () => "\n" + " ".repeat(depth * width);
  for (let i = 0; i < source.length; i++) {
    const c = source[i];
    if (quoted) {
      out += c;
      if (escaped) escaped = false;
      else if (c === "\\") escaped = true;
      else if (c === '"') quoted = false;
      continue;
    }
    if (/\s/.test(c)) continue;
    if (c === '"') { quoted = true; out += c; continue; }
    if (c === "{" || c === "[") {
      const close = c === "{" ? "}" : "]";
      out += c;
      const next = source.slice(i + 1).match(/^\s*/)?.[0].length ?? 0;
      if (source[i + 1 + next] === close) { out += close; i += next + 1; continue; }
      depth++; out += newline();
    } else if (c === "}" || c === "]") {
      depth--; out += newline() + c;
    } else if (c === ",") out += "," + newline();
    else if (c === ":") out += ": ";
    else out += c;
  }
  return out;
}
export function jsonSource(value: unknown): string {
  if (typeof value === "string") return value;
  try { return JSON.stringify(value) ?? String(value); }
  catch { return "[Value cannot be serialized as JSON]"; }
}
export const languageAliases: Record<string, string> = {
  "c#": "csharp", cs: "csharp", js: "javascript", ts: "typescript", py: "python",
  sh: "bash", shell: "bash", html: "xml", yml: "yaml", text: "plaintext", txt: "plaintext"
};
export function normalizeLanguage(language: string): string {
  const normalized = language.trim().toLowerCase();
  return languageAliases[normalized] ?? normalized;
}
