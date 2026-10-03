import { formatMicroUsd, formatPercent } from "@/lib/formatters";

interface BudgetBarProps {
  spentMicroUsd: number;
  budgetMicroUsd?: number | null;
  currency?: string;
  showLabels?: boolean;
}

export function BudgetBar({
  spentMicroUsd,
  budgetMicroUsd,
  showLabels = true,
}: BudgetBarProps) {
  if (!budgetMicroUsd || budgetMicroUsd <= 0) {
    return (
      <div className="flex flex-col gap-1">
        {showLabels && (
          <div className="flex justify-between text-xs text-[var(--text-muted)]">
            <span>Spend: {formatMicroUsd(spentMicroUsd)}</span>
            <span>No limit set</span>
          </div>
        )}
        <div className="h-2 w-full rounded-full bg-[var(--surface-raised)] border border-[var(--border)] overflow-hidden">
          <div className="h-full bg-[var(--text-muted)]/30 w-full" />
        </div>
      </div>
    );
  }

  const ratio = Math.min(spentMicroUsd / budgetMicroUsd, 1.5);
  const percentage = Math.min(Math.round((spentMicroUsd / budgetMicroUsd) * 100), 150);

  let barColor = "bg-[var(--success)]";
  let textColor = "text-[var(--success)]";
  if (spentMicroUsd >= budgetMicroUsd) {
    barColor = "bg-[var(--danger)]";
    textColor = "text-[var(--danger)]";
  } else if (spentMicroUsd / budgetMicroUsd >= 0.8) {
    barColor = "bg-[var(--warning)]";
    textColor = "text-[var(--warning)]";
  }

  return (
    <div className="flex flex-col gap-1.5 w-full">
      {showLabels && (
        <div className="flex justify-between items-center text-xs">
          <span className="text-[var(--text-muted)]">
            {formatMicroUsd(spentMicroUsd)} of {formatMicroUsd(budgetMicroUsd)}
          </span>
          <span className={`font-semibold tabular-nums ${textColor}`}>
            {formatPercent(spentMicroUsd / budgetMicroUsd)}
          </span>
        </div>
      )}
      <div
        className="h-2 w-full rounded-full bg-[var(--surface-raised)] border border-[var(--border)] overflow-hidden"
        role="progressbar"
        aria-valuenow={percentage}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Budget consumption"
      >
        <div
          className={`h-full transition-all duration-300 rounded-full ${barColor}`}
          style={{ width: `${Math.min(ratio * 100, 100)}%` }}
        />
      </div>
    </div>
  );
}
