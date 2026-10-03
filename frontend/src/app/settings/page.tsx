"use client";

import { useState } from "react";
import {
  AlertCircle,
  CheckCircle,
  ExternalLink,
  Info,
  Lock,
  Plus,
  Power,
  RefreshCw,
  Save,
  Server,
  Sparkles,
  Tag,
  Trash2,
  Upload,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { EmptyState } from "@/components/shared/EmptyState";
import { ModelPrice, ProviderCredential } from "@/lib/api-types";
import { formatMicroUsd } from "@/lib/formatters";
import {
  useChangePassword,
  useClearDemo,
  useCreatePrice,
  useCreateProvider,
  useDeleteProvider,
  useImportPrices,
  usePrices,
  useProviders,
  useSeedDemo,
  useSettings,
  useTestProvider,
  useUpdatePrice,
  useUpdateProvider,
  useUpdateSettings,
} from "@/lib/queries";

type SettingsTab = "providers" | "prices" | "retention" | "account" | "about";

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>("providers");

  // Providers state
  const [isAddProviderOpen, setIsAddProviderOpen] = useState(false);
  const [providerType, setProviderType] = useState("openai");
  const [providerName, setProviderName] = useState("");
  const [providerApiKey, setProviderApiKey] = useState("");
  const [providerBaseUrl, setProviderBaseUrl] = useState("");
  const [providerToDelete, setProviderToDelete] = useState<ProviderCredential | null>(null);
  const [testingProviderId, setTestingProviderId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ id: string; success: boolean; message: string } | null>(null);
  const [providerError, setProviderError] = useState<string | null>(null);

  // Prices state
  const [isAddPriceOpen, setIsAddPriceOpen] = useState(false);
  const [isImportPriceOpen, setIsImportPriceOpen] = useState(false);
  const [editingPrice, setEditingPrice] = useState<ModelPrice | null>(null);
  const [priceProvider, setPriceProvider] = useState("openai");
  const [priceModel, setPriceModel] = useState("");
  const [priceInputMtok, setPriceInputMtok] = useState("2.50");
  const [priceOutputMtok, setPriceOutputMtok] = useState("10.00");
  const [priceSourceUrl, setPriceSourceUrl] = useState("https://openai.com/pricing");
  const [importJsonText, setImportJsonText] = useState("");
  const [priceError, setPriceError] = useState<string | null>(null);
  const [priceSuccess, setPriceSuccess] = useState<string | null>(null);

  // Retention state
  const [retentionDaysInput, setRetentionDaysInput] = useState<number | null>(null);
  const [retentionSuccess, setRetentionSuccess] = useState(false);

  // Account state
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);

  // Demo data state
  const [demoActionMessage, setDemoActionMessage] = useState<string | null>(null);

  // Queries
  const { data: providers, isLoading: isProvidersLoading } = useProviders();
  const { data: prices, isLoading: isPricesLoading } = usePrices();
  const { data: settings } = useSettings();

  // Mutations
  const createProviderMutation = useCreateProvider();
  const updateProviderMutation = useUpdateProvider();
  const deleteProviderMutation = useDeleteProvider();
  const testProviderMutation = useTestProvider();
  const createPriceMutation = useCreatePrice();
  const updatePriceMutation = useUpdatePrice(editingPrice?.id || "");
  const importPricesMutation = useImportPrices();
  const updateSettingsMutation = useUpdateSettings();
  const changePasswordMutation = useChangePassword();
  const seedDemoMutation = useSeedDemo();
  const clearDemoMutation = useClearDemo();

  // Handlers for Providers
  const handleCreateProvider = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!providerName.trim() || !providerApiKey.trim() || createProviderMutation.isPending) return;
    setProviderError(null);

    try {
      await createProviderMutation.mutateAsync({
        provider: providerType,
        name: providerName.trim(),
        api_key: providerApiKey.trim(),
        base_url: providerBaseUrl.trim() || null,
      });
      setIsAddProviderOpen(false);
      setProviderName("");
      setProviderApiKey("");
      setProviderBaseUrl("");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setProviderError(err.message);
      } else {
        setProviderError("Failed to save provider credential.");
      }
    }
  };

  const handleTestProvider = async (p: ProviderCredential) => {
    setTestingProviderId(p.id);
    setTestResult(null);
    try {
      const res = await testProviderMutation.mutateAsync(p.id);
      setTestResult({ id: p.id, success: res.success, message: res.message });
    } catch (err: unknown) {
      setTestResult({
        id: p.id,
        success: false,
        message: err instanceof Error ? err.message : "Provider test failed.",
      });
    } finally {
      setTestingProviderId(null);
    }
  };

  const handleToggleProvider = async (p: ProviderCredential) => {
    try {
      // Backend expects is_disabled (inverse of is_enabled)
      await updateProviderMutation.mutateAsync({
        id: p.id,
        is_disabled: p.is_enabled,  // if currently enabled, disable it; and vice versa
      });
    } catch {
      // handled
    }
  };

  const handleDeleteProvider = async () => {
    if (!providerToDelete) return;
    try {
      await deleteProviderMutation.mutateAsync(providerToDelete.id);
      setProviderToDelete(null);
    } catch {
      // handled
    }
  };

  // Handlers for Prices
  const handleSavePrice = async (e: React.FormEvent) => {
    e.preventDefault();
    setPriceError(null);
    setPriceSuccess(null);

    const inputMicro = Math.round(parseFloat(priceInputMtok) * 1_000_000);
    const outputMicro = Math.round(parseFloat(priceOutputMtok) * 1_000_000);

    try {
      if (editingPrice) {
        await updatePriceMutation.mutateAsync({
          input_micro_usd_per_mtok: inputMicro,
          output_micro_usd_per_mtok: outputMicro,
          source_url: priceSourceUrl,
          verified_on: new Date().toISOString().split("T")[0],
        });
        setPriceSuccess(`Updated pricing for ${editingPrice.model}`);
        setEditingPrice(null);
      } else {
        await createPriceMutation.mutateAsync({
          provider: priceProvider,
          model: priceModel.trim(),
          input_micro_usd_per_mtok: inputMicro,
          output_micro_usd_per_mtok: outputMicro,
          source_url: priceSourceUrl,
          verified_on: new Date().toISOString().split("T")[0],
        });
        setPriceSuccess(`Added price for ${priceModel}`);
        setIsAddPriceOpen(false);
        setPriceModel("");
      }
    } catch (err: unknown) {
      setPriceError(err instanceof Error ? err.message : "Failed to save model price.");
    }
  };

  const handleImportPrices = async (e: React.FormEvent) => {
    e.preventDefault();
    setPriceError(null);
    try {
      const parsed = JSON.parse(importJsonText);
      const list = Array.isArray(parsed) ? parsed : parsed.prices;
      if (!Array.isArray(list)) {
        throw new Error("JSON must be an array of prices or have a 'prices' array key.");
      }
      const res = await importPricesMutation.mutateAsync({ prices: list });
      setPriceSuccess(res.message);
      setIsImportPriceOpen(false);
      setImportJsonText("");
    } catch (err: unknown) {
      setPriceError(err instanceof Error ? err.message : "Invalid JSON format for price import.");
    }
  };

  // Handlers for Retention
  const handleSaveRetention = async (e: React.FormEvent) => {
    e.preventDefault();
    const days = retentionDaysInput ?? settings?.retention_days ?? 30;
    try {
      await updateSettingsMutation.mutateAsync({ retention_days: days });
      setRetentionSuccess(true);
      setTimeout(() => setRetentionSuccess(false), 3000);
    } catch {
      // handled
    }
  };

  // Handlers for Account
  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError(null);
    setPasswordSuccess(null);

    if (newPassword.length < 12) {
      setPasswordError("New password must be at least 12 characters long.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("New passwords do not match.");
      return;
    }

    try {
      const res = await changePasswordMutation.mutateAsync({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setPasswordSuccess(res.message);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err: unknown) {
      setPasswordError(err instanceof Error ? err.message : "Failed to change password.");
    }
  };

  return (
    <AppShell>
      <div className="space-y-6 max-w-5xl">
        {/* Header */}
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[var(--text)]">
            Gateway Settings
          </h1>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            Configure upstream AI providers, token price catalogs, data retention, and credentials.
          </p>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-[var(--border)] overflow-x-auto">
          {(
            [
              { id: "providers", label: `Providers (${providers?.length || 0})` },
              { id: "prices", label: `Prices (${prices?.length || 0})` },
              { id: "retention", label: "Data Retention" },
              { id: "account", label: "Owner Account" },
              { id: "about", label: "About" },
            ] as { id: SettingsTab; label: string }[]
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

        {/* TAB 1: PROVIDERS */}
        {activeTab === "providers" && (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-[var(--text)]">
                  Provider API Credentials
                </h2>
                <p className="text-xs text-[var(--text-muted)]">
                  Encrypted at rest with AES-256-GCM. Keys are never logged or returned by the API.
                </p>
              </div>

              <button
                onClick={() => setIsAddProviderOpen(true)}
                className="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-3 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-[var(--accent-hover)] transition-colors self-start sm:self-auto"
              >
                <Plus className="h-3.5 w-3.5" />
                <span>Add Provider Key</span>
              </button>
            </div>

            {testResult && (
              <div
                className={`flex items-center gap-2 rounded-lg p-3 text-xs ${
                  testResult.success
                    ? "bg-[var(--success)]/10 text-[var(--success)]"
                    : "bg-[var(--danger)]/10 text-[var(--danger)]"
                }`}
              >
                {testResult.success ? (
                  <CheckCircle className="h-4 w-4 shrink-0" />
                ) : (
                  <AlertCircle className="h-4 w-4 shrink-0" />
                )}
                <span>{testResult.message}</span>
              </div>
            )}

            {isProvidersLoading ? (
              <div className="space-y-3">
                {[1, 2].map((i) => (
                  <div key={i} className="h-16 animate-pulse rounded bg-[var(--surface)] border border-[var(--border)]" />
                ))}
              </div>
            ) : !providers || providers.length === 0 ? (
              <EmptyState
                title="No provider keys configured"
                description="Add an API key for OpenAI, Anthropic, Gemini, or a self-hosted provider to route requests."
                icon={<Server className="h-6 w-6" />}
                action={{
                  label: "Add First Provider Key",
                  onClick: () => setIsAddProviderOpen(true),
                }}
              />
            ) : (
              <div className="overflow-x-auto rounded-lg border border-[var(--border)] bg-[var(--surface)] shadow-xs">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-[var(--border)] bg-[var(--surface-raised)] text-[var(--text-muted)]">
                    <tr>
                      <th className="py-3 px-4 font-medium">Provider</th>
                      <th className="py-3 px-4 font-medium">Name</th>
                      <th className="py-3 px-4 font-medium">Key Suffix</th>
                      <th className="py-3 px-4 font-medium">Status</th>
                      <th className="py-3 px-4 font-medium text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)] text-[var(--text)]">
                    {providers.map((p) => (
                      <tr key={p.id} className="hover:bg-[var(--surface-raised)]/60 transition-colors">
                        <td className="py-3 px-4">
                          <span className="font-semibold text-[var(--text)] capitalize">
                            {p.provider}
                          </span>
                          {p.base_url && (
                            <p className="font-mono text-[10px] text-[var(--text-muted)] truncate max-w-xs">
                              {p.base_url}
                            </p>
                          )}
                        </td>
                        <td className="py-3 px-4 font-medium text-[var(--text)]">
                          {p.name}
                        </td>
                        <td className="py-3 px-4 font-mono text-[11px] text-[var(--text-muted)]">
                          ••••••••••••{p.key_suffix}
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                              p.is_enabled
                                ? "bg-[var(--success)]/10 text-[var(--success)]"
                                : "bg-[var(--text-muted)]/20 text-[var(--text-muted)]"
                            }`}
                          >
                            {p.is_enabled ? "Enabled" : "Disabled"}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              type="button"
                              onClick={() => handleTestProvider(p)}
                              disabled={testProviderMutation.isPending && testingProviderId === p.id}
                              className="inline-flex items-center gap-1 rounded border border-[var(--border)] bg-[var(--surface-raised)] px-2.5 py-1 text-xs font-medium text-[var(--text)] hover:bg-[var(--muted)] disabled:opacity-50 transition-colors"
                            >
                              <RefreshCw
                                className={`h-3 w-3 ${
                                  testProviderMutation.isPending && testingProviderId === p.id
                                    ? "animate-spin"
                                    : ""
                                }`}
                              />
                              <span>Test</span>
                            </button>

                            <button
                              type="button"
                              onClick={() => handleToggleProvider(p)}
                              className="rounded border border-[var(--border)] bg-[var(--surface-raised)] p-1 text-[var(--text-muted)] hover:text-[var(--text)] transition-colors"
                              title={p.is_enabled ? "Disable provider" : "Enable provider"}
                            >
                              <Power className="h-3.5 w-3.5" />
                            </button>

                            <button
                              type="button"
                              onClick={() => setProviderToDelete(p)}
                              className="rounded border border-[var(--border)] bg-[var(--surface-raised)] p-1 text-[var(--danger)] hover:bg-[var(--danger)]/10 transition-colors"
                              title="Delete provider credential"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Add Provider Modal */}
            {isAddProviderOpen && (
              <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
                <div className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] p-6 shadow-xl animate-in fade-in zoom-in-95">
                  <h3 className="text-base font-bold text-[var(--text)]">Add Upstream Provider</h3>
                  <p className="mt-1 text-xs text-[var(--text-muted)]">
                    The secret key will be encrypted with your master key and stored securely.
                  </p>

                  {providerError && (
                    <div className="mt-4 rounded-md bg-[var(--danger)]/10 p-2.5 text-xs text-[var(--danger)]">
                      {providerError}
                    </div>
                  )}

                  <form onSubmit={handleCreateProvider} className="mt-4 space-y-4 text-xs">
                    <div>
                      <label className="block font-medium text-[var(--text-muted)] mb-1">
                        Provider Type
                      </label>
                      <select
                        value={providerType}
                        onChange={(e) => setProviderType(e.target.value)}
                        className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
                      >
                        <option value="openai">OpenAI</option>
                        <option value="anthropic">Anthropic</option>
                        <option value="google">Google Gemini</option>
                        <option value="openai_compatible">OpenAI-Compatible (e.g. vLLM, Ollama, Groq)</option>
                        <option value="mock">Mock Provider (for testing)</option>
                      </select>
                    </div>

                    <div>
                      <label className="block font-medium text-[var(--text-muted)] mb-1">
                        Credential Label / Name
                      </label>
                      <input
                        type="text"
                        required
                        value={providerName}
                        onChange={(e) => setProviderName(e.target.value)}
                        placeholder="e.g. Main Production OpenAI Key"
                        className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
                      />
                    </div>

                    <div>
                      <label className="block font-medium text-[var(--text-muted)] mb-1">
                        API Key Secret
                      </label>
                      <input
                        type="password"
                        required
                        value={providerApiKey}
                        onChange={(e) => setProviderApiKey(e.target.value)}
                        placeholder="sk-..."
                        className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 font-mono text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
                      />
                    </div>

                    {providerType === "openai_compatible" && (
                      <div>
                        <label className="block font-medium text-[var(--text-muted)] mb-1">
                          Base URL (https only)
                        </label>
                        <input
                          type="url"
                          required
                          value={providerBaseUrl}
                          onChange={(e) => setProviderBaseUrl(e.target.value)}
                          placeholder="https://api.together.xyz/v1"
                          className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
                        />
                      </div>
                    )}

                    <div className="flex justify-end gap-2 pt-2">
                      <button
                        type="button"
                        onClick={() => setIsAddProviderOpen(false)}
                        className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3.5 py-1.5 font-medium text-[var(--text-muted)] hover:text-[var(--text)]"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={createProviderMutation.isPending}
                        className="rounded-md bg-[var(--accent)] px-4 py-1.5 font-semibold text-white shadow-xs hover:bg-[var(--accent-hover)] disabled:opacity-50"
                      >
                        {createProviderMutation.isPending ? "Encrypting & Saving..." : "Save Key"}
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}

            {/* Delete Provider Confirmation */}
            {providerToDelete && (
              <ConfirmDialog
                isOpen={true}
                title="Delete Provider Credential"
                description={`Are you sure you want to remove "${providerToDelete.name}"? Projects relying exclusively on this provider may fail.`}
                confirmLabel="Delete Credential"
                destructive={true}
                onConfirm={handleDeleteProvider}
                onClose={() => setProviderToDelete(null)}
              />
            )}
          </div>
        )}

        {/* TAB 2: PRICES */}
        {activeTab === "prices" && (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-[var(--text)]">
                  Model Pricing Catalog
                </h2>
                <p className="text-xs text-[var(--text-muted)]">
                  Prices are specified in USD per million tokens (Mtok). Cost is computed per request using exact tokens.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setIsImportPriceOpen(true)}
                  className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-medium text-[var(--text)] hover:bg-[var(--surface-raised)] transition-colors"
                >
                  <Upload className="h-3.5 w-3.5" />
                  <span>Import JSON</span>
                </button>
                <button
                  onClick={() => {
                    setEditingPrice(null);
                    setPriceModel("");
                    setPriceInputMtok("2.50");
                    setPriceOutputMtok("10.00");
                    setIsAddPriceOpen(true);
                  }}
                  className="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-3 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-[var(--accent-hover)] transition-colors"
                >
                  <Plus className="h-3.5 w-3.5" />
                  <span>Add Price</span>
                </button>
              </div>
            </div>

            {priceSuccess && (
              <div className="flex items-center gap-2 rounded-lg bg-[var(--success)]/10 p-3 text-xs text-[var(--success)]">
                <CheckCircle className="h-4 w-4 shrink-0" />
                <span>{priceSuccess}</span>
              </div>
            )}

            {isPricesLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-14 animate-pulse rounded bg-[var(--surface)] border border-[var(--border)]" />
                ))}
              </div>
            ) : !prices || prices.length === 0 ? (
              <EmptyState
                title="No prices configured"
                description="Configure model prices so the gateway can calculate costs and budget enforcement accurately."
                icon={<Tag className="h-6 w-6" />}
              />
            ) : (
              <div className="overflow-x-auto rounded-lg border border-[var(--border)] bg-[var(--surface)] shadow-xs">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-[var(--border)] bg-[var(--surface-raised)] text-[var(--text-muted)]">
                    <tr>
                      <th className="py-3 px-4 font-medium">Model / Provider</th>
                      <th className="py-3 px-4 font-medium">Input / 1M Tokens</th>
                      <th className="py-3 px-4 font-medium">Output / 1M Tokens</th>
                      <th className="py-3 px-4 font-medium">Source / Status</th>
                      <th className="py-3 px-4 font-medium text-right">Edit</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)] text-[var(--text)]">
                    {prices.map((pr) => (
                      <tr key={pr.id} className="hover:bg-[var(--surface-raised)]/60 transition-colors">
                        <td className="py-3 px-4">
                          <span className="font-mono font-medium text-[var(--text)]">
                            {pr.model}
                          </span>
                          <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider">
                            {pr.provider}
                          </p>
                        </td>

                        <td className="py-3 px-4 tabular-nums font-semibold text-[var(--text)]">
                          {formatMicroUsd(pr.input_micro_usd_per_mtok)}
                        </td>

                        <td className="py-3 px-4 tabular-nums font-semibold text-[var(--text)]">
                          {formatMicroUsd(pr.output_micro_usd_per_mtok)}
                        </td>

                        <td className="py-3 px-4">
                          <div className="flex items-center gap-2">
                            {pr.is_seed ? (
                              <span className="rounded bg-[var(--warning)]/10 px-2 py-0.5 text-[10px] font-semibold text-[var(--warning)]">
                                Seed Price — Verify
                              </span>
                            ) : (
                              <span className="rounded bg-[var(--success)]/10 px-2 py-0.5 text-[10px] font-medium text-[var(--success)]">
                                Verified
                              </span>
                            )}
                            {pr.source_url && (
                              <a
                                href={pr.source_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-[var(--text-muted)] hover:text-[var(--accent)]"
                                title="View price source"
                              >
                                <ExternalLink className="h-3 w-3" />
                              </a>
                            )}
                          </div>
                        </td>

                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={() => {
                              setEditingPrice(pr);
                              setPriceProvider(pr.provider);
                              setPriceModel(pr.model);
                              setPriceInputMtok((pr.input_micro_usd_per_mtok / 1_000_000).toFixed(2));
                              setPriceOutputMtok((pr.output_micro_usd_per_mtok / 1_000_000).toFixed(2));
                              setPriceSourceUrl(pr.source_url || "");
                              setIsAddPriceOpen(true);
                            }}
                            className="rounded border border-[var(--border)] bg-[var(--surface-raised)] px-2.5 py-1 text-xs font-medium text-[var(--text)] hover:bg-[var(--muted)] transition-colors"
                          >
                            Edit
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Add / Edit Price Modal */}
            {isAddPriceOpen && (
              <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
                <div className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] p-6 shadow-xl animate-in fade-in zoom-in-95">
                  <h3 className="text-base font-bold text-[var(--text)]">
                    {editingPrice ? `Edit Price: ${editingPrice.model}` : "Add Model Price"}
                  </h3>
                  <p className="mt-1 text-xs text-[var(--text-muted)]">
                    Define token costs in USD per 1 Million Tokens (Mtok).
                  </p>

                  {priceError && (
                    <div className="mt-4 rounded-md bg-[var(--danger)]/10 p-2.5 text-xs text-[var(--danger)]">
                      {priceError}
                    </div>
                  )}

                  <form onSubmit={handleSavePrice} className="mt-4 space-y-4 text-xs">
                    {!editingPrice && (
                      <>
                        <div>
                          <label className="block font-medium text-[var(--text-muted)] mb-1">
                            Provider
                          </label>
                          <input
                            type="text"
                            required
                            value={priceProvider}
                            onChange={(e) => setPriceProvider(e.target.value)}
                            placeholder="openai"
                            className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[var(--text)]"
                          />
                        </div>
                        <div>
                          <label className="block font-medium text-[var(--text-muted)] mb-1">
                            Model Identifier
                          </label>
                          <input
                            type="text"
                            required
                            value={priceModel}
                            onChange={(e) => setPriceModel(e.target.value)}
                            placeholder="gpt-4o"
                            className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 font-mono text-[var(--text)]"
                          />
                        </div>
                      </>
                    )}

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block font-medium text-[var(--text-muted)] mb-1">
                          Input ($ / Mtok)
                        </label>
                        <input
                          type="number"
                          step="0.000001"
                          required
                          value={priceInputMtok}
                          onChange={(e) => setPriceInputMtok(e.target.value)}
                          className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[var(--text)]"
                        />
                      </div>
                      <div>
                        <label className="block font-medium text-[var(--text-muted)] mb-1">
                          Output ($ / Mtok)
                        </label>
                        <input
                          type="number"
                          step="0.000001"
                          required
                          value={priceOutputMtok}
                          onChange={(e) => setPriceOutputMtok(e.target.value)}
                          className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[var(--text)]"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block font-medium text-[var(--text-muted)] mb-1">
                        Source Reference URL
                      </label>
                      <input
                        type="url"
                        required
                        value={priceSourceUrl}
                        onChange={(e) => setPriceSourceUrl(e.target.value)}
                        placeholder="https://..."
                        className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[var(--text)]"
                      />
                    </div>

                    <div className="flex justify-end gap-2 pt-2">
                      <button
                        type="button"
                        onClick={() => setIsAddPriceOpen(false)}
                        className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3.5 py-1.5 font-medium text-[var(--text-muted)] hover:text-[var(--text)]"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        className="rounded-md bg-[var(--accent)] px-4 py-1.5 font-semibold text-white shadow-xs hover:bg-[var(--accent-hover)]"
                      >
                        Save Price
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}

            {/* Import Prices Modal */}
            {isImportPriceOpen && (
              <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
                <div className="w-full max-w-lg rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] p-6 shadow-xl animate-in fade-in zoom-in-95">
                  <h3 className="text-base font-bold text-[var(--text)]">Import Price Catalog</h3>
                  <p className="mt-1 text-xs text-[var(--text-muted)]">
                    Paste a JSON array of model prices conforming to the gateway price schema.
                  </p>

                  {priceError && (
                    <div className="mt-4 rounded-md bg-[var(--danger)]/10 p-2.5 text-xs text-[var(--danger)]">
                      {priceError}
                    </div>
                  )}

                  <form onSubmit={handleImportPrices} className="mt-4 space-y-4 text-xs">
                    <div>
                      <textarea
                        required
                        rows={10}
                        value={importJsonText}
                        onChange={(e) => setImportJsonText(e.target.value)}
                        placeholder={`[\n  {\n    "provider": "openai",\n    "model": "gpt-4o",\n    "input_micro_usd_per_mtok": 2500000,\n    "output_micro_usd_per_mtok": 10000000,\n    "source_url": "https://openai.com/pricing",\n    "verified_on": "2026-03-01"\n  }\n]`}
                        className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] p-3 font-mono text-[11px] text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
                      />
                    </div>

                    <div className="flex justify-end gap-2 pt-2">
                      <button
                        type="button"
                        onClick={() => setIsImportPriceOpen(false)}
                        className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3.5 py-1.5 font-medium text-[var(--text-muted)] hover:text-[var(--text)]"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={importPricesMutation.isPending}
                        className="rounded-md bg-[var(--accent)] px-4 py-1.5 font-semibold text-white shadow-xs hover:bg-[var(--accent-hover)] disabled:opacity-50"
                      >
                        {importPricesMutation.isPending ? "Importing..." : "Import Catalog"}
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 3: RETENTION */}
        {activeTab === "retention" && (
          <form onSubmit={handleSaveRetention} className="space-y-6 max-w-xl">
            <div>
              <h2 className="text-sm font-semibold text-[var(--text)]">Data Retention Policy</h2>
              <p className="text-xs text-[var(--text-muted)] mt-0.5">
                Automatically purge historical completion logs and stored contents past the retention window.
              </p>
            </div>

            {retentionSuccess && (
              <div className="flex items-center gap-2 rounded-lg bg-[var(--success)]/10 p-3 text-xs text-[var(--success)]">
                <CheckCircle className="h-4 w-4 shrink-0" />
                <span>Retention period updated successfully.</span>
              </div>
            )}

            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xs space-y-4 text-xs">
              <div>
                <label className="block font-medium text-[var(--text-muted)] mb-1.5">
                  Retention Window (Days)
                </label>
                <input
                  type="number"
                  min="1"
                  max="365"
                  value={retentionDaysInput ?? settings?.retention_days ?? 30}
                  onChange={(e) => setRetentionDaysInput(parseInt(e.target.value, 10) || 1)}
                  className="w-48 rounded-md border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-2 text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
                />
                <p className="text-[11px] text-[var(--text-muted)] mt-1.5">
                  A nightly background task enforces this limit by deleting expired request rows and prompt bodies.
                </p>
              </div>

              <div className="flex items-start gap-2 rounded-md bg-[var(--muted)]/40 p-3 text-[11px] text-[var(--text-muted)]">
                <Info className="h-4 w-4 shrink-0 mt-0.5" />
                <span>
                  Aggregate stats (daily spend totals, token counts, and error summaries) are retained in summary tables for long-term reporting.
                </span>
              </div>

              <button
                type="submit"
                disabled={updateSettingsMutation.isPending}
                className="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-4 py-2 font-semibold text-white shadow-xs hover:bg-[var(--accent-hover)] transition-colors disabled:opacity-50"
              >
                <Save className="h-3.5 w-3.5" />
                <span>{updateSettingsMutation.isPending ? "Saving..." : "Save Policy"}</span>
              </button>
            </div>
          </form>
        )}

        {/* TAB 4: ACCOUNT */}
        {activeTab === "account" && (
          <form onSubmit={handleChangePassword} className="space-y-6 max-w-md">
            <div>
              <h2 className="text-sm font-semibold text-[var(--text)]">Change Owner Password</h2>
              <p className="text-xs text-[var(--text-muted)] mt-0.5">
                Update your primary administrator credentials.
              </p>
            </div>

            {passwordError && (
              <div className="rounded-md bg-[var(--danger)]/10 p-3 text-xs text-[var(--danger)]">
                {passwordError}
              </div>
            )}

            {passwordSuccess && (
              <div className="rounded-md bg-[var(--success)]/10 p-3 text-xs text-[var(--success)]">
                {passwordSuccess}
              </div>
            )}

            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xs space-y-4 text-xs">
              <div>
                <label className="block font-medium text-[var(--text-muted)] mb-1">
                  Current Password
                </label>
                <input
                  type="password"
                  required
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="w-full rounded-md border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-2 text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
                />
              </div>

              <div>
                <label className="block font-medium text-[var(--text-muted)] mb-1">
                  New Password (Minimum 12 characters)
                </label>
                <input
                  type="password"
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full rounded-md border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-2 text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
                />
              </div>

              <div>
                <label className="block font-medium text-[var(--text-muted)] mb-1">
                  Confirm New Password
                </label>
                <input
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full rounded-md border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-2 text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
                />
              </div>

              <div className="rounded-md bg-[var(--warning)]/10 border border-[var(--warning)]/30 p-2.5 text-[11px] text-[var(--warning)]">
                Note: Updating your password immediately terminates and invalidates all existing active browser sessions.
              </div>

              <button
                type="submit"
                disabled={changePasswordMutation.isPending}
                className="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-4 py-2 font-semibold text-white shadow-xs hover:bg-[var(--accent-hover)] transition-colors disabled:opacity-50"
              >
                <Lock className="h-3.5 w-3.5" />
                <span>{changePasswordMutation.isPending ? "Updating..." : "Change Password"}</span>
              </button>
            </div>
          </form>
        )}

        {/* TAB 5: ABOUT */}
        {activeTab === "about" && (
          <div className="space-y-6 max-w-2xl text-xs">
            <div>
              <h2 className="text-sm font-semibold text-[var(--text)]">About LLM Gateway</h2>
              <p className="text-xs text-[var(--text-muted)] mt-0.5">
                Self-hosted, open-source proxy and cost tracker between applications and AI model providers.
              </p>
            </div>

            {/* Demo Data Management Card */}
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xs space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                  <h3 className="text-sm font-semibold text-[var(--text)]">Sample Demo Data</h3>
                  <p className="text-xs text-[var(--text-muted)] mt-1">
                    {settings?.demo_banner?.has_sample_data || settings?.demo_mode
                      ? "Sample projects, request logs, and budget alerts are currently active in your dashboard."
                      : "No sample data loaded. Dashboard is displaying only your real gateway traffic."}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-[10px] font-semibold ${
                      settings?.demo_banner?.has_sample_data || settings?.demo_mode
                        ? "bg-[var(--accent)]/15 text-[var(--accent)]"
                        : "bg-[var(--success)]/15 text-[var(--success)]"
                    }`}
                  >
                    {settings?.demo_banner?.has_sample_data || settings?.demo_mode
                      ? "Demo Data Active"
                      : "Real Data Only"}
                  </span>
                </div>
              </div>

              {demoActionMessage && (
                <div className="rounded-md bg-[var(--success)]/10 p-2.5 text-xs text-[var(--success)] flex items-center gap-2">
                  <CheckCircle className="h-4 w-4 shrink-0" />
                  <span>{demoActionMessage}</span>
                </div>
              )}

              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-3 border-t border-[var(--border)]">
                <p className="text-[11px] text-[var(--text-muted)]">
                  {settings?.demo_banner?.has_sample_data || settings?.demo_mode
                    ? "Click Unload Demo Data to instantly purge all fake sample records."
                    : "Click Load Demo Data to populate synthetic traffic for charts and explorer views."}
                </p>

                {settings?.demo_banner?.has_sample_data || settings?.demo_mode ? (
                  <button
                    type="button"
                    disabled={clearDemoMutation.isPending}
                    onClick={async () => {
                      setDemoActionMessage(null);
                      try {
                        const res = await clearDemoMutation.mutateAsync();
                        setDemoActionMessage(res.message || "All fake demo data removed. Only real data is displayed.");
                      } catch {
                        // handled
                      }
                    }}
                    className="inline-flex items-center gap-1.5 rounded-md border border-[var(--danger)]/30 bg-[var(--danger)]/10 px-3.5 py-1.5 text-xs font-semibold text-[var(--danger)] hover:bg-[var(--danger)]/20 transition-colors disabled:opacity-50 self-start sm:self-auto"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    <span>{clearDemoMutation.isPending ? "Unloading..." : "Unload Demo Data"}</span>
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled={seedDemoMutation.isPending}
                    onClick={async () => {
                      setDemoActionMessage(null);
                      try {
                        const res = await seedDemoMutation.mutateAsync();
                        setDemoActionMessage(res.message || "Sample demo data loaded successfully.");
                      } catch {
                        // handled
                      }
                    }}
                    className="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-[var(--accent-hover)] transition-colors disabled:opacity-50 self-start sm:self-auto"
                  >
                    <Sparkles className="h-3.5 w-3.5" />
                    <span>{seedDemoMutation.isPending ? "Loading..." : "Load Demo Data"}</span>
                  </button>
                )}
              </div>
            </div>

            {/* System Info Card */}
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xs space-y-4">
              <h3 className="text-sm font-semibold text-[var(--text)]">System Info</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-[var(--text-muted)] block">Version:</span>
                  <span className="font-mono font-bold text-[var(--text)]">v0.1.0</span>
                </div>
                <div>
                  <span className="text-[var(--text-muted)] block">Backend Engine:</span>
                  <span className="text-[var(--text)]">FastAPI (Python 3.13) + SQLite / PostgreSQL</span>
                </div>
                <div>
                  <span className="text-[var(--text-muted)] block">Frontend UI:</span>
                  <span className="text-[var(--text)]">Next.js 16 (React 19, Tailwind v4)</span>
                </div>
                <div>
                  <span className="text-[var(--text-muted)] block">Data Retention:</span>
                  <span className="text-[var(--text)]">{settings?.retention_days ?? 30} days</span>
                </div>
              </div>

              <div className="pt-3 border-t border-[var(--border)] flex items-center justify-between">
                <span className="text-[var(--text-muted)]">Open Source Repository:</span>
                <a
                  href="https://github.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 font-medium text-[var(--accent)] hover:underline"
                >
                  <span>GitHub</span>
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
