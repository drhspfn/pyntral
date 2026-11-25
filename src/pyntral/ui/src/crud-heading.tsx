import type { ReactNode } from "react";

/** Keep action controls available even when the stock title is hidden. */
export function CrudHeading({ showHeading = true, heading, actions, before }: {
  showHeading?: boolean; heading: ReactNode; actions?: ReactNode; before?: ReactNode;
}) {
  return <>
    {(showHeading || actions != null) && <div className={`page-heading${showHeading ? "" : " ra-crud-actions-only"}`}>
      {showHeading && <div>{heading}</div>}
      {actions != null && <div className="heading-actions">{actions}</div>}
    </div>}
    {before}
  </>;
}
