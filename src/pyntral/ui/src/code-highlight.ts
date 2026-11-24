import hljs from "highlight.js/lib/core";
import json from "highlight.js/lib/languages/json";
import csharp from "highlight.js/lib/languages/csharp";
import javascript from "highlight.js/lib/languages/javascript";
import typescript from "highlight.js/lib/languages/typescript";
import python from "highlight.js/lib/languages/python";
import sql from "highlight.js/lib/languages/sql";
import bash from "highlight.js/lib/languages/bash";
import xml from "highlight.js/lib/languages/xml";
import css from "highlight.js/lib/languages/css";
import yaml from "highlight.js/lib/languages/yaml";
import { normalizeLanguage } from "./code-state";

const grammars = { json, csharp, javascript, typescript, python, sql, bash, xml, css, yaml };
for (const [name, grammar] of Object.entries(grammars)) hljs.registerLanguage(name, grammar);
const names: Record<string,string> = { json:"JSON", csharp:"C#", javascript:"JavaScript", typescript:"TypeScript", python:"Python", sql:"SQL", bash:"Bash", xml:"XML / HTML", css:"CSS", yaml:"YAML", plaintext:"Text" };
export function codeLanguage(source: string, requested: string, validJson: boolean): string {
  const name = normalizeLanguage(requested);
  if (name !== "auto") return name;
  if (validJson) return "json";
  if (source.length > 12000 || !source.trim()) return "plaintext";
  try {
    const result = hljs.highlightAuto(source, Object.keys(grammars));
    return result.language && result.relevance >= 3 ? result.language : "plaintext";
  } catch { return "plaintext"; }
}
export function languageLabel(language: string): string { return Object.hasOwn(names, language) ? names[language] : language; }
export function highlightedCode(source: string, language: string): string | null {
  if (source.length > 40000 || language === "plaintext" || !hljs.getLanguage(language)) return null;
  try { return hljs.highlight(source, { language, ignoreIllegals: true }).value; }
  catch { return null; }
}
