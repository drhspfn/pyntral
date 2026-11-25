/** Pure navigation filtering; never creates nodes outside the authorized tree. */
export interface SearchNode {
  label: string;
  id: string;
  children: SearchNode[];
}
export function matchesNavigation(label: string, id: string, query: string): boolean {
  const normalize = (value: string) => value.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase();
  const haystack = normalize(label + " " + id);
  return normalize(query).trim().split(/\s+/).every(word => haystack.includes(word));
}
export function navigationMatches<T extends SearchNode>(nodes: readonly T[], query: string): Set<SearchNode> {
  const matches = new Set<SearchNode>();
  function visit(node: SearchNode, ancestorMatch: boolean): boolean {
    const ownMatch = ancestorMatch || matchesNavigation(node.label, node.id, query);
    let childMatch = false;
    for (const child of node.children) if (visit(child, ownMatch)) childMatch = true;
    if (ownMatch || childMatch) matches.add(node);
    return ownMatch || childMatch;
  }
  for (const node of nodes) visit(node, false);
  return matches;
}
export function categoryRoute(path: string): string {
  return "groups/" + path.split("/").map(encodeURIComponent).join("/");
}
