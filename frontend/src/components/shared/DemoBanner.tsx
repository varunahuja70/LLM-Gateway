"use client";

import { useState } from "react";
import { Sparkles, Database } from "lucide-react";
import { api } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";

interface DemoBannerProps {
  hasSampleData?: boolean;
}

export function DemoBanner({ hasSampleData = true }: DemoBannerProps) {
  const [loading, setLoading] = useState(false);
  const [seeded, setSeeded] = useState(false);
  const queryClient = useQueryClient();

  const handleLoadDemoData = async () => {
    try {
      setLoading(true);
      await api.post("/admin/settings/seed-demo");
      setSeeded(true);
      queryClient.invalidateQueries();
    } catch {
      // Error handled
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-between gap-4 border-b border-[var(--accent)]/30 bg-[var(--accent)]/10 px-4 py-2 text-xs text-[var(--text)]">
      <div className="flex items-center gap-2">
        <Sparkles className="h-3.5 w-3.5 text-[var(--accent)] shrink-0" />
        <span>
          <strong className="font-semibold text-[var(--accent)]">Demo Mode Active:</strong> The gateway is running with the deterministic mock provider. No real API keys required.
        </span>
      </div>

      {!hasSampleData && !seeded && (
        <button
          onClick={handleLoadDemoData}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-2.5 py-1 text-xs font-medium text-white shadow-xs hover:bg-[var(--accent-hover)] transition-colors disabled:opacity-50"
        >
          <Database className="h-3 w-3" />
          {loading ? "Loading Data..." : "Load Demo Data"}
        </button>
      )}
    </div>
  );
}
