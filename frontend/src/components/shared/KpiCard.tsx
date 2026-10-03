import { ReactNode } from "react";

interface KpiCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: {
    value: string;
    isPositive?: boolean;
    isNeutral?: boolean;
  };
  icon?: ReactNode;
  loading?: boolean;
}

export function KpiCard({
  title,
  value,
  subtitle,
  trend,
  icon,
  loading = false,
}: KpiCardProps) {
  if (loading) {
    return (
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xs">
        <div className="h-4 w-24 animate-pulse rounded bg-[var(--muted)]" />
        <div className="mt-3 h-8 w-36 animate-pulse rounded bg-[var(--muted)]" />
        <div className="mt-2 h-3 w-20 animate-pulse rounded bg-[var(--muted)]" />
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xs transition-colors hover:border-[var(--accent)]/40">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-[var(--text-muted)] tracking-wide uppercase">
          {title}
        </span>
        {icon && <div className="text-[var(--text-muted)]">{icon}</div>}
      </div>

      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-2xl font-bold tracking-tight text-[var(--text)] tabular-nums">
          {value}
        </span>
        {trend && (
          <span
            className={`text-xs font-medium ${
              trend.isNeutral
                ? "text-[var(--text-muted)]"
                : trend.isPositive
                ? "text-[var(--success)]"
                : "text-[var(--danger)]"
            }`}
          >
            {trend.value}
          </span>
        )}
      </div>

      {subtitle && (
        <p className="mt-1 text-xs text-[var(--text-muted)]">{subtitle}</p>
      )}
    </div>
  );
}
