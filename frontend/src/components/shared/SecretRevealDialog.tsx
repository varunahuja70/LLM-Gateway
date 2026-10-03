"use client";

import { useState } from "react";
import { Check, Copy, KeyRound, ShieldAlert } from "lucide-react";

interface SecretRevealDialogProps {
  isOpen: boolean;
  onClose: () => void;
  secret: string;
  title?: string;
  description?: string;
}

export function SecretRevealDialog({
  isOpen,
  onClose,
  secret,
  title = "Gateway API Key Created",
  description = "Please save this secret key now. For security, it will never be displayed again.",
}: SecretRevealDialogProps) {
  const [copied, setCopied] = useState(false);
  const [confirmedSaved, setConfirmedSaved] = useState(false);

  if (!isOpen) return null;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(secret);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  const handleClose = () => {
    if (confirmedSaved) {
      setConfirmedSaved(false);
      setCopied(false);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs">
      <div className="w-full max-w-lg rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] p-6 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--accent)]/10 text-[var(--accent)]">
            <KeyRound className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-[var(--text)]">
              {title}
            </h3>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              {description}
            </p>
          </div>
        </div>

        <div className="mt-5 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3">
          <div className="flex items-center justify-between gap-3">
            <code className="font-mono text-xs text-[var(--text)] break-all select-all font-semibold">
              {secret}
            </code>
            <button
              onClick={handleCopy}
              className="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-[var(--muted)] px-2.5 py-1.5 text-xs font-medium text-[var(--text)] hover:bg-[var(--border)] transition-colors"
            >
              {copied ? (
                <>
                  <Check className="h-3.5 w-3.5 text-[var(--success)]" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="h-3.5 w-3.5 text-[var(--text-muted)]" />
                  Copy
                </>
              )}
            </button>
          </div>
        </div>

        <div className="mt-4 flex items-start gap-2.5 rounded-md bg-[var(--warning)]/10 p-3 text-xs text-[var(--warning)]">
          <ShieldAlert className="h-4 w-4 shrink-0 mt-0.5" />
          <span>
            Store this key securely. Anyone with access to this key can make calls on your project budget.
          </span>
        </div>

        <div className="mt-5 flex items-center gap-2">
          <input
            type="checkbox"
            id="saved-confirm"
            checked={confirmedSaved}
            onChange={(e) => setConfirmedSaved(e.target.checked)}
            className="h-4 w-4 rounded border-[var(--border)] text-[var(--accent)] focus:ring-[var(--ring)]"
          />
          <label
            htmlFor="saved-confirm"
            className="text-xs font-medium text-[var(--text)] cursor-pointer select-none"
          >
            I have saved this key in a secure location
          </label>
        </div>

        <div className="mt-6 flex justify-end">
          <button
            type="button"
            onClick={handleClose}
            disabled={!confirmedSaved}
            className={`rounded-md bg-[var(--accent)] px-4 py-2 text-xs font-medium text-white shadow-xs transition-opacity ${
              !confirmedSaved ? "opacity-40 cursor-not-allowed" : "hover:bg-[var(--accent-hover)]"
            }`}
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
