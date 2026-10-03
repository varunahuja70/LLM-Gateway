import { AlertCircle } from "lucide-react";

interface ErrorStateProps {
  title?: string;
  message: string;
  requestId?: string;
  onRetry?: () => void;
}

export function ErrorState({
  title = "Something went wrong",
  message,
  requestId,
  onRetry,
}: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-[var(--danger)]/30 bg-[var(--danger)]/5 p-8 text-center">
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-[var(--danger)]/10 text-[var(--danger)]">
        <AlertCircle className="h-5 w-5" />
      </div>
      <h3 className="text-sm font-semibold text-[var(--text)]">{title}</h3>
      <p className="mt-1 max-w-md text-xs text-[var(--text-muted)]">{message}</p>
      {requestId && (
        <span className="mt-2 text-[10px] font-mono text-[var(--text-muted)] opacity-70">
          Request ID: {requestId}
        </span>
      )}
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 rounded-md border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-1.5 text-xs font-medium text-[var(--text)] shadow-xs transition-colors hover:bg-[var(--muted)]"
        >
          Try again
        </button>
      )}
    </div>
  );
}
