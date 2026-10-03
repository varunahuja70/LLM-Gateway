import { isValidElement, ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: ReactNode;
  action?:
    | {
        label: string;
        onClick: () => void;
      }
    | ReactNode;
}

export function EmptyState({
  title,
  description,
  icon,
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-[var(--border)] p-12 text-center bg-[var(--surface)]/50">
      {icon && (
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[var(--muted)] text-[var(--text-muted)]">
          {icon}
        </div>
      )}
      <h3 className="text-base font-semibold text-[var(--text)]">{title}</h3>
      <p className="mt-1 max-w-sm text-sm text-[var(--text-muted)]">
        {description}
      </p>
      {action && (
        <div className="mt-5">
          {isValidElement(action) ? (
            action
          ) : (
            <button
              onClick={(action as { label: string; onClick: () => void }).onClick}
              className="inline-flex items-center justify-center rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white shadow-xs transition-colors hover:bg-[var(--accent-hover)] focus:outline-hidden focus:ring-2 focus:ring-[var(--ring)] focus:ring-offset-2"
            >
              {(action as { label: string; onClick: () => void }).label}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
