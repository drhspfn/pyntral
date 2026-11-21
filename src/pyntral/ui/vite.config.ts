import fs from "node:fs";
import path from "node:path";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

const project = path.resolve(process.env.PYNTRAL_PROJECT || process.cwd());
const base = process.env.PYNTRAL_BASE || "/admin/";
const backend = process.env.PYNTRAL_BACKEND || "http://127.0.0.1:8000";
const configFile = path.join(project, "pyntral.components.json");
const managedUi = process.cwd();
const managedDependencies = Object.keys(
  JSON.parse(fs.readFileSync(path.join(managedUi, "package.json"), "utf8")).dependencies as Record<string, string>,
);

// Extensions are imported by absolute path from the host project. Ordinary
// package resolution starts at their location, so it cannot discover modules
// installed under .pyntral/ui/node_modules. Resolve bundled UI dependencies
// through absolute aliases *before* Rolldown attempts Node resolution.
// This also guarantees a single React instance across the UI and extensions.
const managedAliases = managedDependencies.map((dependency) => ({
  find: dependency,
  replacement: path.join(managedUi, "node_modules", dependency).replace(/\\/g, "/"),
}));

function extensions(): Plugin {
  const virtualId = "virtual:pyntral-extensions";
  const resolvedId = "\0" + virtualId;
  const loadConfig = (): Record<string, Record<string, string>> =>
    fs.existsSync(configFile) ? JSON.parse(fs.readFileSync(configFile, "utf8")) : {};
  return {
    name: "pyntral-components",
    resolveId(id) { if (id === virtualId) return resolvedId; },
    load(id) {
      if (id !== resolvedId) return;
      const config = loadConfig();
      const lines: string[] = [];
      for (const category of ["fields", "pages", "actions", "dialogs", "themes", "profile", "access", "auth"]) {
        const entries: string[] = [];
        for (const [key, relative] of Object.entries(config[category] || {})) {
          const absolute = path.resolve(project, relative);
          if (!absolute.startsWith(project + path.sep)) {
            throw new Error(`Extension outside project: ${relative}`);
          }
          if (!fs.existsSync(absolute)) throw new Error(`Missing extension: ${relative}`);
          const binding = `ext_${category}_${entries.length}`;
          lines.push(`import ${binding} from ${JSON.stringify(absolute.replace(/\\/g, "/"))};`);
          entries.push(`${JSON.stringify(key)}: ${binding}`);
        }
        lines.push(`export const ${category} = {${entries.join(",")}};`);
      }
      return lines.join("\n");
    },
    handleHotUpdate({ file, server }) {
      if (file === configFile) {
        const module = server.moduleGraph.getModuleById(resolvedId);
        if (module) server.moduleGraph.invalidateModule(module);
        server.ws.send({ type: "full-reload" });
      }
    },
  };
}

/** Resolve packages imported by app-owned extensions.
 *
 * Extension files are intentionally kept in the host project (e.g. admin/).
 * Node's normal lookup from those files cannot see the dependencies installed
 * in the managed .pyntral/ui workspace. First respect packages installed by
 * the host app, then fall back to Pyntral's dependency tree. This covers
 * arbitrary packages, not just lucide-react, and avoids externalizing imports
 * that must be present in the production SPA bundle.
 */
function extensionDependencies(): Plugin {
  const uiEntry = path.resolve("src/main.tsx");
  const uiRoot = path.resolve("src");
  return {
    name: "pyntral-extension-dependencies",
    async resolveId(source, importer) {
      if (
        !importer ||
        !path.isAbsolute(importer) ||
        !path.isAbsolute(project) ||
        !importer.startsWith(project + path.sep) ||
        importer.startsWith(uiRoot + path.sep) ||
        source.startsWith(".") ||
        source.startsWith("/") ||
        source.startsWith("\0") ||
        source.startsWith("node:") ||
        source.startsWith("@pyntral/")
      ) return null;

      const fromProject = await this.resolve(source, importer, { skipSelf: true });
      if (fromProject) return fromProject;
      return this.resolve(source, uiEntry, { skipSelf: true });
    },
  };
}

export default defineConfig({
  base,
  plugins: [react(), extensions(), extensionDependencies()],
  resolve: { alias: [
    ...Object.entries({
      "@pyntral/types": path.resolve("src/types.ts"),
    "@pyntral/api": path.resolve("src/api.ts"),
    "@pyntral/bridge": path.resolve("src/bridge.ts"),
    "@pyntral/feedback": path.resolve("src/feedback.tsx"),
    "@pyntral/ui": path.resolve("src/ui.tsx"),
    "@pyntral/auth": path.resolve("src/currentAdmin.tsx"),
    "@pyntral/mutations": path.resolve("src/mutations.ts"),
    "@pyntral/generated": path.join(project, ".pyntral", "generated", "bridges.ts"),
    }).map(([find, replacement]) => ({ find, replacement })),
    ...managedAliases,
  ], dedupe: ["react", "react-dom", "@tanstack/react-query"] },
  server: {
    fs: { allow: [project, process.cwd()] },
    proxy: {
      [`${base}api`]: { target: backend, changeOrigin: false },
      [`${base}auth`]: { target: backend, changeOrigin: false },
    },
  },
  build: { target: "es2022", sourcemap: false, emptyOutDir: true },
});
