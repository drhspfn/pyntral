import type { ReactNode, CSSProperties, Key } from "react";

/** The same responsive, themed semantic table shell used by built-in CRUD. */
export function Table({ children, className = "", compact = false, style, label }: {
  children: ReactNode; className?: string; compact?: boolean; style?: CSSProperties; label?: string;
}) {
  return <div className={`ra-table ${compact ? "ra-table-compact" : ""} ${className}`} style={style}>
    <div className="table-scroll"><table className="data-table" aria-label={label}>{children}</table></div>
  </div>;
}
export interface DataColumn<Row> {
  id: string; header: ReactNode; cell: (row: Row) => ReactNode; className?: string;
  sortable?: boolean;
}
export interface DataTableProps<Row> {
  rows: readonly Row[]; columns: readonly DataColumn<Row>[]; getRowKey: (row: Row) => Key;
  label?: string; compact?: boolean; loading?: boolean; empty?: ReactNode; className?: string;
  sort?: { column: string; direction: "asc" | "desc" };
  onSortChange?: (sort: { column: string; direction: "asc" | "desc" }) => void;
}
/** Presentational table: caller owns queries, pagination and sorting. */
export function DataTable<Row>({ rows, columns, getRowKey, label, compact, loading, empty = "No records", className,
  sort, onSortChange }: DataTableProps<Row>) {
  return <Table label={label} compact={compact} className={className}>
    <thead><tr>{columns.map(column => <th key={column.id} scope="col" className={column.className}
      aria-sort={sort?.column === column.id ? (sort.direction === "asc" ? "ascending" : "descending") : undefined}>
      {column.sortable && onSortChange ? <button type="button" className="ra-table-sort"
        onClick={() => onSortChange({ column: column.id, direction: sort?.column === column.id && sort.direction === "asc" ? "desc" : "asc" })}>
        {column.header}{sort?.column === column.id && (sort.direction === "asc" ? " ↑" : " ↓")}
      </button> : column.header}</th>)}</tr></thead>
    <tbody>{loading || !rows.length ? <tr><td colSpan={Math.max(1, columns.length)} className="ra-table-empty">
      {loading ? "Loading…" : empty}</td></tr> :
      rows.map(row => <tr key={getRowKey(row)}>{columns.map(column => <td key={column.id} className={column.className}>{column.cell(row)}</td>)}</tr>)}</tbody>
  </Table>;
}
