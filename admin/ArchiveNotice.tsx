import type { ActionDialogProps } from "@pyntral/types";

/** Pluggable body for a contextual record action confirmation dialog. */
export default function ArchiveNotice({ record }: ActionDialogProps) {
  return <div style={{ marginTop: 16, fontSize: 13, lineHeight: 1.6 }}>
    <p>Archive <strong>{String(record.name ?? "this customer")}</strong>?</p>
    <p style={{ color: "var(--ra-muted)" }}>The record will remain in the database, but its active flag will be disabled.</p>
  </div>;
}
