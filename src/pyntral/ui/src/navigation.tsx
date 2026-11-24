import { useCallback, useEffect, useMemo, useState } from "react";
import { LockKeyhole, ChevronDown, ChevronRight } from "lucide-react";
import type { Schema, SidebarConfig, IconSpec, SidebarItemProps } from "./types";
import { Icon } from "./icon";
import { sidebarConfig } from "./sidebar";
import { useAdminFeedback } from "./feedback";
import { useCurrentAdmin } from "./currentAdmin";
import { useI18n } from "./i18n";
import { OverflowText } from "./overflow-text";
import { SearchInput } from "./ui";
import { categoryRoute, matchesNavigation, navigationMatches, type SearchNode } from "./navigation-state";
import { access as accessExtensions, sidebarItems } from "virtual:pyntral-extensions";

type Node = { type: "group" | "resource" | "page"; id: string; label: string; icon: IconSpec; order: number; route?: string;
  locked?: boolean; children: Node[] };
function makeTree(schema: Schema): Node[] {
  const root: Node[] = [];
  const groups = new Map<string, Node>();
  const definitions = new Map((schema.navigation?.groups || []).map((g) => [g.path, g]));
  function childrenFor(path?: string | null): Node[] {
    if (!path) return root;
    let parent = root;
    let current = "";
    for (const part of path.split("/")) {
      current = current ? `${current}/${part}` : part;
      let node = groups.get(current);
      if (!node) {
        const settings = definitions.get(current);
        node = { type: "group", id: current, label: part, icon: settings ? settings.icon : "folder", order: settings?.order || 0, route: settings?.component ? categoryRoute(current) : undefined, children: [] };
        parent.push(node);
        groups.set(current, node);
      }
      parent = node.children;
    }
    return parent;
  }
  // Explicit empty groups are allowed; users can fill them dynamically later.
  for (const group of schema.navigation?.groups || []) childrenFor(group.path);
  for (const resource of schema.resources.filter((r) => r.navigationState !== "hidden")) {
    childrenFor(resource.navigation).push({ type: "resource", id: resource.id, label: resource.label,
      icon: resource.icon, order: resource.navigationOrder || 0,
      locked: resource.navigationState === "locked", route: `resources/${resource.id}`, children: [] });
  }
  for (const page of schema.pages) {
    childrenFor(page.navigation).push({ type: "page", id: page.name, label: page.label,
      icon: page.icon, order: page.navigationOrder || 0, route: `pages/${page.name}`, children: [] });
  }
  const sort = (nodes: Node[]) => { nodes.sort((a, b) => a.order - b.order || a.label.localeCompare(b.label)); nodes.forEach((n) => sort(n.children)); };
  sort(root);
  return root;
}

function ItemContent({ config, schema, type, id, label, icon, depth, active, locked, open }: Omit<SidebarItemProps, "children"> & { config: SidebarConfig }) {
  const Custom = config.itemComponent ? sidebarItems[config.itemComponent] : undefined;
  const children = <>
    {config.showIcons && <Icon icon={icon} size={config.iconSize} fallback={type === "group" ? "folder" : "database"}/>}
    <OverflowText>{label}</OverflowText>
    {locked && <LockKeyhole size={13} aria-label="Locked"/>}
    {type === "group" && open !== undefined && (open ? <ChevronDown size={14}/> : <ChevronRight size={14}/>)}
  </>;
  return Custom ? <Custom schema={schema} type={type} id={id} label={label} icon={icon}
    depth={depth} active={active} locked={locked} open={open}>{children}</Custom> : children;
}
function Branch({ node, schema, route, go, depth, config, matches, expansion, setExpanded }: {
  node: Node; schema: Schema; route: string; go: (route: string) => void; depth: number; config: SidebarConfig; matches: Set<SearchNode> | null;
  expansion: Record<string, boolean>; setExpanded: (path: string, open: boolean) => void;
}) {
  const containsRoute = (target: Node): boolean => (!!target.route && (route === target.route || (target.type !== "group" && route.startsWith(target.route + "/")))) || target.children.some(containsRoute);
  const activeChild = containsRoute(node);
  const open = Object.hasOwn(expansion, node.id) ? expansion[node.id] : (activeChild || depth === 0);
  useEffect(() => { if (activeChild && node.type === "group" && matches === null) setExpanded(node.id, true); }, [activeChild, node.id, node.type, setExpanded, matches]);
  const setOpen = (value: boolean) => setExpanded(node.id, value);
  const expanded = matches !== null || open;
  const { confirm } = useAdminFeedback();
  const currentAdmin = useCurrentAdmin();
  const LockedContent = accessExtensions.denied;
  const resource = schema.resources.find((r) => r.id === node.id);
  const paddingLeft = 12 + Math.min(depth, config.maxIndentDepth) * config.indent;
  const content = <ItemContent config={config} schema={schema} type={node.type} id={node.id}
    label={node.label} icon={node.icon} depth={depth} active={activeChild} locked={!!node.locked}
    open={node.type === "group" && !node.route ? expanded : undefined}/>;
  if (matches && !matches.has(node)) return null;
  if (node.type !== "group") return <button type="button" className={`nav-link ${activeChild ? "active" : ""}`}
    aria-label={node.label} aria-current={activeChild ? "page" : undefined}
    style={{ paddingLeft }} onClick={() => {
      if (node.locked) void confirm({ title: "Access denied", message: `You cannot access ${node.label}.`,
        confirmLabel: "OK", cancelLabel: "Close",
        content: LockedContent && resource ? <LockedContent currentAdmin={currentAdmin} resource={resource}/> : undefined });
      else go(node.route!);
    }}>{content}</button>;
  return <div className="nav-branch">
    {node.route ? <div className="ra-nav-group-row">
      <button type="button" className={`nav-link nav-toggle ${route === node.route ? "active" : activeChild ? "ancestor-active" : ""}`}
        aria-label={node.label} aria-current={route === node.route ? "page" : undefined} style={{ paddingLeft }}
        onClick={() => { setOpen(true); go(node.route!); }}>{content}</button>
      {!!node.children.length && <button type="button" className="ra-nav-expand"
        aria-label={`${expanded ? "Collapse" : "Expand"} ${node.label}`} aria-expanded={expanded}
        disabled={matches !== null} onClick={() => setOpen(!open)}>
        {expanded ? <ChevronDown size={14}/> : <ChevronRight size={14}/>}
      </button>}
    </div> : <button className={`nav-link nav-toggle ${activeChild ? "ancestor-active" : ""}`} type="button"
      aria-label={node.label} aria-expanded={expanded} style={{ paddingLeft }} disabled={matches !== null} onClick={() => setOpen(!open)}>
      {content}
    </button>}
    {expanded && <div className="nav-children">{node.children.map(child => <Branch key={child.type + child.id}
      node={child} schema={schema} route={route} go={go} depth={depth + 1} config={config} matches={matches} expansion={expansion} setExpanded={setExpanded}/>)}</div>}
  </div>;
}
export function SidebarNavigation({ schema, route, navigate }: { schema: Schema; route: string; navigate: (route: string) => void }) {
  const tree = useMemo(() => makeTree(schema), [schema]);
  const config = sidebarConfig(schema);
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const [expansion, setExpansion] = useState<Record<string, boolean>>({});
  const setExpanded = useCallback((path: string, open: boolean) => setExpansion(old => old[path] === open ? old : {...old, [path]: open}), []);
  const search = config.showSearch ? query.trim() : "";
  const matches = useMemo(() => search ? navigationMatches(tree, search) : null, [tree, search]);
  const overview = schema.navigation?.showDashboard !== false && (!search || matchesNavigation(t("nav.overview", "Overview"), "dashboard", search));
  return <div className="ra-sidebar-navigation">
    {config.showSearch && <div className="ra-nav-search"><SearchInput value={query} onChange={setQuery}
      placeholder={config.searchPlaceholder ?? t("nav.search", "Search navigation…")} aria-label={t("nav.search", "Search navigation")}/></div>}
    <nav aria-label="Admin navigation">
    {overview && <button type="button" className={`nav-link ${!route ? "active" : ""}`}
      aria-current={!route ? "page" : undefined} aria-label={t("nav.overview", "Overview")} onClick={() => navigate("")}>
      <ItemContent config={config} schema={schema} type="dashboard" id="dashboard" label={t("nav.overview", "Overview")}
        icon={config.dashboardIcon} depth={0} active={!route} locked={false}/></button>}
    {tree.map(node => <Branch key={node.type + node.id} node={node} schema={schema} route={route} go={navigate} depth={0} config={config} matches={matches} expansion={expansion} setExpanded={setExpanded}/>)}
    {matches && !matches.size && !overview && <div className="ra-nav-empty" role="status">{t("nav.no_results", "No matching pages")}</div>}
    </nav>
  </div>;
}
