"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  FolderKanban,
  Key,
  Plus,
  Search,
  Sparkles,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { BudgetBar } from "@/components/shared/BudgetBar";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import {
  useCreateProject,
  useProjects,
  useSeedDemo,
  useSettings,
} from "@/lib/queries";

export default function ProjectsPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [projectDesc, setProjectDesc] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);

  const {
    data: projects,
    isLoading,
    isError,
    error,
    refetch,
  } = useProjects();
  const { data: settings } = useSettings();
  const createProjectMutation = useCreateProject();
  const seedDemoMutation = useSeedDemo();

  const filteredProjects = (projects || []).filter(
    (p) =>
      p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.slug.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectName.trim() || createProjectMutation.isPending) return;
    setCreateError(null);

    try {
      await createProjectMutation.mutateAsync({
        name: projectName.trim(),
        description: projectDesc.trim() || undefined,
      });
      setProjectName("");
      setProjectDesc("");
      setIsCreateModalOpen(false);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setCreateError(err.message);
      } else {
        setCreateError("Failed to create project.");
      }
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

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-[var(--text)]">
              Projects
            </h1>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              Manage your application workspaces, budgets, gateway keys and routing configs.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-[var(--accent-hover)] transition-colors"
            >
              <Plus className="h-4 w-4" />
              <span>New Project</span>
            </button>
          </div>
        </div>

        {/* Error State */}
        {isError && (
          <ErrorState
            title="Failed to load projects"
            message={
              error instanceof Error
                ? error.message
                : "Could not retrieve projects from gateway."
            }
            onRetry={() => refetch()}
          />
        )}

        {/* Search Bar */}
        <div className="relative max-w-sm">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-[var(--text-muted)]" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search projects by name or slug..."
            className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] py-1.5 pl-9 pr-3 text-xs text-[var(--text)] placeholder-[var(--text-muted)] focus:border-[var(--accent)] focus:outline-hidden"
          />
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 animate-pulse rounded bg-[var(--muted)]/50" />
            ))}
          </div>
        )}

        {/* Empty State */}
        {!isLoading && (!projects || projects.length === 0) && (
          <EmptyState
            title="No projects configured"
            description="Create your first project to configure models, keys and budgets."
            icon={<FolderKanban className="h-6 w-6" />}
            action={
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setIsCreateModalOpen(true)}
                  className="rounded-md bg-[var(--accent)] px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-[var(--accent-hover)] transition-colors"
                >
                  Create Project
                </button>
                {settings?.demo_mode && (
                  <button
                    onClick={handleSeedDemo}
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

        {/* Projects Table */}
        {!isLoading && projects && projects.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-[var(--border)] bg-[var(--surface)] shadow-xs">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-[var(--border)] bg-[var(--surface-raised)] text-[var(--text-muted)]">
                <tr>
                  <th className="py-3 px-4 font-medium">Project</th>
                  <th className="py-3 px-4 font-medium">Active Keys</th>
                  <th className="py-3 px-4 font-medium min-w-[180px]">Monthly Budget</th>
                  <th className="py-3 px-4 font-medium">Created</th>
                  <th className="py-3 px-4 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)] text-[var(--text)]">
                {filteredProjects.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-xs text-[var(--text-muted)]">
                      No projects matching &ldquo;{searchTerm}&rdquo;
                    </td>
                  </tr>
                ) : (
                  filteredProjects.map((p) => (
                    <tr
                      key={p.id}
                      className="hover:bg-[var(--surface-raised)]/60 transition-colors"
                    >
                      <td className="py-3 px-4">
                        <Link
                          href={`/projects/${p.id}`}
                          className="font-medium text-[var(--text)] hover:text-[var(--accent)] transition-colors"
                        >
                          {p.name}
                        </Link>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="font-mono text-[11px] text-[var(--text-muted)]">
                            {p.slug}
                          </span>
                          {p.description && (
                            <>
                              <span className="text-[var(--text-muted)]">•</span>
                              <span className="text-[11px] text-[var(--text-muted)] truncate max-w-xs">
                                {p.description}
                              </span>
                            </>
                          )}
                        </div>
                      </td>

                      <td className="py-3 px-4">
                        <div className="inline-flex items-center gap-1.5 rounded-full bg-[var(--surface-raised)] border border-[var(--border)] px-2.5 py-0.5 text-[11px] font-medium">
                          <Key className="h-3 w-3 text-[var(--text-muted)]" />
                          <span>{p.active_keys_count}</span>
                        </div>
                      </td>

                      <td className="py-3 px-4">
                        <BudgetBar spentMicroUsd={0} budgetMicroUsd={null} showLabels={false} />
                      </td>

                      <td className="py-3 px-4 text-[var(--text-muted)] font-mono text-[11px]">
                        {new Date(p.created_at).toLocaleDateString()}
                      </td>

                      <td className="py-3 px-4 text-right">
                        <Link
                          href={`/projects/${p.id}`}
                          className="inline-flex items-center gap-1 rounded border border-[var(--border)] bg-[var(--surface-raised)] px-2.5 py-1 text-xs font-medium text-[var(--text)] hover:bg-[var(--muted)] transition-colors"
                        >
                          <span>Manage</span>
                          <ArrowRight className="h-3 w-3" />
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Create Project Modal */}
        {isCreateModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
            <div className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] p-6 shadow-xl animate-in fade-in zoom-in-95 duration-150">
              <h2 className="text-base font-bold text-[var(--text)]">Create Project</h2>
              <p className="mt-1 text-xs text-[var(--text-muted)]">
                A project encapsulates gateway keys, usage analytics, budgets and routing chains.
              </p>

              {createError && (
                <div className="mt-4 rounded-md bg-[var(--danger)]/10 p-2.5 text-xs text-[var(--danger)]">
                  {createError}
                </div>
              )}

              <form onSubmit={handleCreate} className="mt-4 space-y-4">
                <div>
                  <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">
                    Project Name
                  </label>
                  <input
                    type="text"
                    required
                    value={projectName}
                    onChange={(e) => setProjectName(e.target.value)}
                    placeholder="e.g. Production Mobile App"
                    className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-xs text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
                    autoFocus
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">
                    Description (Optional)
                  </label>
                  <input
                    type="text"
                    value={projectDesc}
                    onChange={(e) => setProjectDesc(e.target.value)}
                    placeholder="Customer-facing iOS and Android LLM features"
                    className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-xs text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
                  />
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsCreateModalOpen(false)}
                    className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-medium text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-raised)]"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={!projectName.trim() || createProjectMutation.isPending}
                    className="rounded-md bg-[var(--accent)] px-4 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-[var(--accent-hover)] disabled:opacity-50"
                  >
                    {createProjectMutation.isPending ? "Creating..." : "Create Project"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
