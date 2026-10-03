import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, setCsrfToken } from "./api";
import {
  BudgetAlertItem,
  CreatedGatewayKey,
  GatewayKey,
  ModelPrice,
  ModelsQualityResponse,
  OverviewStats,
  OwnerUser,
  Project,
  ProjectConfig,
  ProjectStatsResponse,
  ProviderCredential,
  RequestDetailResponse,
  RequestListResponse,
  SettingsResponse,
  SetupStatusResponse,
  TimeseriesResponse,
} from "./api-types";

export const queryKeys = {
  setupStatus: ["setup", "status"] as const,
  authMe: ["auth", "me"] as const,
  projects: ["projects"] as const,
  project: (id: string) => ["projects", id] as const,
  projectConfig: (id: string) => ["projects", id, "config"] as const,
  projectKeys: (id: string) => ["projects", id, "keys"] as const,
  projectStats: (id: string, from?: string, to?: string) =>
    ["stats", "project", id, { from, to }] as const,
  overviewStats: (from?: string, to?: string, projectId?: string) =>
    ["stats", "overview", { from, to, projectId }] as const,
  timeseriesStats: (from?: string, to?: string, bucket?: string, projectId?: string) =>
    ["stats", "timeseries", { from, to, bucket, projectId }] as const,
  modelsStats: (from?: string, to?: string, projectId?: string) =>
    ["stats", "models", { from, to, projectId }] as const,
  requests: (params: Record<string, unknown>) => ["requests", params] as const,
  requestDetail: (id: string) => ["requests", id] as const,
  providers: ["providers"] as const,
  prices: ["prices"] as const,
  alerts: ["alerts"] as const,
  settings: ["settings"] as const,
};

// 1. Auth & Setup
export function useSetupStatus() {
  return useQuery<SetupStatusResponse>({
    queryKey: queryKeys.setupStatus,
    queryFn: () => api.get<SetupStatusResponse>("/admin/setup/status"),
    // Setup status never changes after initial setup — cache for 1 hour
    staleTime: 60 * 60 * 1000,
    gcTime: 60 * 60 * 1000,
  });
}

export function useAuth() {
  return useQuery<OwnerUser>({
    queryKey: queryKeys.authMe,
    queryFn: async () => {
      const res = await api.get<OwnerUser>("/admin/auth/me");
      if (res?.csrf_token) {
        setCsrfToken(res.csrf_token);
      }
      return res;
    },
    // Don't retry on 401 (not authenticated) — only on network errors
    retry: (failureCount, error) => {
      if (error instanceof Error && "status" in error && (error as { status: number }).status === 401) {
        return false;
      }
      return failureCount < 2;
    },
    // Keep data fresh for 5 minutes — avoids constant refetches kicking users out
    staleTime: 5 * 60 * 1000,
    // Keep cached data for 10 minutes even when not subscribed
    gcTime: 10 * 60 * 1000,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (credentials: { email: string; password: string }) =>
      api.post<OwnerUser>("/admin/auth/login", credentials),
    onSuccess: (data) => {
      if (data?.csrf_token) {
        setCsrfToken(data.csrf_token);
      }
      queryClient.setQueryData(queryKeys.authMe, data);
      queryClient.invalidateQueries({ queryKey: queryKeys.authMe });
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post("/admin/auth/logout"),
    onSuccess: () => {
      setCsrfToken(null);
      queryClient.setQueryData(queryKeys.authMe, null);
      queryClient.clear();
    },
  });
}

export function useSetup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { email: string; password: string }) =>
      api.post<OwnerUser>("/admin/setup", data),
    onSuccess: (data) => {
      if (data?.csrf_token) {
        setCsrfToken(data.csrf_token);
      }
      queryClient.setQueryData(queryKeys.setupStatus, { is_setup: true, setup_completed: true });
      queryClient.setQueryData(queryKeys.authMe, data);
    },
  });
}

// 2. Projects
export function useProjects() {
  return useQuery<Project[]>({
    queryKey: queryKeys.projects,
    queryFn: () => api.get<Project[]>("/admin/projects"),
  });
}

export function useProject(id: string) {
  return useQuery<Project>({
    queryKey: queryKeys.project(id),
    queryFn: () => api.get<Project>(`/admin/projects/${id}`),
    enabled: !!id,
  });
}

export function useProjectConfig(id: string) {
  return useQuery<ProjectConfig>({
    queryKey: queryKeys.projectConfig(id),
    queryFn: () => api.get<ProjectConfig>(`/admin/projects/${id}/config`),
    enabled: !!id,
  });
}

export function useProjectKeys(id: string) {
  return useQuery<GatewayKey[]>({
    queryKey: queryKeys.projectKeys(id),
    queryFn: () => api.get<GatewayKey[]>(`/admin/projects/${id}/keys`),
    enabled: !!id,
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      api.post<Project>("/admin/projects", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects });
    },
  });
}

export function useUpdateProject(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { name?: string; description?: string }) =>
      api.patch<Project>(`/admin/projects/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects });
      queryClient.invalidateQueries({ queryKey: queryKeys.project(id) });
    },
  });
}

export function useArchiveProject(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.delete<Project>(`/admin/projects/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects });
      queryClient.invalidateQueries({ queryKey: queryKeys.project(id) });
    },
  });
}

export function useDeleteProjectData(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.delete<{ message: string; rows_deleted: number }>(`/admin/projects/${id}/data`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects });
      queryClient.invalidateQueries({ queryKey: queryKeys.project(id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.overviewStats() });
    },
  });
}

export function useUpdateProjectConfig(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<ProjectConfig>) =>
      api.put<ProjectConfig>(`/admin/projects/${id}/config`, data),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.projectConfig(id), data);
      queryClient.invalidateQueries({ queryKey: queryKeys.projectConfig(id) });
    },
  });
}

export function useCreateProjectKey(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; expires_at?: string | null }) =>
      api.post<CreatedGatewayKey>(`/admin/projects/${projectId}/keys`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projectKeys(projectId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.projects });
    },
  });
}

export function useRevokeProjectKey(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (keyId: string) =>
      api.delete<{ message: string }>(`/admin/projects/${projectId}/keys/${keyId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projectKeys(projectId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.projects });
    },
  });
}

export function useRotateProjectKey(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (keyId: string) =>
      api.post<CreatedGatewayKey>(`/admin/projects/${projectId}/keys/${keyId}/rotate`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projectKeys(projectId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.projects });
    },
  });
}

export function useSeedDemo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ message: string }>("/admin/settings/seed-demo"),
    onSuccess: () => {
      queryClient.invalidateQueries();
    },
  });
}

export function useClearDemo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ message: string }>("/admin/settings/clear-demo"),
    onSuccess: () => {
      queryClient.invalidateQueries();
    },
  });
}

// 3. Stats
export function useOverviewStats(from?: string, to?: string, projectId?: string) {
  const params = new URLSearchParams();
  if (from) params.set("from", from);
  if (to) params.set("to", to);
  if (projectId) params.set("project_id", projectId);
  const q = params.toString() ? `?${params.toString()}` : "";

  return useQuery<OverviewStats>({
    queryKey: queryKeys.overviewStats(from, to, projectId),
    queryFn: () => api.get<OverviewStats>(`/admin/stats/overview${q}`),
  });
}

export function useTimeseriesStats(from?: string, to?: string, bucket: string = "hour", projectId?: string) {
  const params = new URLSearchParams({ bucket });
  if (from) params.set("from", from);
  if (to) params.set("to", to);
  if (projectId) params.set("project_id", projectId);
  const q = `?${params.toString()}`;

  return useQuery<TimeseriesResponse>({
    queryKey: queryKeys.timeseriesStats(from, to, bucket, projectId),
    queryFn: () => api.get<TimeseriesResponse>(`/admin/stats/timeseries${q}`),
  });
}

export function useModelsStats(from?: string, to?: string, projectId?: string) {
  const params = new URLSearchParams();
  if (from) params.set("from", from);
  if (to) params.set("to", to);
  if (projectId) params.set("project_id", projectId);
  const q = params.toString() ? `?${params.toString()}` : "";

  return useQuery<ModelsQualityResponse>({
    queryKey: queryKeys.modelsStats(from, to, projectId),
    queryFn: () => api.get<ModelsQualityResponse>(`/admin/stats/models${q}`),
  });
}

export function useProjectStats(projectId: string, from?: string, to?: string) {
  const params = new URLSearchParams();
  if (from) params.set("from", from);
  if (to) params.set("to", to);
  const q = params.toString() ? `?${params.toString()}` : "";

  return useQuery<ProjectStatsResponse>({
    queryKey: queryKeys.projectStats(projectId, from, to),
    queryFn: () => api.get<ProjectStatsResponse>(`/admin/stats/projects/${projectId}${q}`),
    enabled: !!projectId,
  });
}

// 4. Requests Explorer
export function useRequests(filters: {
  project_id?: string;
  model?: string;
  provider?: string;
  status?: string;
  from?: string;
  to?: string;
  cache_hit?: boolean;
  fallback_used?: boolean;
  user_tag?: string;
  search?: string;
  cursor?: string;
  limit?: number;
}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") {
      params.set(k, String(v));
    }
  });
  const q = params.toString() ? `?${params.toString()}` : "";

  return useQuery<RequestListResponse>({
    queryKey: queryKeys.requests(filters),
    queryFn: () => api.get<RequestListResponse>(`/admin/requests${q}`),
  });
}

export function useRequestDetail(id: string) {
  return useQuery<RequestDetailResponse>({
    queryKey: queryKeys.requestDetail(id),
    queryFn: () => api.get<RequestDetailResponse>(`/admin/requests/${id}`),
    enabled: !!id,
  });
}

// 5. Providers, Prices, Alerts, Settings
export function useProviders() {
  return useQuery<ProviderCredential[]>({
    queryKey: queryKeys.providers,
    queryFn: () => api.get<ProviderCredential[]>("/admin/providers"),
  });
}

export function usePrices() {
  return useQuery<ModelPrice[]>({
    queryKey: queryKeys.prices,
    queryFn: () => api.get<ModelPrice[]>("/admin/prices"),
  });
}

export function useAlerts() {
  return useQuery<BudgetAlertItem[]>({
    queryKey: queryKeys.alerts,
    queryFn: () => api.get<BudgetAlertItem[]>("/admin/alerts"),
  });
}

export function useSettings() {
  return useQuery<SettingsResponse>({
    queryKey: queryKeys.settings,
    queryFn: () => api.get<SettingsResponse>("/admin/settings"),
  });
}

export function useCreateProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      provider: string;
      name: string;
      api_key: string;
      base_url?: string | null;
    }) => api.post<ProviderCredential>("/admin/providers", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.providers });
    },
  });
}

export function useUpdateProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: { id: string; name?: string; is_disabled?: boolean; base_url?: string | null }) =>
      api.patch<ProviderCredential>(`/admin/providers/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.providers });
    },
  });
}

export function useDeleteProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<{ message: string }>(`/admin/providers/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.providers });
    },
  });
}

export function useTestProvider() {
  return useMutation({
    mutationFn: (id: string) =>
      api.post<{ status: string; success: boolean; latency_ms: number; message: string; model_tested?: string }>(
        `/admin/providers/${id}/test`
      ),
  });
}

export function useCreatePrice() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      provider: string;
      model: string;
      input_micro_usd_per_mtok: number;
      output_micro_usd_per_mtok: number;
      cached_input_micro_usd_per_mtok?: number | null;
      source_url: string;
      verified_on: string;
    }) => api.post<ModelPrice>("/admin/prices", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.prices });
    },
  });
}

export function useUpdatePrice(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      input_micro_usd_per_mtok?: number;
      output_micro_usd_per_mtok?: number;
      cached_input_micro_usd_per_mtok?: number | null;
      source_url?: string;
      verified_on?: string;
    }) => api.put<ModelPrice>(`/admin/prices/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.prices });
    },
  });
}

export function useImportPrices() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { prices: Record<string, unknown>[] }) =>
      api.post<{ message: string; imported_count: number }>("/admin/prices/import", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.prices });
    },
  });
}

export function useUpdateSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { retention_days?: number; demo_mode?: boolean }) =>
      api.put<SettingsResponse>("/admin/settings", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings });
    },
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (data: { current_password: string; new_password: string }) =>
      api.post<{ message: string }>("/admin/auth/change-password", data),
  });
}
