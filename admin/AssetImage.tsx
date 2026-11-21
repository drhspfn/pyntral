import { useQuery } from "@tanstack/react-query";
import { resolveAsset } from "@pyntral/generated";
import type { CustomFieldProps } from "@pyntral/types";

/** Demonstrates Entity.Agent.cover_id -> Entity.FileAsset -> Python bridge -> image URL. */
export default function AssetImage({ record }: CustomFieldProps) {
  const id = record.cover_id;
  const asset = useQuery({
    queryKey: ["asset-url", id], enabled: id !== null && id !== undefined,
    queryFn: () => resolveAsset({ asset_id: Number(id) }),
  });
  if (id == null) return <span className="muted">No asset</span>;
  if (asset.isPending) return <span className="muted">Loading…</span>;
  if (!asset.data || asset.error) return <span className="muted">Not available</span>;
  return <img src={asset.data.url} alt={asset.data.filename} width={34} height={34}
    style={{ borderRadius: 8, objectFit: "cover", verticalAlign: "middle" }} />;
}
