"use client";

import { ReactNode, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "./header";
import { Sidebar } from "./sidebar";
import { DemoBanner } from "@/components/shared/DemoBanner";
import { useAuth, useSettings, useSetupStatus } from "@/lib/queries";

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);

  const { data: setupStatus, isLoading: isSetupLoading } = useSetupStatus();
  const { data: user, isLoading: isAuthLoading } = useAuth();
  const { data: settings } = useSettings();

  useEffect(() => {
    // Use is_setup as primary field (setup_completed is a legacy alias)
    const isSetup = setupStatus
      ? Boolean(setupStatus.is_setup ?? setupStatus.setup_completed)
      : undefined;

    if (!isSetupLoading && setupStatus && !isSetup) {
      router.replace("/setup");
      return;
    }

    if (!isAuthLoading && !user && isSetup) {
      router.replace("/login");
    }
  }, [user, isAuthLoading, setupStatus, isSetupLoading, router]);

  if (isSetupLoading || isAuthLoading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-[var(--background)]">
        <div className="flex flex-col items-center gap-3">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-[var(--accent)] border-t-transparent" />
          <span className="text-xs text-[var(--text-muted)]">Loading Gateway...</span>
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[var(--background)]">
      {/* Desktop sidebar */}
      <div className="hidden md:flex md:shrink-0">
        <Sidebar />
      </div>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden">
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity"
            onClick={() => setMobileOpen(false)}
          />
          <div className="relative flex w-64 flex-1 flex-col">
            <Sidebar onClose={() => setMobileOpen(false)} />
          </div>
        </div>
      )}

      {/* Main content body */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {settings?.demo_mode && (
          <DemoBanner hasSampleData={settings.demo_banner.has_sample_data} />
        )}
        <Header onOpenMobileMenu={() => setMobileOpen(true)} />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <div className="mx-auto max-w-7xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
