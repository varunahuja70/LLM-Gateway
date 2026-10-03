"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Shield, Check, X, AlertCircle } from "lucide-react";
import { useSetup, useSetupStatus } from "@/lib/queries";

export default function SetupPage() {
  const router = useRouter();
  const { data: setupStatus, isLoading: isStatusLoading } = useSetupStatus();
  const setupMutation = useSetup();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isStatusLoading && setupStatus?.setup_completed) {
      router.replace("/login");
    }
  }, [setupStatus, isStatusLoading, router]);

  const hasLength = password.length >= 12;
  const passwordsMatch = password === confirmPassword && confirmPassword.length > 0;
  const isValid = hasLength && passwordsMatch && email.includes("@");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValid || setupMutation.isPending) return;
    setError(null);

    try {
      await setupMutation.mutateAsync({ email, password });
      router.replace("/");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to complete setup. Please check your credentials.");
      }
    }
  };

  if (isStatusLoading) {
    return null;
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--background)] p-4">
      <div className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] p-8 shadow-xl">
        <div className="flex flex-col items-center text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--accent)] text-white shadow-md mb-4">
            <Shield className="h-6 w-6" />
          </div>
          <h1 className="text-xl font-bold tracking-tight text-[var(--text)]">
            Welcome to LLM Gateway
          </h1>
          <p className="mt-1 text-xs text-[var(--text-muted)] max-w-xs">
            Create the primary administrator account to secure your self-hosted gateway instance.
          </p>
        </div>

        {error && (
          <div className="mt-6 flex items-start gap-2.5 rounded-lg bg-[var(--danger)]/10 p-3 text-xs text-[var(--danger)]">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">
              Owner Email
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="owner@example.com"
              className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
              autoFocus
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">
              Admin Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 12 characters"
              className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">
              Confirm Password
            </label>
            <input
              type="password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Re-enter password"
              className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
            />
          </div>

          {/* Password strength checks */}
          <div className="rounded-md bg-[var(--surface)] p-3 text-xs space-y-1.5 border border-[var(--border)]">
            <div className="flex items-center gap-2">
              {hasLength ? (
                <Check className="h-3.5 w-3.5 text-[var(--success)]" />
              ) : (
                <X className="h-3.5 w-3.5 text-[var(--text-muted)]" />
              )}
              <span className={hasLength ? "text-[var(--text)]" : "text-[var(--text-muted)]"}>
                Minimum 12 characters
              </span>
            </div>
            <div className="flex items-center gap-2">
              {passwordsMatch ? (
                <Check className="h-3.5 w-3.5 text-[var(--success)]" />
              ) : (
                <X className="h-3.5 w-3.5 text-[var(--text-muted)]" />
              )}
              <span className={passwordsMatch ? "text-[var(--text)]" : "text-[var(--text-muted)]"}>
                Passwords match
              </span>
            </div>
          </div>

          <button
            type="submit"
            disabled={!isValid || setupMutation.isPending}
            className={`w-full rounded-md bg-[var(--accent)] py-2.5 text-xs font-semibold text-white shadow-xs transition-colors ${
              !isValid || setupMutation.isPending
                ? "opacity-50 cursor-not-allowed"
                : "hover:bg-[var(--accent-hover)]"
            }`}
          >
            {setupMutation.isPending ? "Configuring Gateway..." : "Create Owner Account"}
          </button>
        </form>
      </div>
    </div>
  );
}
