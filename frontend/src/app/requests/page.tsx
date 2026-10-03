"use client";

import { useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowRight,
  Filter,
  RefreshCw,
  Search,
  Sparkles,
  Zap,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { RequestDetailSheet } from "@/components/requests/RequestDetailSheet";
import { DateRangePicker, DateRangePreset } from "@/components/shared/DateRangePicker";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import {
  formatLatency,
  formatMicroUsd,
  formatTokens,
} from "@/lib/formatters";
import {
  useProjects,
  useRequests,
  useSeedDemo,
  useSettings,
} from "@/lib/queries";

export default function RequestExplorerPage() {
  const searchParams = useSearchParams();
  const initialProjectId = searchParams.get("project_id") || "";

  const [projectId, setProjectId] = useState<string>(initialProjectId);
  const [provider, setProvider] = useState<string>("");
  const [status, setStatus] = useState<string>("");
  const [cacheHitOnly, setCacheHitOnly] = useState<boolean>(false);
  const [fallbackOnly, setFallbackOnly] = useState<boolean>(false);
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [cursor, setCursor] = useState<string | undefined>(undefined);
  const [cursorStack, setCursorStack] = useState<string[]>([]);
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null);

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
    setCursor(undefined);
    setCursorStack([]);
  };

  const { data: projects } = useProjects();
  const { data: settings } = useSettings();
  const seedDemoMutation = useSeedDemo();

  const queryFilters = {
    project_id: projectId || undefined,
    provider: provider || undefined,
    status: status || undefined,
    cache_hit: cacheHitOnly ? true : undefined,
    fallback_used: fallbackOnly ? true : undefined,
    search: searchTerm.trim() || undefined,
    from: from || undefined,
    to: to || undefined,
    cursor: cursor || undefined,
    limit: 25,
  };

  const {
    data: requestsData,
    isLoading,
    isError,
    error,
    refetch,
  } = useRequests(queryFilters);

  const handleNextPage = () => {
    if (requestsData?.next_cursor) {
      setCursorStack((prev) => [...prev, cursor || ""]);
      setCursor(requestsData.next_cursor);
    }
  };

  const handlePrevPage = () => {
    if (cursorStack.length > 0) {
      const prevStack = [...cursorStack];
      const prevCursor = prevStack.pop();
      setCursorStack(prevStack);
      setCursor(prevCursor || undefined);
    }
  };

  const handleResetFilters = () => {
    setProjectId("");
    setProvider("");
    setStatus("");
    setCacheHitOnly(false);
    setFallbackOnly(false);
    setSearchTerm("");
    setCursor(undefined);
    setCursorStack([]);
  };

  const handleSeedDemo = async () => {
    try {
      await seedDemoMutation.mutateAsync();
      refetch();
    } catch {
      // handled
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-[var(--text)]">
              Request Explorer
            </h1>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              Inspect live completions, token usage, latency distributions and fallbacks.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <DateRangePicker
              value={datePreset}
              onChange={handleDateChange}
              from={from}
              to={to}
            />
            <button
              onClick={() => refetch()}
              className="rounded-md border border-[var(--border)] bg-[var(--surface)] p-2 text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-raised)] transition-colors"
              title="Refresh requests"
              aria-label="Refresh requests"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Filter Controls Bar */}
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 shadow-xs space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {/* Search Input */}
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-[var(--text-muted)]" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value);
                  setCursor(undefined);
                }}
                placeholder="Search request ID or user tag..."
                className="w-full rounded-md border border-[var(--border)] bg-[var(--surface-raised)] py-1.5 pl-9 pr-3 text-xs text-[var(--text)] placeholder-[var(--text-muted)] focus:border-[var(--accent)] focus:outline-hidden"
              />
            </div>

            {/* Project Filter */}
            <select
              value={projectId}
              onChange={(e) => {
                setProjectId(e.target.value);
                setCursor(undefined);
              }}
              className="rounded-md border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-1.5 text-xs text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
            >
              <option value="">All Projects</option>
              {projects?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>

            {/* Provider Filter */}
            <select
              value={provider}
              onChange={(e) => {
                setProvider(e.target.value);
                setCursor(undefined);
              }}
              className="rounded-md border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-1.5 text-xs text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
            >
              <option value="">All Providers</option>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="google">Google Gemini</option>
              <option value="deepseek">DeepSeek</option>
              <option value="groq">Groq</option>
              <option value="mistral">Mistral</option>
              <option value="bedrock">AWS Bedrock</option>
              <option value="openrouter">OpenRouter</option>
              <option value="openai_compatible">OpenAI-Compatible</option>
              <option value="mock">Mock Provider</option>
            </select>

            {/* Status Filter */}
            <select
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setCursor(undefined);
              }}
              className="rounded-md border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-1.5 text-xs text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
            >
              <option value="">All Statuses</option>
              <option value="success">Success (200)</option>
              <option value="error">Error (4xx / 5xx)</option>
            </select>
          </div>

          {/* Toggle Pills & Clear Filters */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-[var(--border)] text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  setCacheHitOnly(!cacheHitOnly);
                  setCursor(undefined);
                }}
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  cacheHitOnly
                    ? "bg-[var(--accent)] text-white"
                    : "bg-[var(--surface-raised)] border border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--text)]"
                }`}
              >
                <Zap className="h-3 w-3" />
                <span>Cache Hits Only</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setFallbackOnly(!fallbackOnly);
                  setCursor(undefined);
                }}
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  fallbackOnly
                    ? "bg-[var(--accent)] text-white"
                    : "bg-[var(--surface-raised)] border border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--text)]"
                }`}
              >
                <AlertTriangle className="h-3 w-3" />
                <span>Fallbacks Only</span>
              </button>
            </div>

            {(projectId || provider || status || cacheHitOnly || fallbackOnly || searchTerm) && (
              <button
                type="button"
                onClick={handleResetFilters}
                className="text-xs text-[var(--accent)] hover:underline"
              >
                Reset filters
              </button>
            )}
          </div>
        </div>

        {/* Error State */}
        {isError && (
          <ErrorState
            title="Failed to load requests"
            message={
              error instanceof Error
                ? error.message
                : "Could not fetch requests from gateway."
            }
            onRetry={() => refetch()}
          />
        )}

        {/* Loading State */}
        {isLoading && (
          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-12 animate-pulse rounded bg-[var(--muted)]/50" />
            ))}
          </div>
        )}

        {/* Empty State */}
        {!isLoading && (!requestsData || requestsData.items.length === 0) && (
          <EmptyState
            title="No matching requests found"
            description="Adjust your filters, search term, or seed demo data to inspect requests."
            icon={<Filter className="h-6 w-6" />}
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

        {/* Requests Table */}
        {!isLoading && requestsData && requestsData.items.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-[var(--border)] bg-[var(--surface)] shadow-xs">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-[var(--border)] bg-[var(--surface-raised)] text-[var(--text-muted)]">
                <tr>
                  <th className="py-3 px-4 font-medium">Status</th>
                  <th className="py-3 px-4 font-medium">Request ID / Time</th>
                  <th className="py-3 px-4 font-medium">Model Used</th>
                  <th className="py-3 px-4 font-medium">Tokens</th>
                  <th className="py-3 px-4 font-medium">Latency</th>
                  <th className="py-3 px-4 font-medium">Cost / Savings</th>
                  <th className="py-3 px-4 font-medium text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)] text-[var(--text)]">
                {requestsData.items.map((r) => {
                  const isOk = r.http_status === 200;
                  return (
                    <tr
                      key={r.id}
                      onClick={() => setSelectedRequestId(r.id)}
                      className="cursor-pointer hover:bg-[var(--surface-raised)]/60 transition-colors"
                    >
                      {/* Status */}
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <span
                            className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold font-mono ${
                              isOk
                                ? "bg-[var(--success)]/10 text-[var(--success)]"
                                : "bg-[var(--danger)]/10 text-[var(--danger)]"
                            }`}
                          >
                            {r.http_status}
                          </span>
                        </div>
                      </td>

                      {/* Request ID / Time */}
                      <td className="py-3 px-4">
                        <span className="font-mono text-xs text-[var(--text)]">
                          {r.id.slice(0, 14)}...
                        </span>
                        <div className="flex items-center gap-1.5 text-[11px] text-[var(--text-muted)] font-mono mt-0.5">
                          <span>{new Date(r.created_at).toLocaleTimeString()}</span>
                          {r.user_tag && (
                            <>
                              <span>•</span>
                              <span className="text-[var(--accent)] truncate max-w-[120px]">
                                {r.user_tag}
                              </span>
                            </>
                          )}
                        </div>
                      </td>

                      {/* Model Used & Badges */}
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1.5 font-mono text-[11px] font-medium text-[var(--text)]">
                          <span>{r.model_used}</span>
                        </div>
                        <div className="flex items-center gap-1.5 mt-1">
                          <span className="text-[10px] text-[var(--text-muted)] capitalize">
                            {r.provider}
                          </span>
                          {r.cache_hit && (
                            <span className="rounded bg-[var(--accent)]/10 px-1 py-0.2 text-[9px] font-semibold text-[var(--accent)]">
                              CACHED
                            </span>
                          )}
                          {r.fallback_used && (
                            <span className="rounded bg-[var(--warning)]/10 px-1 py-0.2 text-[9px] font-semibold text-[var(--warning)]">
                              FALLBACK
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Tokens */}
                      <td className="py-3 px-4 tabular-nums">
                        <span className="font-semibold text-[var(--text)]">
                          {formatTokens(r.input_tokens + r.output_tokens)}
                        </span>
                        <p className="text-[11px] text-[var(--text-muted)]">
                          {formatTokens(r.input_tokens)} / {formatTokens(r.output_tokens)}
                        </p>
                      </td>

                      {/* Latency */}
                      <td className="py-3 px-4 tabular-nums">
                        <span className="font-medium text-[var(--text)]">
                          {formatLatency(r.latency_ms)}
                        </span>
                        {r.ttft_ms !== null && (
                          <p className="text-[11px] text-[var(--text-muted)]">
                            {formatLatency(r.ttft_ms)} ttft
                          </p>
                        )}
                      </td>

                      {/* Cost / Savings */}
                      <td className="py-3 px-4 tabular-nums">
                        <span className="font-semibold text-[var(--text)]">
                          {formatMicroUsd(r.cost_micro_usd)}
                        </span>
                        {r.saved_micro_usd > 0 && (
                          <p className="text-[11px] text-[var(--success)] font-medium">
                            +{formatMicroUsd(r.saved_micro_usd)}
                          </p>
                        )}
                      </td>

                      {/* Arrow Action */}
                      <td className="py-3 px-4 text-right">
                        <span className="inline-flex items-center gap-1 text-[var(--text-muted)] group-hover:text-[var(--text)]">
                          <ArrowRight className="h-4 w-4" />
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {/* Cursor Pagination Footer */}
            <div className="flex items-center justify-between border-t border-[var(--border)] bg-[var(--surface-raised)] px-4 py-3 text-xs text-[var(--text-muted)]">
              <span>Showing up to 25 items per page</span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handlePrevPage}
                  disabled={cursorStack.length === 0}
                  className="rounded border border-[var(--border)] bg-[var(--surface)] px-3 py-1 font-medium text-[var(--text)] disabled:opacity-30 disabled:cursor-not-allowed hover:bg-[var(--muted)] transition-colors"
                >
                  Previous
                </button>
                <button
                  type="button"
                  onClick={handleNextPage}
                  disabled={!requestsData.has_more || !requestsData.next_cursor}
                  className="rounded border border-[var(--border)] bg-[var(--surface)] px-3 py-1 font-medium text-[var(--text)] disabled:opacity-30 disabled:cursor-not-allowed hover:bg-[var(--muted)] transition-colors"
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Request Detail Sheet / Drawer */}
        <RequestDetailSheet
          requestId={selectedRequestId}
          onClose={() => setSelectedRequestId(null)}
        />
      </div>
    </AppShell>
  );
}
