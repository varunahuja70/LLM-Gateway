"use client";

import {
  AlertTriangle,
  ArrowRight,
  ThumbsDown,
  ThumbsUp,
  X,
} from "lucide-react";
import { CodeSnippet } from "@/components/shared/CodeSnippet";
import {
  formatLatency,
  formatMicroUsd,
  formatTokens,
} from "@/lib/formatters";
import { useRequestDetail } from "@/lib/queries";

interface RequestDetailSheetProps {
  requestId: string | null;
  onClose: () => void;
}

export function RequestDetailSheet({
  requestId,
  onClose,
}: RequestDetailSheetProps) {
  const { data: request, isLoading } = useRequestDetail(requestId || "");

  if (!requestId) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50 backdrop-blur-xs">
      <div
        className="fixed inset-0"
        onClick={onClose}
        aria-hidden="true"
      />
      <div className="relative flex h-full w-full max-w-xl flex-col border-l border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl overflow-y-auto animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--border)] pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold text-[var(--text)]">
                {request?.id || requestId}
              </span>
              {request && (
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                    request.http_status === 200
                      ? "bg-[var(--success)]/10 text-[var(--success)]"
                      : "bg-[var(--danger)]/10 text-[var(--danger)]"
                  }`}
                >
                  HTTP {request.http_status}
                </span>
              )}
            </div>
            <p className="text-xs text-[var(--text-muted)] mt-1">
              {request?.created_at ? new Date(request.created_at).toLocaleString() : "Loading..."}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1.5 text-[var(--text-muted)] hover:bg-[var(--surface-raised)] hover:text-[var(--text)] transition-colors"
            aria-label="Close detail panel"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Loading skeleton */}
        {isLoading && (
          <div className="space-y-4 pt-6">
            <div className="h-10 animate-pulse rounded bg-[var(--muted)]/50" />
            <div className="h-24 animate-pulse rounded bg-[var(--muted)]/30" />
            <div className="h-48 animate-pulse rounded bg-[var(--muted)]/30" />
          </div>
        )}

        {/* Content body */}
        {request && (
          <div className="mt-6 space-y-6 text-xs">
            {/* Core Metrics Grid */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-3">
                <span className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider block mb-1">
                  Latency
                </span>
                <span className="text-base font-bold text-[var(--text)] tabular-nums">
                  {formatLatency(request.latency_ms)}
                </span>
                {request.ttft_ms !== null && (
                  <span className="text-[10px] text-[var(--text-muted)] block mt-0.5">
                    TTFT: {formatLatency(request.ttft_ms)}
                  </span>
                )}
              </div>

              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-3">
                <span className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider block mb-1">
                  Total Tokens
                </span>
                <span className="text-base font-bold text-[var(--text)] tabular-nums">
                  {formatTokens(request.input_tokens + request.output_tokens)}
                </span>
                <span className="text-[10px] text-[var(--text-muted)] block mt-0.5">
                  In: {formatTokens(request.input_tokens)} · Out: {formatTokens(request.output_tokens)}
                </span>
              </div>

              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-3">
                <span className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider block mb-1">
                  Cost
                </span>
                <span className="text-base font-bold text-[var(--text)] tabular-nums">
                  {formatMicroUsd(request.cost_micro_usd)}
                </span>
                {request.usage_estimated && (
                  <span className="text-[10px] text-[var(--warning)] block mt-0.5">
                    Estimated
                  </span>
                )}
              </div>

              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-3">
                <span className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider block mb-1">
                  Savings
                </span>
                <span className="text-base font-bold text-[var(--success)] tabular-nums">
                  {formatMicroUsd(request.saved_micro_usd)}
                </span>
                <span className="text-[10px] text-[var(--text-muted)] block mt-0.5">
                  {request.cache_hit ? "Cache Hit" : "No Cache"}
                </span>
              </div>
            </div>

            {/* Model & Routing Details */}
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-4 space-y-3">
              <span className="text-xs font-semibold text-[var(--text)] block">
                Model & Provider
              </span>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-[var(--text-muted)] block">Provider:</span>
                  <span className="font-medium text-[var(--text)] capitalize">
                    {request.provider}
                  </span>
                </div>
                <div>
                  <span className="text-[var(--text-muted)] block">Model Used:</span>
                  <span className="font-mono font-medium text-[var(--text)]">
                    {request.model_used}
                  </span>
                </div>
                <div>
                  <span className="text-[var(--text-muted)] block">Endpoint:</span>
                  <span className="font-mono text-[var(--text)]">{request.endpoint}</span>
                </div>
                <div>
                  <span className="text-[var(--text-muted)] block">Streamed:</span>
                  <span className="text-[var(--text)]">{request.streamed ? "Yes" : "No"}</span>
                </div>
                {request.user_tag && (
                  <div className="col-span-2">
                    <span className="text-[var(--text-muted)] block">User Tag:</span>
                    <span className="font-mono text-[var(--text)]">{request.user_tag}</span>
                  </div>
                )}
              </div>

              {/* Fallback Story if triggered */}
              {request.fallback_used && (
                <div className="mt-3 rounded-md bg-[var(--warning)]/10 border border-[var(--warning)]/30 p-3">
                  <div className="flex items-center gap-1.5 text-[var(--warning)] font-semibold mb-1">
                    <AlertTriangle className="h-4 w-4" />
                    <span>Fallback Triggered</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-[var(--text)] mt-1 font-mono">
                    <span>{request.fallback_from}</span>
                    <ArrowRight className="h-3 w-3 text-[var(--text-muted)]" />
                    <span className="font-semibold text-[var(--success)]">{request.model_used}</span>
                  </div>
                  {request.fallback_reason && (
                    <p className="text-[11px] text-[var(--text-muted)] mt-1">
                      Reason: {request.fallback_reason}
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Error Story if failed */}
            {request.http_status !== 200 && (
              <div className="rounded-lg border border-[var(--danger)]/30 bg-[var(--danger)]/5 p-4 space-y-2">
                <span className="text-xs font-semibold text-[var(--danger)] block">
                  Error Details
                </span>
                <div className="space-y-1 text-xs">
                  <p>
                    <span className="text-[var(--text-muted)]">Type: </span>
                    <span className="font-mono font-medium text-[var(--danger)]">
                      {request.error_type || "InternalError"}
                    </span>
                  </p>
                  {request.error_message_safe && (
                    <p className="rounded bg-[var(--surface)] p-2 font-mono text-[11px] text-[var(--text)] border border-[var(--border)]">
                      {request.error_message_safe}
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Quality & Feedback Signals */}
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-4 space-y-2">
              <span className="text-xs font-semibold text-[var(--text)] block">
                Quality Signals
              </span>
              <div className="flex items-center justify-between text-xs">
                <span>Finish Reason:</span>
                <span className="font-mono text-[var(--text-muted)]">
                  {request.finish_reason || "stop"}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span>Empty or Truncated:</span>
                <span className={request.empty_or_truncated ? "text-[var(--danger)] font-medium" : "text-[var(--text-muted)]"}>
                  {request.empty_or_truncated ? "Yes" : "No"}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span>User Feedback:</span>
                {request.feedback_score === 1 ? (
                  <span className="inline-flex items-center gap-1 text-[var(--success)] font-medium">
                    <ThumbsUp className="h-3.5 w-3.5" /> Positive
                  </span>
                ) : request.feedback_score === -1 ? (
                  <span className="inline-flex items-center gap-1 text-[var(--danger)] font-medium">
                    <ThumbsDown className="h-3.5 w-3.5" /> Negative
                  </span>
                ) : (
                  <span className="text-[var(--text-muted)]">None recorded</span>
                )}
              </div>
            </div>

            {/* Content (if logged) */}
            {request.content ? (
              <div className="space-y-3">
                <span className="text-xs font-semibold text-[var(--text)] block">
                  Logged Payloads
                </span>
                <div>
                  <span className="text-[11px] text-[var(--text-muted)] block mb-1">
                    Request Payload
                  </span>
                  <CodeSnippet
                    language="json"
                    code={JSON.stringify(request.content.request_json, null, 2)}
                  />
                </div>
                <div>
                  <span className="text-[11px] text-[var(--text-muted)] block mb-1">
                    Response Payload
                  </span>
                  <CodeSnippet
                    language="json"
                    code={JSON.stringify(request.content.response_json, null, 2)}
                  />
                </div>
              </div>
            ) : (
              <div className="rounded-lg border border-dashed border-[var(--border)] p-4 text-center text-xs text-[var(--text-muted)]">
                Content logging is disabled for this project. Prompt and response payloads are not stored.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
