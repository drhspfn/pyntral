import { api } from "./api";

/** Authenticated, CSRF-protected Pydantic RPC. Never call Python functions directly from the browser. */
export async function invokeBridge<Input, Output>(name: string, input: Input): Promise<Output> {
  if (!/^[a-zA-Z][a-zA-Z0-9_-]*$/.test(name)) throw new Error("Invalid bridge name");
  const response = await api<{ result: Output }>(`/api/bridge/${name}`, {
    method: "POST", body: JSON.stringify(input),
  });
  return response.result;
}
