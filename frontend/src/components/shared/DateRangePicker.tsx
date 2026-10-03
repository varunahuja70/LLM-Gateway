"use client";

import { Calendar } from "lucide-react";

export type DateRangePreset = "24h" | "7d" | "30d" | "custom";

interface DateRangePickerProps {
  value: DateRangePreset;
  onChange: (preset: DateRangePreset, from?: string, to?: string) => void;
  from?: string;
  to?: string;
}

export function DateRangePicker({
  value,
  onChange,
  from,
  to,
}: DateRangePickerProps) {
  const handlePreset = (preset: DateRangePreset) => {
    const now = new Date();
    let fromDate: Date;

    if (preset === "24h") {
      fromDate = new Date(now.getTime() - 24 * 60 * 60 * 1000);
      onChange(preset, fromDate.toISOString(), now.toISOString());
    } else if (preset === "7d") {
      fromDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      onChange(preset, fromDate.toISOString(), now.toISOString());
    } else if (preset === "30d") {
      fromDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
      onChange(preset, fromDate.toISOString(), now.toISOString());
    } else {
      onChange("custom", from, to);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-1 text-xs">
      <div className="flex items-center gap-1.5 px-2 text-[var(--text-muted)]">
        <Calendar className="h-3.5 w-3.5" />
        <span className="hidden sm:inline font-medium">Period:</span>
      </div>
      {(["24h", "7d", "30d"] as DateRangePreset[]).map((preset) => (
        <button
          key={preset}
          onClick={() => handlePreset(preset)}
          className={`rounded-md px-2.5 py-1 font-medium transition-colors ${
            value === preset
              ? "bg-[var(--accent)] text-white shadow-xs"
              : "text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-raised)]"
          }`}
        >
          {preset.toUpperCase()}
        </button>
      ))}

      {value === "custom" && (
        <div className="flex items-center gap-1.5 pl-2 border-l border-[var(--border)] text-xs text-[var(--text-muted)]">
          <input
            type="date"
            value={from ? from.split("T")[0] : ""}
            onChange={(e) =>
              onChange("custom", e.target.value ? new Date(e.target.value).toISOString() : undefined, to)
            }
            className="rounded border border-[var(--border)] bg-[var(--surface-raised)] px-1.5 py-0.5 text-xs text-[var(--text)]"
          />
          <span>to</span>
          <input
            type="date"
            value={to ? to.split("T")[0] : ""}
            onChange={(e) =>
              onChange("custom", from, e.target.value ? new Date(e.target.value).toISOString() : undefined)
            }
            className="rounded border border-[var(--border)] bg-[var(--surface-raised)] px-1.5 py-0.5 text-xs text-[var(--text)]"
          />
        </div>
      )}
    </div>
  );
}
