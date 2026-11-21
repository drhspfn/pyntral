import { createContext, useContext, type ReactNode } from "react";
import type { Principal } from "./types";

const CurrentAdminContext = createContext<Principal | null>(null);
export function CurrentAdminProvider({ currentAdmin, children }: {
  currentAdmin: Principal; children: ReactNode;
}) { return <CurrentAdminContext.Provider value={currentAdmin}>{children}</CurrentAdminContext.Provider>; }
/** Identity from LocalAuth, ModelAuth, or a verified external auth callback. */
export function useCurrentAdmin(): Principal {
  const currentAdmin = useContext(CurrentAdminContext);
  if (!currentAdmin) throw new Error("useCurrentAdmin requires an authenticated admin session");
  return currentAdmin;
}
