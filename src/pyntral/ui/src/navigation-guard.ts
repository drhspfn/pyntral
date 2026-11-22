/** Registry used by built-in forms to guard SPA navigation. */
export type NavigationBlocker = () => Promise<boolean>;
let blocker: NavigationBlocker | null = null;
export function registerNavigationBlocker(callback: NavigationBlocker): () => void {
  blocker = callback;
  return () => { if (blocker === callback) blocker = null; };
}
export function hasNavigationBlocker(): boolean { return blocker !== null; }
export async function mayLeavePage(): Promise<boolean> {
  return blocker ? blocker() : true;
}
