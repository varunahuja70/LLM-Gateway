export interface SetupStatusResponse {
  is_setup: boolean;
  setup_completed?: boolean;
}

export interface OwnerUser {
  id: string;
  email: string;
  created_at: string;
  csrf_token: string;
}

export interface MessageResponse {
  message: string;
}

export interface Project {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  created_at: string;
  archived_at: string | null;
  active_keys_count: number;
}

export interface FallbackTarget {
  provider: string;
  model: string;
}

export interface ProjectConfig {
  project_id: string;
  daily_budget_micro_usd: number | null;
  monthly_budget_micro_usd: number | null;
  warn_thresholds: number[];
  block_at_limit: boolean;
  fallback_chain: FallbackTarget[];
  max_fallbacks: number;
  request_timeout_s: number;
  cache_enabled: boolean;
  cache_ttl_s: number;
  rpm_limit: number | null;
  log_content: boolean;
  provider_credential_id: string | null;
  webhook_url: string | null;
}

export interface GatewayKey {
  id: string;
  project_id: string;
  name: string;
  prefix: string;
  created_at: string;
  expires_at: string | null;
  revoked_at: string | null;
  last_used_at: string | null;
}

export interface CreatedGatewayKey extends GatewayKey {
  key: string;
}

export interface ProviderCredential {
  id: string;
  provider: string;
  name: string;
  key_suffix: string;
  base_url: string | null;
  is_enabled: boolean;
  created_at: string;
}

export interface ModelPrice {
  id: string;
  provider: string;
  model: string;
  input_micro_usd_per_mtok: number;
  output_micro_usd_per_mtok: number;
  cached_input_micro_usd_per_mtok: number | null;
  source_url: string;
  verified_on: string;
  is_seed: boolean;
  updated_at: string;
}

export interface RequestContentDetail {
  request_id: string;
  request_json: Record<string, unknown>;
  response_json: Record<string, unknown>;
}

export interface RequestLogSummary {
  id: string;
  project_id: string;
  gateway_key_id: string | null;
  created_at: string;
  endpoint: string;
  provider: string;
  model_requested: string;
  model_used: string;
  status: string;
  http_status: number;
  error_type: string | null;
  error_message_safe: string | null;
  input_tokens: number;
  output_tokens: number;
  cached_input_tokens: number;
  usage_estimated: boolean;
  cost_micro_usd: number | null;
  saved_micro_usd: number;
  latency_ms: number;
  ttft_ms: number | null;
  streamed: boolean;
  cache_hit: boolean;
  fallback_used: boolean;
  fallback_from: string | null;
  fallback_reason: string | null;
  finish_reason: string | null;
  empty_or_truncated: boolean;
  user_tag: string | null;
  feedback_score: number | null;
}

export interface RequestDetailResponse extends RequestLogSummary {
  content: RequestContentDetail | null;
}

export interface RequestListResponse {
  items: RequestLogSummary[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface OverviewStats {
  total_requests: number;
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  cached_input_tokens: number;
  total_cost_micro_usd: number;
  saved_micro_usd: number;
  error_rate: number;
  fallback_rate: number;
  avg_latency_ms: number;
  p95_latency_ms: number | null;
  cache_hit_rate: number;
}

export interface TimeseriesBucket {
  timestamp: string;
  requests: number;
  errors: number;
  tokens: number;
  input_tokens: number;
  output_tokens: number;
  cost_micro_usd: number;
  saved_micro_usd: number;
  cache_hits: number;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  p99_latency_ms: number | null;
}

export interface TimeseriesResponse {
  bucket: string;
  data: TimeseriesBucket[];
}

export interface ModelQualityStat {
  model: string;
  provider: string;
  total_requests: number;
  total_tokens: number;
  total_cost_micro_usd: number;
  error_rate: number;
  fallback_rate: number;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  p99_latency_ms: number | null;
  avg_ttft_ms: number | null;
  empty_or_truncated_rate: number;
  avg_feedback_score: number | null;
}

export interface ModelsQualityResponse {
  data: ModelQualityStat[];
}

export interface ProjectStatsResponse {
  project_id: string;
  overview: OverviewStats;
  models: ModelQualityStat[];
  budget_daily_used_micro_usd: number;
  budget_monthly_used_micro_usd: number;
}

export interface BudgetAlertItem {
  id: string;
  project_id: string;
  period: string;
  period_start: string;
  threshold_percent: number;
  spend_micro_usd: number;
  budget_micro_usd: number;
  created_at: string;
  webhook_status: string;
  webhook_attempts: number;
  last_error: string | null;
}

export interface DemoBannerData {
  is_demo: boolean;
  message: string;
  has_sample_data: boolean;
}

export interface SettingsResponse {
  retention_days: number;
  demo_mode: boolean;
  demo_banner: DemoBannerData;
  notification_defaults: Record<string, unknown>;
}
