import { useMutation, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { useAdminFeedback } from "./feedback";
import type { RecordData, ResourceDef } from "./types";

export interface Listing { items: RecordData[]; total: number; offset: number; limit: number; actionsByRecord?: Record<string, string[]> }

/** Update all already loaded list/relationship pages synchronously; rollback on error. */
export function removeRecordFromCache(client: QueryClient, resource: ResourceDef, id: string) {
  const snapshots = client.getQueriesData<Listing>({ predicate: (query) => {
    const key = query.queryKey;
    return (key[0] === "list" && key[1] === resource.id) || (key[0] === "related" && key[4] === resource.id);
  } });
  for (const [key, data] of snapshots) {
    if (!data?.items) continue;
    const items = data.items.filter((row) => String(row[resource.primaryKey]) !== id);
    if (items.length === data.items.length) continue;
    const actionsByRecord = data.actionsByRecord ? { ...data.actionsByRecord } : undefined;
    if (actionsByRecord) delete actionsByRecord[id];
    client.setQueryData(key, { ...data, items, total: Math.max(0, data.total - 1), actionsByRecord });
  }
  return () => { for (const [key, data] of snapshots) client.setQueryData(key, data); };
}

/** Call in React components, not outside the React render tree. */
export function useDeleteRecord(resource: ResourceDef, onDeleted?: () => void) {
  const client = useQueryClient();
  const feedback = useAdminFeedback();
  const mutation = useMutation({
    mutationFn: ({ id, version }: { id: string; version?: unknown }) => api(
      `/api/resources/${resource.id}/${encodeURIComponent(id)}`,
      { method: "DELETE", headers: resource.versionField ? { "If-Match": String(version) } : undefined }),
    onMutate: async ({ id }) => {
      await Promise.all([
        client.cancelQueries({ queryKey: ["list"] }),
        client.cancelQueries({ queryKey: ["related"] }),
      ]);
      return { rollback: removeRecordFromCache(client, resource, id) };
    },
    onError: (error, _id, context) => {
      context?.rollback();
      feedback.toast(error instanceof Error ? error.message : "Unable to delete record", { kind: "error", duration: 6500 });
    },
    onSuccess: () => {
      feedback.toast("Record deleted", { kind: "success" });
      onDeleted?.();
    },
    onSettled: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ["list"] }),
        client.invalidateQueries({ queryKey: ["related"] }),
        client.invalidateQueries({ queryKey: ["record", resource.id] }),
        client.invalidateQueries({ queryKey: ["stats"] }),
        client.invalidateQueries({ queryKey: ["options"] }),
      ]);
    },
  });
  const requestDelete = async (id: unknown, version?: unknown) => {
    if (mutation.isPending) return false;
    const accepted = await feedback.confirm({ title: "Delete record?", message: "This action cannot be undone.",
      confirmLabel: "Delete", destructive: true });
    if (!accepted) return false;
    try { await mutation.mutateAsync({ id: String(id), version }); return true; }
    catch { return false; } // onError already reports the error via a toast
  };
  return { requestDelete, isPending: mutation.isPending };
}

export async function invalidateResource(client: QueryClient, resourceId: string) {
  await Promise.all([
    client.invalidateQueries({ queryKey: ["list"] }),
    client.invalidateQueries({ queryKey: ["related"] }),
    client.invalidateQueries({ queryKey: ["record", resourceId] }),
    client.invalidateQueries({ queryKey: ["stats"] }),
    client.invalidateQueries({ queryKey: ["options"] }),
  ]);
}
