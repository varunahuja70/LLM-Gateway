"use client";

import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  Bell,
  CheckCircle,
  Clock,
  RefreshCw,
  XCircle,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { BudgetBar } from "@/components/shared/BudgetBar";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import {
  formatMicroUsd,
} from "@/lib/formatters";
import {
  useAlerts,
  useProjects,
} from "@/lib/queries";

export default function AlertsPage() {
  const {
    data: alerts,
    isLoading: isAlertsLoading,
    isError: isAlertsError,
    error: alertsError,
    refetch: refetchAlerts,
  } = useAlerts();

  const {
    data: projects,
    isLoading: isProjectsLoading,
    refetch: refetchProjects,
  } = useProjects();

  const isLoading = isAlertsLoading || isProjectsLoading;

  const handleRefresh = () => {
    refetchAlerts();
    refetchProjects();
  };

  return (
    <AppShell>
      <div className="space-y-8">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-[var(--text)]">
              Budgets & Alerts
            </h1>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              Monitor project budget thresholds, threshold violations, and webhook delivery status.
            </p>
          </div>

          <button
            onClick={handleRefresh}
            className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-medium text-[var(--text)] hover:bg-[var(--surface-raised)] transition-colors self-start sm:self-auto"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span>Refresh</span>
          </button>
        </div>

        {/* Error State */}
        {isAlertsError && (
          <ErrorState
            title="Failed to load alerts"
            message={
              alertsError instanceof Error
                ? alertsError.message
                : "Could not fetch budget alerts from gateway."
            }
            onRetry={handleRefresh}
          />
        )}

        {/* SECTION 1: PER-PROJECT BUDGET OVERVIEW */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-[var(--text)]">
                Active Project Budgets
              </h2>
              <p className="text-xs text-[var(--text-muted)]">
                Usage and limits configured per workspace.
              </p>
            </div>
            <Link
              href="/projects"
              className="text-xs font-medium text-[var(--accent)] hover:underline"
            >
              Configure budgets
            </Link>
          </div>

          {isLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-28 animate-pulse rounded-lg bg-[var(--surface)] border border-[var(--border)]" />
              ))}
            </div>
          ) : !projects || projects.length === 0 ? (
            <div className="rounded-lg border border-dashed border-[var(--border)] p-6 text-center text-xs text-[var(--text-muted)]">
              No projects configured. Create a project to set budget alerts.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {projects.map((p) => (
                <div
                  key={p.id}
                  className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 shadow-xs flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between">
                      <Link
                        href={`/projects/${p.id}`}
                        className="text-xs font-semibold text-[var(--text)] hover:text-[var(--accent)] transition-colors"
                      >
                        {p.name}
                      </Link>
                      <span className="font-mono text-[10px] text-[var(--text-muted)]">
                        {p.slug}
                      </span>
                    </div>

                    <div className="mt-3">
                      <BudgetBar spentMicroUsd={0} budgetMicroUsd={null} />
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-[var(--border)] flex items-center justify-between text-[11px] text-[var(--text-muted)]">
                    <span>{p.active_keys_count} active keys</span>
                    <Link
                      href={`/projects/${p.id}`}
                      className="inline-flex items-center gap-1 font-medium text-[var(--text)] hover:text-[var(--accent)]"
                    >
                      <span>Manage</span>
                      <ArrowRight className="h-3 w-3" />
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* SECTION 2: ALERT NOTIFICATION HISTORY */}
        <div className="space-y-4">
          <div>
            <h2 className="text-sm font-semibold text-[var(--text)]">
              Alert Trigger History
            </h2>
            <p className="text-xs text-[var(--text-muted)]">
              Threshold triggers, limit notifications, and external webhook delivery status.
            </p>
          </div>

          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-12 animate-pulse rounded bg-[var(--surface)] border border-[var(--border)]" />
              ))}
            </div>
          ) : !alerts || alerts.length === 0 ? (
            <EmptyState
              title="No budget alerts triggered"
              description="When a project exceeds 80% or 100% of its daily or monthly limit, notifications and webhook payloads appear here."
              icon={<Bell className="h-6 w-6" />}
            />
          ) : (
            <div className="overflow-x-auto rounded-lg border border-[var(--border)] bg-[var(--surface)] shadow-xs">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-[var(--border)] bg-[var(--surface-raised)] text-[var(--text-muted)]">
                  <tr>
                    <th className="py-3 px-4 font-medium">Project</th>
                    <th className="py-3 px-4 font-medium">Trigger Threshold</th>
                    <th className="py-3 px-4 font-medium">Spend / Limit</th>
                    <th className="py-3 px-4 font-medium">Webhook Delivery</th>
                    <th className="py-3 px-4 font-medium text-right">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)] text-[var(--text)]">
                  {alerts.map((a) => {
                    const isSuccess = a.webhook_status === "success" || a.webhook_status === "delivered";
                    const isFailed = a.webhook_status === "failed";

                    return (
                      <tr key={a.id} className="hover:bg-[var(--surface-raised)]/60 transition-colors">
                        {/* Project */}
                        <td className="py-3 px-4">
                          <Link
                            href={`/projects/${a.project_id}`}
                            className="font-mono text-xs font-medium text-[var(--accent)] hover:underline"
                          >
                            {a.project_id.slice(0, 12)}...
                          </Link>
                          <p className="text-[10px] text-[var(--text-muted)] capitalize mt-0.5">
                            {a.period} limit
                          </p>
                        </td>

                        {/* Threshold */}
                        <td className="py-3 px-4">
                          <div className="inline-flex items-center gap-1.5 rounded-full bg-[var(--warning)]/10 px-2.5 py-0.5 text-xs font-semibold text-[var(--warning)]">
                            <AlertTriangle className="h-3.5 w-3.5" />
                            <span>{a.threshold_percent}% Limit Reached</span>
                          </div>
                        </td>

                        {/* Spend vs Limit */}
                        <td className="py-3 px-4 tabular-nums">
                          <span className="font-semibold text-[var(--text)]">
                            {formatMicroUsd(a.spend_micro_usd)}
                          </span>
                          <span className="text-[var(--text-muted)]"> of </span>
                          <span className="text-[var(--text-muted)]">
                            {formatMicroUsd(a.budget_micro_usd)}
                          </span>
                        </td>

                        {/* Webhook Delivery */}
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-1.5">
                            {isSuccess ? (
                              <span className="inline-flex items-center gap-1 rounded bg-[var(--success)]/10 px-2 py-0.5 text-[11px] font-medium text-[var(--success)]">
                                <CheckCircle className="h-3 w-3" />
                                <span>Delivered ({a.webhook_attempts})</span>
                              </span>
                            ) : isFailed ? (
                              <div className="flex flex-col gap-0.5">
                                <span className="inline-flex items-center gap-1 rounded bg-[var(--danger)]/10 px-2 py-0.5 text-[11px] font-medium text-[var(--danger)]">
                                  <XCircle className="h-3 w-3" />
                                  <span>Failed ({a.webhook_attempts} attempts)</span>
                                </span>
                                {a.last_error && (
                                  <span className="text-[10px] text-[var(--danger)] font-mono truncate max-w-xs">
                                    {a.last_error}
                                  </span>
                                )}
                              </div>
                            ) : (
                              <span className="inline-flex items-center gap-1 rounded bg-[var(--surface-raised)] border border-[var(--border)] px-2 py-0.5 text-[11px] text-[var(--text-muted)]">
                                <Clock className="h-3 w-3" />
                                <span className="capitalize">{a.webhook_status || "None"}</span>
                              </span>
                            )}
                          </div>
                        </td>

                        {/* Timestamp */}
                        <td className="py-3 px-4 text-right font-mono text-[11px] text-[var(--text-muted)]">
                          {new Date(a.created_at).toLocaleString()}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
