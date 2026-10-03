"use client";

import { ReactNode, useState } from "react";
import { AlertTriangle, X } from "lucide-react";

interface ConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  description: ReactNode;
  confirmText?: string;
  confirmLabel?: string;
  destructive?: boolean;
  isLoading?: boolean;
}

export function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  description,
  confirmText,
  confirmLabel = "Confirm",
  destructive = false,
  isLoading = false,
}: ConfirmDialogProps) {
  const [typedInput, setTypedInput] = useState("");

  if (!isOpen) return null;

  const isConfirmed = confirmText ? typedInput === confirmText : true;

  const handleConfirm = () => {
    if (isConfirmed && !isLoading) {
      onConfirm();
      setTypedInput("");
    }
  };

  const handleClose = () => {
    setTypedInput("");
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] p-6 shadow-xl animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            {destructive && (
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--danger)]/15 text-[var(--danger)]">
                <AlertTriangle className="h-4 w-4" />
              </div>
            )}
            <h3 className="text-base font-semibold text-[var(--text)]">
              {title}
            </h3>
          </div>
          <button
            onClick={handleClose}
            className="rounded-md p-1 text-[var(--text-muted)] hover:bg-[var(--muted)] hover:text-[var(--text)]"
            aria-label="Close dialog"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-3 text-sm text-[var(--text-muted)] leading-relaxed">
          {description}
        </div>

        {confirmText && (
          <div className="mt-4">
            <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">
              Type <span className="font-semibold text-[var(--text)] select-all">{confirmText}</span> to confirm:
            </label>
            <input
              type="text"
              value={typedInput}
              onChange={(e) => setTypedInput(e.target.value)}
              placeholder={confirmText}
              className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
              autoFocus
            />
          </div>
        )}

        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={handleClose}
            disabled={isLoading}
            className="rounded-md border border-[var(--border)] px-3.5 py-2 text-xs font-medium text-[var(--text)] hover:bg-[var(--muted)]"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={!isConfirmed || isLoading}
            className={`rounded-md px-3.5 py-2 text-xs font-medium text-white transition-opacity ${
              destructive
                ? "bg-[var(--danger)] hover:bg-[var(--danger)]/90"
                : "bg-[var(--accent)] hover:bg-[var(--accent-hover)]"
            } ${!isConfirmed || isLoading ? "opacity-40 cursor-not-allowed" : ""}`}
          >
            {isLoading ? "Processing..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
