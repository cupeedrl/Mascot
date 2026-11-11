import { useEffect, useRef } from "react";
import { AlertTriangle, ShieldCheck } from "lucide-react";

export interface ConfirmRequest {
  title: string;
  message: string;
  confirmLabel: string;
  tone?: "danger" | "primary";
}

interface ConfirmDialogProps {
  request: ConfirmRequest | null;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * In-page confirmation. Native window.confirm() is blocked by some embedded
 * browsers (it returns false without showing anything), so never use it.
 */
export function ConfirmDialog({ request, busy = false, onConfirm, onCancel }: ConfirmDialogProps) {
  const cancelRef = useRef<HTMLButtonElement | null>(null);
  // Keep the latest callbacks without re-running the focus effect every render.
  const latest = useRef({ onCancel, busy });
  latest.current = { onCancel, busy };

  useEffect(() => {
    if (!request) return;
    cancelRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !latest.current.busy) latest.current.onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [request]);

  if (!request) return null;
  const danger = request.tone === "danger";

  return (
    <div
      className="modal-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onCancel();
      }}
    >
      <section
        className="confirm-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-message"
      >
        <span className={`confirm-dialog-icon${danger ? " danger" : ""}`} aria-hidden="true">
          {danger ? <AlertTriangle size={20} /> : <ShieldCheck size={20} />}
        </span>
        <h2 id="confirm-dialog-title">{request.title}</h2>
        <p id="confirm-dialog-message">{request.message}</p>
        <div className="confirm-dialog-actions">
          <button ref={cancelRef} className="secondary-button" type="button" onClick={onCancel} disabled={busy}>
            Hủy
          </button>
          <button
            className={danger ? "danger-button confirm-dialog-danger" : "primary-button"}
            type="button"
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? "Đang xử lý…" : request.confirmLabel}
          </button>
        </div>
      </section>
    </div>
  );
}
