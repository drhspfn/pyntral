import { useEffect, useMemo, useState } from "react";
import { LockKeyhole, Bot, ChevronDown, ChevronRight, Cpu, Database, Folder, LayoutDashboard, Package, Settings, Users } from "lucide-react";
import type { ComponentType } from "react";
import type { Schema } from "./types";
import { useAdminFeedback } from "./feedback";
import { useCurrentAdmin } from "./currentAdmin";
import { access as accessExtensions } from "virtual:pyntral-extensions";

type Node = { type: "group" | "resource" | "page"; id: string; label: string; icon: string; order: number; route?: string;
  locked?: boolean; children: Node[] };
const iconMap: Record<string, ComponentType<{ size?: number }>> = {
  bot: Bot, cpu: Cpu, folder: Folder, database: Database, boxes: Package,
  users: Users, settings: Settings, "layout-dashboard": LayoutDashboard,
};
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
        node = { type: "group", id: current, label: part, icon: settings?.icon || "folder", order: settings?.order || 0, children: [] };
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

function Branch({ node, schema, route, go, depth }: { node: Node; schema: Schema; route: string; go: (route: string) => void; depth: number }) {
  const containsRoute = (target: Node): boolean => target.route ? route === target.route || route.startsWith(target.route + "/") : target.children.some(containsRoute);
  const activeChild = containsRoute(node);
  const [open, setOpen] = useState(activeChild || depth === 0);
  useEffect(() => { if (activeChild) setOpen(true); }, [activeChild]);
  const Icon = iconMap[node.icon] || Folder;
  const { confirm } = useAdminFeedback();
  const currentAdmin = useCurrentAdmin();
  const LockedContent = accessExtensions.denied;
  const resource = schema.resources.find((r) => r.id === node.id);
  if (node.type !== "group") return <button type="button" className={`nav-link ${activeChild ? "active" : ""}`}
    style={{ paddingLeft: `${12 + depth * 12}px` }} onClick={() => {
      if (node.locked) void confirm({ title: "Access denied", message: `You cannot access ${node.label}.`,
        confirmLabel: "OK", cancelLabel: "Close",
        content: LockedContent && resource ? <LockedContent currentAdmin={currentAdmin} resource={resource}/> : undefined });
      else go(node.route!);
    }}>
    <Icon size={16} /><span>{node.label}</span>{node.locked && <LockKeyhole size={13} aria-label="Locked"/>}</button>;
  return <div className="nav-branch">
    <button className={`nav-link nav-toggle ${activeChild ? "ancestor-active" : ""}`} type="button"
      aria-expanded={open} style={{ paddingLeft: `${12 + depth * 12}px` }} onClick={() => setOpen(!open)}>
      <Icon size={16}/><span>{node.label}</span>{open ? <ChevronDown size={14}/> : <ChevronRight size={14}/>}
    </button>
    {open && <div className="nav-children">{node.children.map((child) => <Branch key={child.type + child.id}
      node={child} schema={schema} route={route} go={go} depth={depth + 1} />)}</div>}
  </div>;
}
export function SidebarNavigation({ schema, route, navigate }: { schema: Schema; route: string; navigate: (route: string) => void }) {
  const tree = useMemo(() => makeTree(schema), [schema]);
  return <nav aria-label="Admin navigation">
    {schema.navigation?.showDashboard !== false && <button className={`nav-link ${!route ? "active" : ""}`} onClick={() => navigate("")}>
      <LayoutDashboard size={16}/><span>Overview</span></button>}
    {tree.map((node) => <Branch key={node.type + node.id} node={node} schema={schema} route={route} go={navigate} depth={0}/>)}
  </nav>;
}
