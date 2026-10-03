"use client";

import { useMemo, useState } from "react";
import {
  ArrowUpDown,
  Cpu,
  RefreshCw,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { DateRangePicker, DateRangePreset } from "@/components/shared/DateRangePicker";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { ModelQualityStat } from "@/lib/api-types";
import {
  formatLatency,
  formatMicroUsd,
  formatPercent,
  formatTokens,
} from "@/lib/formatters";
import {
  useModelsStats,
  useProjects,
  useSeedDemo,
  useSettings,
} from "@/lib/queries";

type SortField =
  | "calls"
  | "cost_per_1k"
  | "tokens"
  | "p50"
  | "p95"
  | "error_rate"
  | "feedback";

export default function ModelsPage() {
  const [projectId, setProjectId] = useState<string>("");
  const [sortField, setSortField] = useState<SortField>("calls");
  const [sortAsc, setSortAsc] = useState<boolean>(false);

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

  const { data: projects } = useProjects();
  const { data: settings } = useSettings();
  const {
    data: modelsData,
    isLoading,
    isError,
    error,
    refetch,
  } = useModelsStats(from, to, projectId || undefined);
  const seedDemoMutation = useSeedDemo();

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  const handleSeedDemo = async () => {
    try {
      await seedDemoMutation.mutateAsync();
      refetch();
    } catch {
      // handled
    }
  };

  const rawModels = useMemo(() => modelsData?.data || [], [modelsData?.data]);

  // Compute maximum values for visual bars
  const maxCalls = useMemo(
    () => Math.max(...rawModels.map((m) => m.total_requests), 1),
    [rawModels]
  );
  const maxLatency = useMemo(
    () => Math.max(...rawModels.map((m) => m.p95_latency_ms || 0), 1),
    [rawModels]
  );

  const sortedModels = useMemo(() => {
    return [...rawModels].sort((a: ModelQualityStat, b: ModelQualityStat) => {
      let valA = 0;
      let valB = 0;

      switch (sortField) {
        case "calls":
          valA = a.total_requests;
          valB = b.total_requests;
          break;
        case "cost_per_1k": {
          valA = a.total_requests > 0 ? (a.total_cost_micro_usd / a.total_requests) * 1000 : 0;
          valB = b.total_requests > 0 ? (b.total_cost_micro_usd / b.total_requests) * 1000 : 0;
          break;
        }
        case "tokens":
          valA = a.total_requests > 0 ? a.total_tokens / a.total_requests : 0;
          valB = b.total_requests > 0 ? b.total_tokens / b.total_requests : 0;
          break;
        case "p50":
          valA = a.p50_latency_ms || 0;
          valB = b.p50_latency_ms || 0;
          break;
        case "p95":
          valA = a.p95_latency_ms || 0;
          valB = b.p95_latency_ms || 0;
          break;
        case "error_rate":
          valA = a.error_rate;
          valB = b.error_rate;
          break;
        case "feedback":
          valA = a.avg_feedback_score || 0;
          valB = b.avg_feedback_score || 0;
          break;
      }

      return sortAsc ? valA - valB : valB - valA;
    });
  }, [rawModels, sortField, sortAsc]);

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-[var(--text)]">
              Model Quality & Cost Comparison
            </h1>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              Benchmark latency distributions, cost efficiency, error rates and quality across models.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <select
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
            >
              <option value="">All Projects</option>
              {projects?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <DateRangePicker
              value={datePreset}
              onChange={handleDateChange}
              from={from}
              to={to}
            />
            <button
              onClick={() => refetch()}
              className="rounded-md border border-[var(--border)] bg-[var(--surface)] p-2 text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-raised)] transition-colors"
              title="Refresh models data"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Error State */}
        {isError && (
          <ErrorState
            title="Failed to load model statistics"
            message={
              error instanceof Error
                ? error.message
                : "Could not fetch model metrics from gateway."
            }
            onRetry={() => refetch()}
          />
        )}

        {/* Loading State */}
        {isLoading && (
          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 space-y-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-16 animate-pulse rounded bg-[var(--muted)]/50" />
            ))}
          </div>
        )}

        {/* Empty State */}
        {!isLoading && sortedModels.length === 0 && (
          <EmptyState
            title="No model metrics recorded"
            description="Route completions through your gateway keys or load demo data to analyze models."
            icon={<Cpu className="h-6 w-6" />}
            action={
              settings?.demo_mode ? (
                <button
                  onClick={handleSeedDemo}
                  disabled={seedDemoMutation.isPending}
                  className="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-[var(--accent-hover)] transition-colors"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>{seedDemoMutation.isPending ? "Seeding..." : "Load Demo Data"}</span>
                </button>
              ) : undefined
            }
          />
        )}

        {/* Comparison Table */}
        {!isLoading && sortedModels.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-[var(--border)] bg-[var(--surface)] shadow-xs">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-[var(--border)] bg-[var(--surface-raised)] text-[var(--text-muted)]">
                <tr>
                  <th className="py-3 px-4 font-medium">Model</th>

                  <th
                    onClick={() => handleSort("calls")}
                    className="py-3 px-4 font-medium cursor-pointer hover:text-[var(--text)] select-none"
                  >
                    <div className="flex items-center gap-1">
                      <span>Volume (Calls)</span>
                      <ArrowUpDown className="h-3 w-3" />
                    </div>
                  </th>

                  <th
                    onClick={() => handleSort("cost_per_1k")}
                    className="py-3 px-4 font-medium cursor-pointer hover:text-[var(--text)] select-none"
                  >
                    <div className="flex items-center gap-1">
                      <span>Cost / 1K Calls</span>
                      <ArrowUpDown className="h-3 w-3" />
                    </div>
                  </th>

                  <th
                    onClick={() => handleSort("tokens")}
                    className="py-3 px-4 font-medium cursor-pointer hover:text-[var(--text)] select-none"
                  >
                    <div className="flex items-center gap-1">
                      <span>Avg Tokens</span>
                      <ArrowUpDown className="h-3 w-3" />
                    </div>
                  </th>

                  <th
                    onClick={() => handleSort("p95")}
                    className="py-3 px-4 font-medium cursor-pointer hover:text-[var(--text)] select-none min-w-[140px]"
                  >
                    <div className="flex items-center gap-1">
                      <span>Latency (p50 / p95)</span>
                      <ArrowUpDown className="h-3 w-3" />
                    </div>
                  </th>

                  <th
                    onClick={() => handleSort("error_rate")}
                    className="py-3 px-4 font-medium cursor-pointer hover:text-[var(--text)] select-none min-w-[120px]"
                  >
                    <div className="flex items-center gap-1">
                      <span>Error Rate</span>
                      <ArrowUpDown className="h-3 w-3" />
                    </div>
                  </th>

                  <th
                    onClick={() => handleSort("feedback")}
                    className="py-3 px-4 font-medium cursor-pointer hover:text-[var(--text)] select-none text-right"
                  >
                    <div className="flex items-center justify-end gap-1">
                      <span>Feedback</span>
                      <ArrowUpDown className="h-3 w-3" />
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)] text-[var(--text)]">
                {sortedModels.map((m) => {
                  const avgTok = m.total_requests > 0 ? Math.round(m.total_tokens / m.total_requests) : 0;
                  const costPer1k = m.total_requests > 0 ? Math.round((m.total_cost_micro_usd / m.total_requests) * 1000) : 0;
                  const p95Ratio = (m.p95_latency_ms || 0) / maxLatency;
                  const callsRatio = m.total_requests / maxCalls;

                  return (
                    <tr
                      key={`${m.provider}/${m.model}`}
                      className="hover:bg-[var(--surface-raised)]/60 transition-colors"
                    >
                      {/* Model & Provider */}
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <Cpu className="h-4 w-4 text-[var(--text-muted)] shrink-0" />
                          <div>
                            <span className="font-mono font-medium text-[var(--text)]">
                              {m.model}
                            </span>
                            <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider">
                              {m.provider}
                            </p>
                          </div>
                        </div>
                      </td>

                      {/* Calls with Volume Bar */}
                      <td className="py-3 px-4 tabular-nums">
                        <div className="flex flex-col gap-1">
                          <span className="font-semibold text-[var(--text)]">
                            {formatTokens(m.total_requests)}
                          </span>
                          <div className="h-1.5 w-24 rounded-full bg-[var(--surface-raised)] border border-[var(--border)] overflow-hidden">
                            <div
                              className="h-full bg-[var(--accent)] rounded-full"
                              style={{ width: `${Math.min(callsRatio * 100, 100)}%` }}
                            />
                          </div>
                        </div>
                      </td>

                      {/* Cost per 1K */}
                      <td className="py-3 px-4 tabular-nums">
                        <span className="font-semibold text-[var(--text)]">
                          {formatMicroUsd(costPer1k)}
                        </span>
                        <p className="text-[11px] text-[var(--text-muted)]">
                          Total: {formatMicroUsd(m.total_cost_micro_usd)}
                        </p>
                      </td>

                      {/* Avg Tokens */}
                      <td className="py-3 px-4 tabular-nums">
                        <span className="font-medium text-[var(--text)]">
                          {formatTokens(avgTok)}
                        </span>
                        <p className="text-[11px] text-[var(--text-muted)]">
                          {formatTokens(m.total_tokens)} total
                        </p>
                      </td>

                      {/* Latency with Bar */}
                      <td className="py-3 px-4 tabular-nums">
                        <div className="flex flex-col gap-1">
                          <div className="flex items-center gap-1.5 text-xs">
                            <span className="text-[var(--text-muted)] font-mono">
                              {formatLatency(m.p50_latency_ms)}
                            </span>
                            <span>/</span>
                            <span className="font-semibold text-[var(--text)] font-mono">
                              {formatLatency(m.p95_latency_ms)}
                            </span>
                          </div>
                          <div className="h-1.5 w-28 rounded-full bg-[var(--surface-raised)] border border-[var(--border)] overflow-hidden">
                            <div
                              className="h-full bg-blue-500 rounded-full"
                              style={{ width: `${Math.min(p95Ratio * 100, 100)}%` }}
                            />
                          </div>
                        </div>
                      </td>

                      {/* Error Rate with Bar */}
                      <td className="py-3 px-4 tabular-nums">
                        <div className="flex flex-col gap-1">
                          <span
                            className={`font-semibold ${
                              m.error_rate > 0.05
                                ? "text-[var(--danger)]"
                                : m.error_rate > 0
                                ? "text-[var(--warning)]"
                                : "text-[var(--text-muted)]"
                            }`}
                          >
                            {formatPercent(m.error_rate)}
                          </span>
                          <div className="h-1.5 w-20 rounded-full bg-[var(--surface-raised)] border border-[var(--border)] overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                m.error_rate > 0.05 ? "bg-[var(--danger)]" : "bg-[var(--warning)]"
                              }`}
                              style={{ width: `${Math.min(m.error_rate * 100, 100)}%` }}
                            />
                          </div>
                        </div>
                      </td>

                      {/* Feedback Score */}
                      <td className="py-3 px-4 text-right">
                        {m.avg_feedback_score === null || m.avg_feedback_score === undefined ? (
                          <span className="text-[var(--text-muted)]">—</span>
                        ) : m.avg_feedback_score >= 0.5 ? (
                          <span className="inline-flex items-center gap-1 text-[var(--success)] font-semibold tabular-nums">
                            <ThumbsUp className="h-3 w-3" />
                            {formatPercent(m.avg_feedback_score)}
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[var(--danger)] font-semibold tabular-nums">
                            <ThumbsDown className="h-3 w-3" />
                            {formatPercent(m.avg_feedback_score)}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AppShell>
  );
}
