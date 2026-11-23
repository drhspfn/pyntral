/** Lint registered app extensions with the UI's own ESLint rules.
 *
 * Project files live outside the cached Vite workspace. ESLint 10 intentionally
 * ignores paths outside its configuration root; lintText maps each extension to
 * an in-root virtual TS/TSX filename without copying or changing its imports.
 */
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { ESLint } from "eslint";

const project = path.resolve(process.env.PYNTRAL_PROJECT || path.join(process.cwd(), "../.."));
const manifestPath = path.join(project, "pyntral.components.json");
let manifest;
try {
  manifest = JSON.parse(await fs.readFile(manifestPath, "utf8"));
} catch (error) {
  if (error.code === "ENOENT") process.exit(0);
  throw error;
}

const eslint = new ESLint({ overrideConfigFile: path.resolve("eslint.config.mjs") });
const categories = ["fields", "pages", "actions", "dialogs", "themes", "profile", "access", "auth", "sidebarHeaders", "sidebarFooters", "sidebarItems"];
const files = new Set();
for (const category of categories) {
  for (const relative of Object.values(manifest[category] || {})) {
    if (typeof relative !== "string") throw new Error(`Invalid ${category} component path`);
    const absolute = path.resolve(project, relative);
    if (!absolute.startsWith(project + path.sep)) throw new Error(`Extension outside project: ${relative}`);
    files.add(absolute);
  }
}

let errorCount = 0;
for (const absolute of [...files].sort()) {
  const extension = path.extname(absolute);
  if (!new Set([".ts", ".tsx", ".js", ".jsx"]).has(extension)) continue;
  const source = await fs.readFile(absolute, "utf8");
  // Use a filename inside src/ so it matches the active ESLint flat config.
  const virtualFile = path.resolve("src", `__pyntral_extension__${extension}`);
  const results = await eslint.lintText(source, { filePath: virtualFile });
  const formatter = await eslint.loadFormatter("stylish");
  const output = formatter.format(results);
  if (output.trim()) {
    process.stderr.write(`Extension: ${path.relative(project, absolute)}\n${output}`);
  }
  errorCount += results.reduce((total, result) => total + result.errorCount, 0);
}
if (errorCount) process.exitCode = 1;
