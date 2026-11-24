import { api } from "./api";

/** Authenticated, CSRF-protected Pydantic RPC. Never call Python functions directly from the browser. */
export async function invokeBridge<Input, Output>(name: string, input: Input): Promise<Output> {
  if (!/^[a-zA-Z][a-zA-Z0-9_-]*$/.test(name)) throw new Error("Invalid bridge name");
  const response = await api<{ result: Output }>(`/api/bridge/${name}`, {
    method: "POST", body: JSON.stringify(input),
  });
  return response.result;
}

/** Opt-in single-file RPC. File bytes are sent directly; metadata remains typed JSON. */
export async function invokeFileBridge<Input, Output>(name: string, input: Input, file: File, signal?: AbortSignal): Promise<Output> {
  if (!/^[a-zA-Z][a-zA-Z0-9_-]*$/.test(name)) throw new Error("Invalid bridge name");
  const metadata = encodeURIComponent(JSON.stringify(input));
  if (metadata.length > 8192) throw new Error("Bridge upload metadata too large");
  const response = await api<{ result: Output }>(`/api/bridge/${name}`, {
    method: "POST", body: file, signal, headers: {
      "Content-Type": file.type || "application/octet-stream",
      "X-Filename": encodeURIComponent(file.name), "X-Pyntral-Input": metadata,
    },
  });
  return response.result;
}
