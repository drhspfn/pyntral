import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { LoaderCircle } from "lucide-react";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  loading?: boolean;
  startIcon?: ReactNode;
  endIcon?: ReactNode;
}
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button({
  variant = "secondary", loading = false, startIcon, endIcon, disabled, children, className = "", ...props
}, ref) {
  return <button {...props} ref={ref} className={`ra-button ra-button-${variant} ${className}`}
    disabled={disabled || loading} aria-busy={loading}>
    {loading ? <LoaderCircle className="spin" size={16}/> : startIcon}
    {children && <span>{children}</span>}{!loading && endIcon}
  </button>;
});
