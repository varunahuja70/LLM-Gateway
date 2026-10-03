"use client";

import { use, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  CheckCircle,
  Clock,
  Coins,
  Database,
  Key,
  Plus,
  RotateCcw,
  Save,
  Trash2,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { CallsChart } from "@/components/charts/CallsChart";
import { SpendChart } from "@/components/charts/SpendChart";
import { FallbackChainEditor } from "@/components/projects/FallbackChainEditor";
import { BudgetBar } from "@/components/shared/BudgetBar";
import { CodeSnippet } from "@/components/shared/CodeSnippet";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { DateRangePicker, DateRangePreset } from "@/components/shared/DateRangePicker";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { KpiCard } from "@/components/shared/KpiCard";
import { SecretRevealDialog } from "@/components/shared/SecretRevealDialog";
import {
  CreatedGatewayKey,
  FallbackTarget,
  ProjectConfig,
} from "@/lib/api-types";
import {
  formatLatency,
  formatMicroUsd,
  formatPercent,
  formatTokens,
} from "@/lib/formatters";
import {
  useArchiveProject,
  useCreateProjectKey,
  useDeleteProjectData,
  useProject,
  useProjectConfig,
  useProjectKeys,
  useProjectStats,
  useRequests,
  useRevokeProjectKey,
  useRotateProjectKey,
  useTimeseriesStats,
  useUpdateProjectConfig,
} from "@/lib/queries";

type TabType = "usage" | "requests" | "keys" | "config" | "quickstart";

export default function ProjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const resolvedParams = use(params);
  const projectId = resolvedParams.id;
  const router = useRouter();

  const [activeTab, setActiveTab] = useState<TabType>("usage");
  const [datePreset, setDatePreset] = useState<DateRangePreset>("7d");
  const now = useMemo(() => new Date(), []);
  const initialFrom = useMemo(
    () => new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString(),
    [now]
  );
  const [from, setFrom] = useState<string | undefined>(initialFrom);
  const [to, setTo] = useState<string | undefined>(now.toISOString());

  // Modal / Dialog states
  const [revealedKey, setRevealedKey] = useState<CreatedGatewayKey | null>(null);
  const [isCreateKeyOpen, setIsCreateKeyOpen] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [keyToRevoke, setKeyToRevoke] = useState<string | null>(null);
  const [keyToRotate, setKeyToRotate] = useState<string | null>(null);
  const [isDeleteDataOpen, setIsDeleteDataOpen] = useState(false);
  const [isArchiveProjectOpen, setIsArchiveProjectOpen] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Queries
  const { data: project, isLoading: isProjectLoading, isError: isProjectError, error: projectError } = useProject(projectId);
  const { data: config, refetch: refetchConfig } = useProjectConfig(projectId);
  const { data: keys, isLoading: isKeysLoading } = useProjectKeys(projectId);
  const { data: stats, isLoading: isStatsLoading } = useProjectStats(projectId, from, to);
  const { data: timeseries, isLoading: isTimeseriesLoading } = useTimeseriesStats(
    from,
    to,
    datePreset === "24h" ? "hour" : "day",
    projectId
  );
  const { data: recentRequests, isLoading: isRequestsLoading } = useRequests({
    project_id: projectId,
    limit: 10,
  });

  // Mutations
  const updateConfigMutation = useUpdateProjectConfig(projectId);
  const createKeyMutation = useCreateProjectKey(projectId);
  const revokeKeyMutation = useRevokeProjectKey(projectId);
  const rotateKeyMutation = useRotateProjectKey(projectId);
  const deleteDataMutation = useDeleteProjectData(projectId);
  const archiveProjectMutation = useArchiveProject(projectId);

  // Form state for config tab
  const [formConfig, setFormConfig] = useState<Partial<ProjectConfig>>({});
  const currentConfig: ProjectConfig | undefined = config ? { ...config, ...formConfig } : undefined;

  const handleDateChange = (preset: DateRangePreset, newFrom?: string, newTo?: string) => {
    setDatePreset(preset);
    setFrom(newFrom);
    setTo(newTo);
  };

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKeyName.trim() || createKeyMutation.isPending) return;

    try {
      const created = await createKeyMutation.mutateAsync({
        name: newKeyName.trim(),
      });
      setNewKeyName("");
      setIsCreateKeyOpen(false);
      setRevealedKey(created);
    } catch {
      // handled
    }
  };

  const handleRotateKey = async () => {
    if (!keyToRotate || rotateKeyMutation.isPending) return;
    try {
      const rotated = await rotateKeyMutation.mutateAsync(keyToRotate);
      setKeyToRotate(null);
      setRevealedKey(rotated);
    } catch {
      // handled
    }
  };

  const handleRevokeKey = async () => {
    if (!keyToRevoke || revokeKeyMutation.isPending) return;
    try {
      await revokeKeyMutation.mutateAsync(keyToRevoke);
      setKeyToRevoke(null);
    } catch {
      // handled
    }
  };

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentConfig || updateConfigMutation.isPending) return;

    try {
      await updateConfigMutation.mutateAsync(currentConfig);
      setSaveSuccess(true);
      setFormConfig({});
      setTimeout(() => setSaveSuccess(false), 3000);
      refetchConfig();
    } catch {
      // handled
    }
  };

  const handleDeleteData = async () => {
    try {
      await deleteDataMutation.mutateAsync();
      setIsDeleteDataOpen(false);
    } catch {
      // handled
    }
  };

  const handleArchiveProject = async () => {
    try {
      await archiveProjectMutation.mutateAsync();
      router.push("/projects");
    } catch {
      // handled
    }
  };

  if (isProjectLoading) {
    return (
      <AppShell>
        <div className="space-y-4">
          <div className="h-8 w-48 animate-pulse rounded bg-[var(--muted)]" />
          <div className="h-12 w-full animate-pulse rounded bg-[var(--muted)]/50" />
          <div className="h-64 w-full animate-pulse rounded bg-[var(--muted)]/30" />
        </div>
      </AppShell>
    );
  }

  if (isProjectError || !project) {
    return (
      <AppShell>
        <ErrorState
          title="Project not found"
          message={
            projectError instanceof Error
              ? projectError.message
              : "The requested project could not be found."
          }
          onRetry={() => router.push("/projects")}
        />
      </AppShell>
    );
  }

  // Active key or placeholder
  const activeKeyPrefix = keys && keys.length > 0 ? `${keys[0].prefix}...` : "lgw_YOUR_KEY";

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Breadcrumb & Navigation */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-3">
            <Link
              href="/projects"
              className="rounded-md border border-[var(--border)] bg-[var(--surface)] p-2 text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-raised)] transition-colors"
              aria-label="Back to projects"
            >
              <ArrowLeft className="h-4 w-4" />
            </Link>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold tracking-tight text-[var(--text)]">
                  {project.name}
                </h1>
                {project.archived_at && (
                  <span className="rounded bg-[var(--danger)]/10 px-2 py-0.5 text-[10px] font-semibold text-[var(--danger)]">
                    Archived
                  </span>
                )}
              </div>
              <p className="font-mono text-xs text-[var(--text-muted)] mt-0.5">
                {project.slug}
              </p>
            </div>
          </div>

          {activeTab === "usage" && (
            <DateRangePicker
              value={datePreset}
              onChange={handleDateChange}
              from={from}
              to={to}
            />
          )}
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-[var(--border)] overflow-x-auto">
          {(
            [
              { id: "usage", label: "Usage" },
              { id: "requests", label: "Requests" },
              { id: "keys", label: `Keys (${keys?.length || 0})` },
              { id: "config", label: "Config" },
              { id: "quickstart", label: "Quick Start" },
            ] as { id: TabType; label: string }[]
          ).map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`border-b-2 px-4 py-2.5 text-xs font-medium whitespace-nowrap transition-colors ${
                activeTab === tab.id
                  ? "border-[var(--accent)] text-[var(--accent)]"
                  : "border-transparent text-[var(--text-muted)] hover:text-[var(--text)] hover:border-[var(--border)]"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* TAB 1: USAGE */}
        {activeTab === "usage" && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
              <KpiCard
                title="Total Spend"
                value={formatMicroUsd(stats?.overview.total_cost_micro_usd ?? 0)}
                subtitle="Project spend"
                icon={<Coins className="h-4 w-4" />}
                loading={isStatsLoading}
              />
              <KpiCard
                title="Total Calls"
                value={formatTokens(stats?.overview.total_requests ?? 0)}
                subtitle="Completions"
                icon={<Activity className="h-4 w-4" />}
                loading={isStatsLoading}
              />
              <KpiCard
                title="Error Rate"
                value={formatPercent(stats?.overview.error_rate ?? 0)}
                subtitle="Errors & rejects"
                icon={<AlertTriangle className="h-4 w-4" />}
                loading={isStatsLoading}
              />
              <KpiCard
                title="p95 Latency"
                value={formatLatency(stats?.overview.avg_latency_ms ?? null)}
                subtitle="Average latency"
                icon={<Clock className="h-4 w-4" />}
                loading={isStatsLoading}
              />
              <KpiCard
                title="Cache Savings"
                value={formatMicroUsd(stats?.overview.saved_micro_usd ?? 0)}
                subtitle={`${formatPercent(stats?.overview.cache_hit_rate ?? 0)} hit rate`}
                icon={<Database className="h-4 w-4" />}
                loading={isStatsLoading}
              />
            </div>

            {/* Monthly Budget Tracker Bar */}
            {config?.monthly_budget_micro_usd && (
              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 shadow-xs">
                <span className="text-xs font-semibold text-[var(--text)] block mb-2">
                  Monthly Budget Limit
                </span>
                <BudgetBar
                  spentMicroUsd={stats?.overview.total_cost_micro_usd || 0}
                  budgetMicroUsd={config.monthly_budget_micro_usd}
                />
              </div>
            )}

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <SpendChart
                data={timeseries?.data || []}
                loading={isTimeseriesLoading}
              />
              <CallsChart
                data={timeseries?.data || []}
                loading={isTimeseriesLoading}
              />
            </div>
          </div>
        )}

        {/* TAB 2: REQUESTS */}
        {activeTab === "requests" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-[var(--text)]">Recent Requests</h3>
                <p className="text-xs text-[var(--text-muted)]">
                  Latest 10 requests routed through this project.
                </p>
              </div>
              <Link
                href={`/requests?project_id=${projectId}`}
                className="rounded-md border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-1.5 text-xs font-medium text-[var(--text)] hover:bg-[var(--muted)] transition-colors"
              >
                Open in Request Explorer
              </Link>
            </div>

            {isRequestsLoading ? (
              <div className="space-y-3">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-12 animate-pulse rounded bg-[var(--muted)]/50" />
                ))}
              </div>
            ) : !recentRequests || recentRequests.items.length === 0 ? (
              <EmptyState
                title="No requests yet"
                description="Make your first API request using this project's gateway key to view logs."
                action={{
                  label: "View Quick Start Guide",
                  onClick: () => setActiveTab("quickstart"),
                }}
              />
            ) : (
              <div className="overflow-x-auto rounded-lg border border-[var(--border)] bg-[var(--surface)] shadow-xs">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-[var(--border)] bg-[var(--surface-raised)] text-[var(--text-muted)]">
                    <tr>
                      <th className="py-2.5 px-3 font-medium">Status</th>
                      <th className="py-2.5 px-3 font-medium">Model</th>
                      <th className="py-2.5 px-3 font-medium">Tokens</th>
                      <th className="py-2.5 px-3 font-medium">Latency</th>
                      <th className="py-2.5 px-3 font-medium">Cost</th>
                      <th className="py-2.5 px-3 font-medium">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)] text-[var(--text)]">
                    {recentRequests.items.map((r) => (
                      <tr key={r.id} className="hover:bg-[var(--surface-raised)]/50">
                        <td className="py-2.5 px-3 font-mono">
                          <span
                            className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                              r.http_status === 200
                                ? "bg-[var(--success)]/10 text-[var(--success)]"
                                : "bg-[var(--danger)]/10 text-[var(--danger)]"
                            }`}
                          >
                            {r.http_status}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-mono text-[11px]">
                          {r.model_used}
                        </td>
                        <td className="py-2.5 px-3 tabular-nums">
                          {formatTokens(r.input_tokens + r.output_tokens)}
                        </td>
                        <td className="py-2.5 px-3 tabular-nums">
                          {formatLatency(r.latency_ms)}
                        </td>
                        <td className="py-2.5 px-3 tabular-nums">
                          {formatMicroUsd(r.cost_micro_usd)}
                        </td>
                        <td className="py-2.5 px-3 font-mono text-[11px] text-[var(--text-muted)]">
                          {new Date(r.created_at).toLocaleTimeString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* TAB 3: KEYS */}
        {activeTab === "keys" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-[var(--text)]">Gateway API Keys</h3>
                <p className="text-xs text-[var(--text-muted)]">
                  Authenticate your client applications with the LLM Gateway API.
                </p>
              </div>
              <button
                onClick={() => setIsCreateKeyOpen(true)}
                className="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-3 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-[var(--accent-hover)] transition-colors"
              >
                <Plus className="h-3.5 w-3.5" />
                <span>Create Key</span>
              </button>
            </div>

            {isKeysLoading ? (
              <div className="space-y-3">
                {[1, 2].map((i) => (
                  <div key={i} className="h-16 animate-pulse rounded bg-[var(--muted)]/50" />
                ))}
              </div>
            ) : !keys || keys.length === 0 ? (
              <EmptyState
                title="No gateway keys"
                description="Create an API key to begin routing requests through this project."
                icon={<Key className="h-6 w-6" />}
                action={{
                  label: "Create First Key",
                  onClick: () => setIsCreateKeyOpen(true),
                }}
              />
            ) : (
              <div className="overflow-x-auto rounded-lg border border-[var(--border)] bg-[var(--surface)] shadow-xs">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-[var(--border)] bg-[var(--surface-raised)] text-[var(--text-muted)]">
                    <tr>
                      <th className="py-3 px-4 font-medium">Name</th>
                      <th className="py-3 px-4 font-medium">Key Prefix</th>
                      <th className="py-3 px-4 font-medium">Status</th>
                      <th className="py-3 px-4 font-medium">Last Used</th>
                      <th className="py-3 px-4 font-medium">Created</th>
                      <th className="py-3 px-4 font-medium text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)] text-[var(--text)]">
                    {keys.map((k) => {
                      const isRevoked = !!k.revoked_at;
                      return (
                        <tr key={k.id} className="hover:bg-[var(--surface-raised)]/50">
                          <td className="py-3 px-4 font-medium text-[var(--text)]">
                            {k.name}
                          </td>
                          <td className="py-3 px-4 font-mono text-[11px] text-[var(--text)]">
                            {k.prefix}...
                          </td>
                          <td className="py-3 px-4">
                            <span
                              className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                                isRevoked
                                  ? "bg-[var(--danger)]/10 text-[var(--danger)]"
                                  : "bg-[var(--success)]/10 text-[var(--success)]"
                              }`}
                            >
                              {isRevoked ? "Revoked" : "Active"}
                            </span>
                          </td>
                          <td className="py-3 px-4 font-mono text-[11px] text-[var(--text-muted)]">
                            {k.last_used_at
                              ? new Date(k.last_used_at).toLocaleDateString()
                              : "Never"}
                          </td>
                          <td className="py-3 px-4 font-mono text-[11px] text-[var(--text-muted)]">
                            {new Date(k.created_at).toLocaleDateString()}
                          </td>
                          <td className="py-3 px-4 text-right">
                            {!isRevoked && (
                              <div className="flex items-center justify-end gap-1.5">
                                <button
                                  onClick={() => setKeyToRotate(k.id)}
                                  className="inline-flex items-center gap-1 rounded border border-[var(--border)] bg-[var(--surface-raised)] px-2 py-1 text-xs text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--muted)] transition-colors"
                                  title="Rotate key (invalidates current key)"
                                >
                                  <RotateCcw className="h-3 w-3" />
                                  <span>Rotate</span>
                                </button>
                                <button
                                  onClick={() => setKeyToRevoke(k.id)}
                                  className="inline-flex items-center gap-1 rounded border border-[var(--border)] bg-[var(--surface-raised)] px-2 py-1 text-xs text-[var(--danger)] hover:bg-[var(--danger)]/10 transition-colors"
                                  title="Revoke key permanently"
                                >
                                  <Trash2 className="h-3 w-3" />
                                  <span>Revoke</span>
                                </button>
                              </div>
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
        )}

        {/* TAB 4: CONFIG */}
        {activeTab === "config" && currentConfig && (
          <form onSubmit={handleSaveConfig} className="space-y-6 max-w-4xl">
            {saveSuccess && (
              <div className="flex items-center gap-2 rounded-lg bg-[var(--success)]/10 p-3 text-xs text-[var(--success)]">
                <CheckCircle className="h-4 w-4 shrink-0" />
                <span>Project configuration saved successfully.</span>
              </div>
            )}

            {/* Budgets & Limits */}
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xs space-y-4">
              <h3 className="text-sm font-semibold text-[var(--text)]">Budgets & Limits</h3>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">
                    Monthly Budget (USD)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={
                      currentConfig.monthly_budget_micro_usd !== null &&
                      currentConfig.monthly_budget_micro_usd !== undefined
                        ? currentConfig.monthly_budget_micro_usd / 1_000_000
                        : ""
                    }
                    onChange={(e) =>
                      setFormConfig((prev) => ({
                        ...prev,
                        monthly_budget_micro_usd: e.target.value
                          ? Math.round(parseFloat(e.target.value) * 1_000_000)
                          : null,
                      }))
                    }
                    placeholder="Unlimited"
                    className="w-full rounded-md border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-1.5 text-xs text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">
                    Daily Budget (USD)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={
                      currentConfig.daily_budget_micro_usd !== null &&
                      currentConfig.daily_budget_micro_usd !== undefined
                        ? currentConfig.daily_budget_micro_usd / 1_000_000
                        : ""
                    }
                    onChange={(e) =>
                      setFormConfig((prev) => ({
                        ...prev,
                        daily_budget_micro_usd: e.target.value
                          ? Math.round(parseFloat(e.target.value) * 1_000_000)
                          : null,
                      }))
                    }
                    placeholder="Unlimited"
                    className="w-full rounded-md border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-1.5 text-xs text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">
                    RPM Rate Limit (Requests per minute)
                  </label>
                  <input
                    type="number"
                    min="1"
                    value={currentConfig.rpm_limit ?? ""}
                    onChange={(e) =>
                      setFormConfig((prev) => ({
                        ...prev,
                        rpm_limit: e.target.value ? parseInt(e.target.value, 10) : null,
                      }))
                    }
                    placeholder="No rate limit"
                    className="w-full rounded-md border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-1.5 text-xs text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">
                    Request Timeout (Seconds)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="300"
                    value={currentConfig.request_timeout_s ?? 60}
                    onChange={(e) =>
                      setFormConfig((prev) => ({
                        ...prev,
                        request_timeout_s: parseInt(e.target.value, 10) || 60,
                      }))
                    }
                    className="w-full rounded-md border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-1.5 text-xs text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
                  />
                </div>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="block_at_limit"
                  checked={currentConfig.block_at_limit ?? false}
                  onChange={(e) =>
                    setFormConfig((prev) => ({ ...prev, block_at_limit: e.target.checked }))
                  }
                  className="rounded border-[var(--border)] text-[var(--accent)] focus:ring-[var(--accent)]"
                />
                <label htmlFor="block_at_limit" className="text-xs text-[var(--text)] font-medium">
                  Block requests immediately when budget limit is reached (HTTP 429)
                </label>
              </div>
            </div>

            {/* Fallback Chain Editor */}
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xs">
              <h3 className="text-sm font-semibold text-[var(--text)] mb-3">
                Model Fallback Chain
              </h3>
              <p className="text-xs text-[var(--text-muted)] mb-4">
                If the requested model times out, returns 429 or 5xx, the gateway automatically retries with these models in order.
              </p>
              <FallbackChainEditor
                chain={(currentConfig.fallback_chain || []).map((t) => `${t.provider}/${t.model}`)}
                onChange={(newChain) => {
                  const mapped: FallbackTarget[] = newChain.map((str) => {
                    const [provider, ...rest] = str.split("/");
                    return { provider, model: rest.join("/") };
                  });
                  setFormConfig((prev) => ({ ...prev, fallback_chain: mapped }));
                }}
              />
            </div>

            {/* Caching & Webhook */}
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xs space-y-4">
              <h3 className="text-sm font-semibold text-[var(--text)]">Caching & Webhooks</h3>

              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs font-medium text-[var(--text)]">Enable Exact Cache</span>
                  <p className="text-[11px] text-[var(--text-muted)]">
                    Identical completions return cached answers instantly with zero spend.
                  </p>
                </div>
                <input
                  type="checkbox"
                  checked={currentConfig.cache_enabled ?? false}
                  onChange={(e) =>
                    setFormConfig((prev) => ({ ...prev, cache_enabled: e.target.checked }))
                  }
                  className="rounded border-[var(--border)] text-[var(--accent)]"
                />
              </div>

              {currentConfig.cache_enabled && (
                <div className="pt-1">
                  <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">
                    Cache TTL (Seconds)
                  </label>
                  <input
                    type="number"
                    min="10"
                    value={currentConfig.cache_ttl_s ?? 3600}
                    onChange={(e) =>
                      setFormConfig((prev) => ({
                        ...prev,
                        cache_ttl_s: parseInt(e.target.value, 10) || 3600,
                      }))
                    }
                    className="w-48 rounded-md border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-1.5 text-xs text-[var(--text)]"
                  />
                </div>
              )}

              <div>
                <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">
                  Budget Alert Webhook URL
                </label>
                <input
                  type="url"
                  value={currentConfig.webhook_url ?? ""}
                  onChange={(e) =>
                    setFormConfig((prev) => ({
                      ...prev,
                      webhook_url: e.target.value.trim() || null,
                    }))
                  }
                  placeholder="https://your-domain.com/api/gateway-alerts"
                  className="w-full rounded-md border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-1.5 text-xs text-[var(--text)]"
                />
              </div>
            </div>

            {/* Content Logging Warning & Setting */}
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xs space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs font-medium text-[var(--text)]">Log Prompt & Response Bodies</span>
                  <p className="text-[11px] text-[var(--text-muted)]">
                    Store raw prompt and completion contents in the database for debugging and evaluation.
                  </p>
                </div>
                <input
                  type="checkbox"
                  checked={currentConfig.log_content ?? false}
                  onChange={(e) =>
                    setFormConfig((prev) => ({ ...prev, log_content: e.target.checked }))
                  }
                  className="rounded border-[var(--border)] text-[var(--accent)]"
                />
              </div>

              {currentConfig.log_content && (
                <div className="flex items-start gap-2 rounded-md bg-[var(--warning)]/10 border border-[var(--warning)]/30 p-3 text-xs text-[var(--warning)]">
                  <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>
                    <strong>Privacy Warning:</strong> Prompts and completions may contain Personally Identifiable Information (PII) or confidential secrets. Stored contents will follow your project retention period.
                  </span>
                </div>
              )}
            </div>

            {/* Save Button */}
            <div className="flex justify-end gap-3 pt-2">
              <button
                type="submit"
                disabled={updateConfigMutation.isPending}
                className="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-[var(--accent-hover)] transition-colors disabled:opacity-50"
              >
                <Save className="h-3.5 w-3.5" />
                <span>{updateConfigMutation.isPending ? "Saving..." : "Save Configuration"}</span>
              </button>
            </div>

            {/* Danger Zone */}
            <div className="rounded-lg border border-[var(--danger)]/30 bg-[var(--danger)]/5 p-5 space-y-4 mt-8">
              <h3 className="text-sm font-semibold text-[var(--danger)]">Danger Zone</h3>
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-1">
                <div>
                  <span className="text-xs font-medium text-[var(--text)]">Delete Project Data</span>
                  <p className="text-[11px] text-[var(--text-muted)]">
                    Purge all logged requests, metrics and stored contents for this project immediately.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setIsDeleteDataOpen(true)}
                  className="inline-flex items-center gap-1 rounded-md border border-[var(--danger)]/40 px-3 py-1.5 text-xs font-medium text-[var(--danger)] hover:bg-[var(--danger)]/10 transition-colors shrink-0"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  <span>Delete Data</span>
                </button>
              </div>

              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-2 border-t border-[var(--border)]">
                <div>
                  <span className="text-xs font-medium text-[var(--text)]">Archive Project</span>
                  <p className="text-[11px] text-[var(--text-muted)]">
                    Disable all gateway keys and halt request processing for this project.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setIsArchiveProjectOpen(true)}
                  className="inline-flex items-center gap-1 rounded-md bg-[var(--danger)] px-3 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-[var(--danger)]/90 transition-colors shrink-0"
                >
                  <span>Archive Project</span>
                </button>
              </div>
            </div>
          </form>
        )}

        {/* TAB 5: QUICK START */}
        {activeTab === "quickstart" && (
          <div className="space-y-6 max-w-4xl">
            <div>
              <h3 className="text-sm font-semibold text-[var(--text)]">Connect to LLM Gateway</h3>
              <p className="text-xs text-[var(--text-muted)] mt-0.5">
                Use your standard OpenAI SDK or HTTP client by pointing the base URL to your gateway.
              </p>
            </div>

            <div className="space-y-4">
              <div>
                <span className="text-xs font-semibold text-[var(--text)] mb-1 block">
                  1. cURL Example
                </span>
                <CodeSnippet
                  language="bash"
                  code={`curl http://localhost:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${activeKeyPrefix}" \\
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello LLM Gateway!"}]
  }'`}
                />
              </div>

              <div>
                <span className="text-xs font-semibold text-[var(--text)] mb-1 block">
                  2. Python (OpenAI SDK)
                </span>
                <CodeSnippet
                  language="python"
                  code={`from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="${activeKeyPrefix}",
)

response = client.chat.completions.create(
    model="openai/gpt-4o-mini",
    messages=[{"role": "user", "content": "Explain quantum computing in one sentence."}],
)

print(response.choices[0].message.content)`}
                />
              </div>

              <div>
                <span className="text-xs font-semibold text-[var(--text)] mb-1 block">
                  3. TypeScript / JavaScript (OpenAI SDK)
                </span>
                <CodeSnippet
                  language="typescript"
                  code={`import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://localhost:8000/v1",
  apiKey: "${activeKeyPrefix}",
});

async function main() {
  const completion = await client.chat.completions.create({
    model: "openai/gpt-4o-mini",
    messages: [{ role: "user", content: "Hello!" }],
  });

  console.log(completion.choices[0].message.content);
}

main();`}
                />
              </div>
            </div>
          </div>
        )}

        {/* Create Key Modal */}
        {isCreateKeyOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
            <div className="w-full max-w-sm rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] p-6 shadow-xl animate-in fade-in zoom-in-95">
              <h2 className="text-base font-bold text-[var(--text)]">Create Gateway Key</h2>
              <p className="mt-1 text-xs text-[var(--text-muted)]">
                Create a new credential to allow clients to send requests.
              </p>

              <form onSubmit={handleCreateKey} className="mt-4 space-y-4">
                <div>
                  <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">
                    Key Name
                  </label>
                  <input
                    type="text"
                    required
                    value={newKeyName}
                    onChange={(e) => setNewKeyName(e.target.value)}
                    placeholder="e.g. backend-server-key"
                    className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-xs text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
                    autoFocus
                  />
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsCreateKeyOpen(false)}
                    className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs text-[var(--text-muted)] hover:text-[var(--text)]"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={!newKeyName.trim() || createKeyMutation.isPending}
                    className="rounded-md bg-[var(--accent)] px-4 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-[var(--accent-hover)] disabled:opacity-50"
                  >
                    {createKeyMutation.isPending ? "Generating..." : "Generate Key"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Reveal Key Dialog (Shown Once) */}
        {revealedKey && (
          <SecretRevealDialog
            isOpen={!!revealedKey}
            title="Gateway API Key Created"
            description="Copy and save your new gateway API key. It will never be shown again!"
            secret={revealedKey.key}
            onClose={() => setRevealedKey(null)}
          />
        )}

        {/* Revoke Key Confirmation */}
        <ConfirmDialog
          isOpen={!!keyToRevoke}
          title="Revoke Gateway Key"
          description="Are you sure you want to revoke this key? Any application using this key will immediately be blocked from sending requests."
          confirmLabel="Revoke Key"
          destructive={true}
          onConfirm={handleRevokeKey}
          onClose={() => setKeyToRevoke(null)}
        />

        {/* Rotate Key Confirmation */}
        <ConfirmDialog
          isOpen={!!keyToRotate}
          title="Rotate Gateway Key"
          description="Rotating this key will immediately revoke the current key and issue a new secret token. Applications using the old key will fail until updated."
          confirmLabel="Rotate Key"
          destructive={true}
          onConfirm={handleRotateKey}
          onClose={() => setKeyToRotate(null)}
        />

        {/* Delete Data Confirmation */}
        <ConfirmDialog
          isOpen={isDeleteDataOpen}
          title="Delete Project Data"
          description="This will permanently delete all requests, logs and stored contents for this project. Historical metrics will be cleared."
          confirmLabel="Delete All Data"
          destructive={true}
          onConfirm={handleDeleteData}
          onClose={() => setIsDeleteDataOpen(false)}
        />

        {/* Archive Project Confirmation */}
        <ConfirmDialog
          isOpen={isArchiveProjectOpen}
          title="Archive Project"
          description={`Are you sure you want to archive "${project.name}"? All keys will be deactivated.`}
          confirmLabel="Archive Project"
          destructive={true}
          confirmText={project.name}
          onConfirm={handleArchiveProject}
          onClose={() => setIsArchiveProjectOpen(false)}
        />
      </div>
    </AppShell>
  );
}
