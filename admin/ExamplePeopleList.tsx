/** Optional full-screen override. Register under `crud` when you need it. */
import { useEffect, useState } from "react";
import type { CustomCrudProps, RecordData } from "@pyntral/types";

export default function ExamplePeopleList({ resource, loadList, navigate }: CustomCrudProps) {
  const [rows, setRows] = useState<RecordData[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    loadList({ limit: 20 }).then((page) => {
      if (!cancelled) setRows(page.items);
    }).catch((reason: unknown) => {
      if (!cancelled) setError(reason instanceof Error ? reason.message : "Unable to load data");
    });
    return () => { cancelled = true; };
  }, [loadList]);
  return <section>
    <h1>{resource.label}</h1>
    {error && <p role="alert">{error}</p>}
    <ul>{rows.map((row) => <li key={String(row[resource.primaryKey])}>
      <button type="button" onClick={() => navigate(`resources/${resource.id}/${encodeURIComponent(String(row[resource.primaryKey]))}`)}>
        {String(row[resource.titleField] ?? row[resource.primaryKey])}
      </button>
    </li>)}</ul>
  </section>;
}
