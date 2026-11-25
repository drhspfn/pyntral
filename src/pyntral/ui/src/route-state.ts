/** Mount-relative internal SPA navigation, preserving the query string. */
export function adminDestination(base: string, route: string): string {
  if (route.startsWith("//") || route.includes("\\") || [...route].some(c => c.charCodeAt(0) < 32) ||
      /^[a-z][a-z0-9+.-]*:/i.test(route)) throw new Error("Expected an admin-relative route");
  const prefix = base.replace(/\/$/, "");
  const url = new URL(prefix + "/" + route.replace(/^\//, ""), "https://pyntral.invalid");
  if (url.origin !== "https://pyntral.invalid" || !url.pathname.startsWith(prefix + "/"))
    throw new Error("Route escapes the admin mount");
  return url.pathname + url.search;
}
export function splitAdminLocation(base: string, location: string) {
  const url = new URL(location, "https://pyntral.invalid");
  const prefix = base.replace(/\/$/, "");
  return {route: url.pathname.startsWith(prefix + "/") ? url.pathname.slice(prefix.length + 1) : "", search: url.search};
}
