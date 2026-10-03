"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Shield, AlertCircle } from "lucide-react";
import { useAuth, useLogin, useSetupStatus } from "@/lib/queries";

export default function LoginPage() {
  const router = useRouter();
  const { data: setupStatus, isLoading: isStatusLoading } = useSetupStatus();
  const { data: user, isLoading: isAuthLoading } = useAuth();
  const loginMutation = useLogin();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isStatusLoading && setupStatus && !setupStatus.setup_completed) {
      router.replace("/setup");
      return;
    }

    if (!isAuthLoading && user) {
      router.replace("/");
    }
  }, [setupStatus, isStatusLoading, user, isAuthLoading, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password || loginMutation.isPending) return;
    setError(null);

    try {
      await loginMutation.mutateAsync({ email, password });
      router.replace("/");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Invalid email or password.");
      }
    }
  };

  if (isStatusLoading || isAuthLoading) {
    return null;
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--background)] p-4">
      <div className="w-full max-w-sm rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] p-8 shadow-xl">
        <div className="flex flex-col items-center text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[var(--accent)] text-white shadow-md mb-3.5">
            <Shield className="h-5 w-5" />
          </div>
          <h1 className="text-lg font-bold tracking-tight text-[var(--text)]">
            Sign In to LLM Gateway
          </h1>
          <p className="mt-1 text-xs text-[var(--text-muted)]">
            Enter your credentials to access the admin dashboard.
          </p>
        </div>

        {error && (
          <div className="mt-5 flex items-start gap-2.5 rounded-lg bg-[var(--danger)]/10 p-3 text-xs text-[var(--danger)]">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">
              Email Address
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
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
            />
          </div>

          <button
            type="submit"
            disabled={!email || !password || loginMutation.isPending}
            className={`w-full rounded-md bg-[var(--accent)] py-2.5 text-xs font-semibold text-white shadow-xs transition-colors ${
              !email || !password || loginMutation.isPending
                ? "opacity-50 cursor-not-allowed"
                : "hover:bg-[var(--accent-hover)]"
            }`}
          >
            {loginMutation.isPending ? "Signing in..." : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}
