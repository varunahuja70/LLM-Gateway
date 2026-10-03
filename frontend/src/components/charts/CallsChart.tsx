"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Table, BarChart2 } from "lucide-react";
import { formatTokens } from "@/lib/formatters";
import { TimeseriesBucket } from "@/lib/api-types";

interface CallsChartProps {
  data: TimeseriesBucket[];
  loading?: boolean;
}

export function CallsChart({ data, loading = false }: CallsChartProps) {
  const [showTable, setShowTable] = useState(false);

  if (loading) {
    return (
      <div className="h-72 w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 flex flex-col justify-between">
        <div className="h-4 w-32 animate-pulse rounded bg-[var(--muted)]" />
        <div className="h-48 w-full animate-pulse rounded bg-[var(--muted)]/50" />
      </div>
    );
  }

  const chartData = (data || []).map((pt) => ({
    timestamp: pt.timestamp,
    label: new Date(pt.timestamp).toLocaleTimeString([], {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }),
    calls: pt.requests || 0,
    errors: pt.errors || 0,
    cache_hits: pt.cache_hits || 0,
  }));

  const totalCalls = chartData.reduce((acc, curr) => acc + curr.calls, 0);
  const totalErrors = chartData.reduce((acc, curr) => acc + curr.errors, 0);

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xs">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <div>
          <h3 className="text-sm font-semibold text-[var(--text)]">Calls & Errors</h3>
          <p className="text-xs text-[var(--text-muted)]">
            {formatTokens(totalCalls)} requests · {formatTokens(totalErrors)} errors
          </p>
        </div>
        <button
          onClick={() => setShowTable(!showTable)}
          className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--surface-raised)] px-2.5 py-1 text-xs font-medium text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--muted)] transition-colors"
          aria-label={showTable ? "View as chart" : "View as table"}
        >
          {showTable ? <BarChart2 className="h-3.5 w-3.5" /> : <Table className="h-3.5 w-3.5" />}
          <span>{showTable ? "Chart View" : "Table View"}</span>
        </button>
      </div>

      {chartData.length === 0 ? (
        <div className="flex h-56 items-center justify-center text-xs text-[var(--text-muted)]">
          No calls recorded for this period.
        </div>
      ) : showTable ? (
        <div className="h-64 overflow-y-auto rounded-md border border-[var(--border)]">
          <table className="w-full text-left text-xs">
            <thead className="bg-[var(--surface-raised)] text-[var(--text-muted)] sticky top-0">
              <tr>
                <th className="py-2 px-3 font-medium">Timestamp</th>
                <th className="py-2 px-3 font-medium text-right">Calls</th>
                <th className="py-2 px-3 font-medium text-right">Errors</th>
                <th className="py-2 px-3 font-medium text-right">Cache Hits</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)] text-[var(--text)]">
              {chartData.map((row, i) => (
                <tr key={i} className="hover:bg-[var(--surface-raised)]/50">
                  <td className="py-1.5 px-3 font-mono">{row.label}</td>
                  <td className="py-1.5 px-3 text-right font-medium tabular-nums">
                    {formatTokens(row.calls)}
                  </td>
                  <td className="py-1.5 px-3 text-right font-medium text-[var(--danger)] tabular-nums">
                    {formatTokens(row.errors)}
                  </td>
                  <td className="py-1.5 px-3 text-right font-medium text-[var(--success)] tabular-nums">
                    {formatTokens(row.cache_hits)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.6} />
              <XAxis
                dataKey="label"
                stroke="var(--text-muted)"
                fontSize={10}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                stroke="var(--text-muted)"
                fontSize={10}
                tickLine={false}
                axisLine={false}
                allowDecimals={false}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "var(--surface-raised)",
                  borderColor: "var(--border)",
                  borderRadius: "8px",
                  fontSize: "12px",
                  color: "var(--text)",
                }}
              />
              <Legend
                verticalAlign="top"
                height={28}
                iconType="circle"
                wrapperStyle={{ fontSize: "11px", color: "var(--text-muted)" }}
              />
              <Bar dataKey="calls" name="Total Calls" fill="#6E6AFF" radius={[4, 4, 0, 0]} />
              <Bar dataKey="errors" name="Errors" fill="#F5555D" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
