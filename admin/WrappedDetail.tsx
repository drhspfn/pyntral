import type { CustomCrudProps } from "@pyntral/types";
import { Card } from "@pyntral/ui";

/** A full CRUD override that wraps the original view instead of replacing it. */
export default function WrappedDetail({ defaultView }: CustomCrudProps) {
  return <>
    <Card title="Composite identity" description="Create a product note with both key fields; edit only the note afterward.">
      <p>The built-in record details and actions are rendered below.</p>
    </Card>
    {defaultView}
  </>;
}
