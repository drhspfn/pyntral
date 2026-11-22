import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";

export type ToastKind = "success" | "error" | "info";
export interface ToastOptions { kind?: ToastKind; duration?: number }
export interface DialogOptions {
  title: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  content?: ReactNode;
}
export interface FeedbackService {
  toast: (message: string, options?: ToastOptions) => void;
  confirm: (options: DialogOptions) => Promise<boolean>;
  dismiss: (id: number) => void;
}
const FeedbackContext = createContext<FeedbackService | null>(null);
export function useAdminFeedback(): FeedbackService {
  const service = useContext(FeedbackContext);
  if (!service) throw new Error("useAdminFeedback must be used inside AdminFeedbackProvider");
  return service;
}
type ToastItem = { id: number; message: string; kind: ToastKind; duration: number };
type DialogItem = { options: DialogOptions; resolve: (accepted: boolean) => void };
export function AdminFeedbackProvider({ children }: { children: ReactNode }) {
  const nextId = useRef(0);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [dialog, setDialog] = useState<DialogItem | null>(null);
  const queue = useRef<DialogItem[]>([]);
  const modal = useRef<HTMLDialogElement>(null);
  const initialFocus = useRef<HTMLButtonElement>(null);
  const [active, setActive] = useState(false);
  const dismiss = useCallback((id: number) => setToasts((current) => current.filter((toast) => toast.id !== id)), []);
  const toast = useCallback((message: string, options: ToastOptions = {}) => {
    const id = ++nextId.current;
    setToasts((current) => [...current.slice(-4), { id, message, kind: options.kind ?? "info", duration: options.duration ?? 4500 }]);
  }, []);
  const confirm = useCallback((options: DialogOptions): Promise<boolean> => new Promise((resolve) => {
    queue.current.push({ options, resolve });
    setActive((old) => !old); // request the next queued dialog
  }), []);
  useEffect(() => { if (!dialog && queue.current.length) setDialog(queue.current.shift()!); }, [active, dialog]);
  const finish = (accepted: boolean) => {
    if (!dialog) return;
    dialog.resolve(accepted);
    setDialog(null);
    setActive((old) => !old);
  };
  useEffect(() => {
    const element = modal.current;
    if (!dialog || !element) return;
    const opener = document.activeElement;
    element.showModal();
    initialFocus.current?.focus();
    return () => {
      element.close();
      if (opener instanceof HTMLElement && opener.isConnected) opener.focus();
    };
  }, [dialog]);
  useEffect(() => () => {
    queue.current.forEach((item) => item.resolve(false));
  }, []);
  const service = useMemo(() => ({ toast, confirm, dismiss }), [toast, confirm, dismiss]);
  return <FeedbackContext.Provider value={service}>
    {children}
    <div className="ra-toast-stack" aria-live="polite">
      {toasts.map((item) => <ToastMessage key={item.id} item={item} dismiss={dismiss}/>) }
    </div>
    {dialog && <dialog ref={modal} className="ra-dialog" role="alertdialog" aria-modal="true"
      aria-labelledby="ra-dialog-title" aria-describedby={dialog.options.message ? "ra-dialog-description" : undefined}
      onCancel={(event) => { event.preventDefault(); finish(false); }}
      onKeyDown={(event) => {
        if (event.key !== "Tab" || event.defaultPrevented) return;
        const items = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(
          'a[href], button, input, select, textarea, [tabindex], [contenteditable="true"]',
        )).filter((item) => item.tabIndex >= 0 && !item.matches(":disabled") && item.getClientRects().length > 0
          && getComputedStyle(item).visibility !== "hidden" && !item.closest("[inert]"));
        const first = items[0], last = items.at(-1);
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault(); last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault(); first?.focus();
        }
      }}
      onClick={(event) => {
        if (event.currentTarget !== event.target) return;
        const rect = event.currentTarget.getBoundingClientRect();
        if (event.clientX < rect.left || event.clientX > rect.right ||
            event.clientY < rect.top || event.clientY > rect.bottom) finish(false);
      }}>
      <div className="ra-dialog-head"><h2 id="ra-dialog-title">{dialog.options.title}</h2>
        <button onClick={() => finish(false)} aria-label="Close dialog"><X size={18}/></button></div>
      {dialog.options.message && <p id="ra-dialog-description">{dialog.options.message}</p>}
      {dialog.options.content}
      <div className="ra-dialog-actions">
        <button ref={dialog.options.destructive ? initialFocus : undefined} className="btn subtle"
          onClick={() => finish(false)}>{dialog.options.cancelLabel ?? "Cancel"}</button>
        <button ref={dialog.options.destructive ? undefined : initialFocus}
          className={`btn ${dialog.options.destructive ? "danger" : "primary"}`}
          onClick={() => finish(true)}>{dialog.options.confirmLabel ?? "Confirm"}</button>
      </div>
    </dialog>}
  </FeedbackContext.Provider>;
}
function ToastMessage({ item, dismiss }: { item: ToastItem; dismiss: (id: number) => void }) {
  useEffect(() => {
    if (item.duration <= 0) return;
    const timeout = window.setTimeout(() => dismiss(item.id), item.duration);
    return () => window.clearTimeout(timeout);
  }, [item.id, item.duration, dismiss]);
  const Icon = item.kind === "success" ? CheckCircle2 : item.kind === "error" ? AlertCircle : Info;
  return <div className={`ra-toast ra-toast-${item.kind}`} role={item.kind === "error" ? "alert" : "status"}>
    <Icon size={18}/><span>{item.message}</span><button onClick={() => dismiss(item.id)} aria-label="Dismiss notification"><X size={17}/></button>
  </div>;
}
