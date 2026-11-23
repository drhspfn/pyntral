import { useId, useState, type ReactNode } from "react";
import { ChevronRight } from "lucide-react";

export interface CollapsibleProps {
  /** Non-interactive label or custom header content. Place interactive controls in actions. */
  header: ReactNode | ((open: boolean) => ReactNode);
  actions?: ReactNode | ((open: boolean) => ReactNode);
  children: ReactNode;
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  disabled?: boolean;
  className?: string;
}
export function Collapsible({ header, actions, children, open: controlled, defaultOpen = false,
  onOpenChange, disabled = false, className = "" }: CollapsibleProps) {
  const [internal, setInternal] = useState(defaultOpen);
  const open = controlled ?? internal;
  const id = useId();
  const toggle = () => {
    if (controlled === undefined) setInternal(!open);
    onOpenChange?.(!open);
  };
  return <section className={`ra-collapsible ${className}`} data-open={open}>
    <div className="ra-collapsible-header">
      <button type="button" className="ra-collapsible-trigger" id={`${id}-trigger`}
        aria-expanded={open} aria-controls={`${id}-content`} disabled={disabled} onClick={toggle}>
        <ChevronRight size={17} aria-hidden="true"/>
        <span className="ra-collapsible-label">{typeof header === "function" ? header(open) : header}</span>
      </button>
      {actions != null && <div className="ra-collapsible-actions">{typeof actions === "function" ? actions(open) : actions}</div>}
    </div>
    <div id={`${id}-content`} role="region" aria-labelledby={`${id}-trigger`} hidden={!open}
      className="ra-collapsible-content">{children}</div>
  </section>;
}
