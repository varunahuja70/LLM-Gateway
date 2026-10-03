"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle,
  Clock,
  Coins,
  Cpu,
  Database,
  Layers,
  Sparkles,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { CallsChart } from "@/components/charts/CallsChart";
import { SpendChart } from "@/components/charts/SpendChart";
import { DateRangePicker, DateRangePreset } from "@/components/shared/DateRangePicker";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { KpiCard } from "@/components/shared/KpiCard";
import {
  formatLatency,
  formatMicroUsd,
  formatPercent,
  formatTokens,
} from "@/lib/formatters";
import {
  useAlerts,
  useModelsStats,
  useOverviewStats,
  useProjects,
  useSeedDemo,
  useSettings,
  useTimeseriesStats,
} from "@/lib/queries";

export default function OverviewPage() {
  const [datePreset, setDatePreset] = useState<DateRangePreset>("7d");
  const now = useMemo(() => new Date(), []);
  const initialFrom = useMemo(
    () => new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString(),
    [now]
  );
  const [from, setFrom] = useState<string | undefined>(initialFrom);
  const [to, setTo] = useState<string | undefined>(now.toISOString());

  const handleDateChange = (preset: DateRangePreset, newFrom?: string, newTo?: string) => {
    setDatePreset(preset);
    setFrom(newFrom);
    setTo(newTo);
  };

  const {
    data: overview,
    isLoading: isOverviewLoading,
    isError: isOverviewError,
    error: overviewError,
    refetch: refetchOverview,
  } = useOverviewStats(from, to);

  const {
    data: timeseries,
    isLoading: isTimeseriesLoading,
  } = useTimeseriesStats(from, to, datePreset === "24h" ? "hour" : "day");

  const {
    data: modelsData,
    isLoading: isModelsLoading,
  } = useModelsStats(from, to);

  const { data: projects, isLoading: isProjectsLoading } = useProjects();
  const { data: alerts } = useAlerts();
  const { data: settings } = useSettings();
  const seedDemoMutation = useSeedDemo();

  const handleLoadDemo = async () => {
    try {
      await seedDemoMutation.mutateAsync();
      refetchOverview();
    } catch {
      // toast or banner handles this
    }
  };

  const isLoading = isOverviewLoading || isProjectsLoading;

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Top Header Row with Date Picker */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-[var(--text)]">
              Overview
            </h1>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              System metrics, aggregate usage and performance across all projects.
            </p>
          </div>
          <DateRangePicker
            value={datePreset}
            onChange={handleDateChange}
            from={from}
            to={to}
          />
        </div>

        {/* Error State */}
        {isOverviewError && (
          <ErrorState
            title="Failed to load overview data"
            message={
              overviewError instanceof Error
                ? overviewError.message
                : "Could not retrieve stats from gateway."
            }
            onRetry={() => refetchOverview()}
          />
        )}

        {/* Empty State when no projects exist */}
        {!isLoading && projects && projects.length === 0 && (
          <EmptyState
            title="No projects configured"
            description="Create your first project or seed demo data to inspect spend, latency and quality metrics."
            icon={<Layers className="h-6 w-6" />}
            action={
              <div className="flex items-center gap-3">
                <Link
                  href="/projects"
                  className="rounded-md bg-[var(--accent)] px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-[var(--accent-hover)] transition-colors"
                >
                  Create Project
                </Link>
                {settings?.demo_mode && (
                  <button
                    onClick={handleLoadDemo}
                    disabled={seedDemoMutation.isPending}
                    className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--surface-raised)] px-4 py-2 text-xs font-semibold text-[var(--text)] hover:bg-[var(--muted)] transition-colors"
                  >
                    <Sparkles className="h-3.5 w-3.5 text-[var(--accent)]" />
                    <span>{seedDemoMutation.isPending ? "Seeding..." : "Load Demo Data"}</span>
                  </button>
                )}
              </div>
            }
          />
        )}

        {/* KPI Cards Row */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          <KpiCard
            title="Total Spend"
            value={formatMicroUsd(overview?.total_cost_micro_usd ?? 0)}
            subtitle="Calculated LLM cost"
            icon={<Coins className="h-4 w-4" />}
            loading={isLoading}
          />
          <KpiCard
            title="Total Calls"
            value={formatTokens(overview?.total_requests ?? 0)}
            subtitle="API completions"
            icon={<Activity className="h-4 w-4" />}
            loading={isLoading}
          />
          <KpiCard
            title="Error Rate"
            value={formatPercent(overview?.error_rate ?? 0)}
            subtitle="Failed or rejected"
            icon={<AlertTriangle className="h-4 w-4" />}
            loading={isLoading}
          />
          <KpiCard
            title="p95 Latency"
            value={formatLatency(overview?.avg_latency_ms ?? null)}
            subtitle="Average latency"
            icon={<Clock className="h-4 w-4" />}
            loading={isLoading}
          />
          <KpiCard
            title="Cache Savings"
            value={formatMicroUsd(overview?.saved_micro_usd ?? 0)}
            subtitle={`${formatPercent(overview?.cache_hit_rate ?? 0)} hit rate`}
            icon={<Database className="h-4 w-4" />}
            loading={isLoading}
          />
        </div>

        {/* Spend & Calls Charts */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <SpendChart
            data={timeseries?.data || []}
            loading={isTimeseriesLoading || isLoading}
          />
          <CallsChart
            data={timeseries?.data || []}
            loading={isTimeseriesLoading || isLoading}
          />
        </div>

        {/* Top Projects and Top Models Row */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Top Projects List */}
          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xs">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-semibold text-[var(--text)]">Top Projects</h3>
                <p className="text-xs text-[var(--text-muted)]">By overall spend</p>
              </div>
              <Link
                href="/projects"
                className="inline-flex items-center gap-1 text-xs font-medium text-[var(--accent)] hover:underline"
              >
                <span>View all</span>
                <ArrowRight className="h-3 w-3" />
              </Link>
            </div>

            {isLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-10 animate-pulse rounded bg-[var(--muted)]/50" />
                ))}
              </div>
            ) : !projects || projects.length === 0 ? (
              <div className="py-8 text-center text-xs text-[var(--text-muted)]">
                No active projects.
              </div>
            ) : (
              <div className="divide-y divide-[var(--border)]">
                {projects.slice(0, 5).map((project) => (
                  <Link
                    key={project.id}
                    href={`/projects/${project.id}`}
                    className="flex items-center justify-between py-2.5 px-2 hover:bg-[var(--surface-raised)] rounded-md transition-colors"
                  >
                    <div>
                      <span className="text-xs font-medium text-[var(--text)]">
                        {project.name}
                      </span>
                      <p className="text-[11px] text-[var(--text-muted)] font-mono">
                        {project.slug}
                      </p>
                    </div>
                    <div className="text-right">
                      <span className="text-xs font-semibold text-[var(--text)] tabular-nums">
                        {project.active_keys_count} active {project.active_keys_count === 1 ? "key" : "keys"}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

          {/* Top Models List */}
          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xs">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-semibold text-[var(--text)]">Top Models</h3>
                <p className="text-xs text-[var(--text-muted)]">By volume & quality</p>
              </div>
              <Link
                href="/models"
                className="inline-flex items-center gap-1 text-xs font-medium text-[var(--accent)] hover:underline"
              >
                <span>Compare all</span>
                <ArrowRight className="h-3 w-3" />
              </Link>
            </div>

            {isModelsLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-10 animate-pulse rounded bg-[var(--muted)]/50" />
                ))}
              </div>
            ) : !modelsData || modelsData.data.length === 0 ? (
              <div className="py-8 text-center text-xs text-[var(--text-muted)]">
                No model traffic recorded yet.
              </div>
            ) : (
              <div className="divide-y divide-[var(--border)]">
                {modelsData.data.slice(0, 5).map((item) => (
                  <div
                    key={`${item.provider}/${item.model}`}
                    className="flex items-center justify-between py-2.5 px-2"
                  >
                    <div className="flex items-center gap-2">
                      <Cpu className="h-4 w-4 text-[var(--text-muted)]" />
                      <div>
                        <span className="text-xs font-mono font-medium text-[var(--text)]">
                          {item.provider}/{item.model}
                        </span>
                        <div className="flex gap-2 text-[11px] text-[var(--text-muted)]">
                          <span>{formatTokens(item.total_requests)} calls</span>
                          <span>•</span>
                          <span>{formatLatency(item.p95_latency_ms)} p95</span>
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <span className="text-xs font-semibold text-[var(--text)] tabular-nums">
                        {formatMicroUsd(item.total_cost_micro_usd)}
                      </span>
                      <p className="text-[11px] text-[var(--text-muted)]">
                        {formatPercent(item.error_rate)} err
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Recent Alerts Strip */}
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 shadow-xs">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-[var(--text)]">Recent Alerts</span>
            <Link
              href="/alerts"
              className="text-xs font-medium text-[var(--accent)] hover:underline"
            >
              View all alerts
            </Link>
          </div>
          {!alerts || alerts.length === 0 ? (
            <div className="flex items-center gap-2 text-xs text-[var(--text-muted)] py-2">
              <CheckCircle className="h-3.5 w-3.5 text-[var(--success)]" />
              <span>All budgets and systems operating normally. No alerts triggered.</span>
            </div>
          ) : (
            <div className="divide-y divide-[var(--border)]">
              {alerts.slice(0, 3).map((alert) => (
                <div key={alert.id} className="flex items-center justify-between py-2 text-xs">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="h-3.5 w-3.5 text-[var(--warning)]" />
                    <span className="font-mono text-[var(--text)]">{alert.project_id.slice(0, 8)}...</span>
                    <span className="text-[var(--text-muted)]">
                      reached {alert.threshold_percent}% {alert.period} budget threshold
                    </span>
                  </div>
                  <span className="text-[10px] text-[var(--text-muted)]">
                    {new Date(alert.created_at).toLocaleDateString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
