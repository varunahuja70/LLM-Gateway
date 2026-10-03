"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Bell,
  Cpu,
  FolderGit2,
  LayoutDashboard,
  ListFilter,
  LogOut,
  Settings,
  Shield,
} from "lucide-react";
import { useAuth, useLogout } from "@/lib/queries";

const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/projects", label: "Projects", icon: FolderGit2 },
  { href: "/requests", label: "Requests", icon: ListFilter },
  { href: "/models", label: "Models", icon: Cpu },
  { href: "/alerts", label: "Budgets & Alerts", icon: Bell },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar({ onClose }: { onClose?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const { data: user } = useAuth();
  const logoutMutation = useLogout();

  const handleLogout = async () => {
    await logoutMutation.mutateAsync();
    router.push("/login");
  };

  return (
    <aside className="flex h-full w-64 flex-col border-r border-[var(--border)] bg-[var(--surface)] select-none">
      {/* Brand logo */}
      <div className="flex h-14 items-center gap-2.5 border-b border-[var(--border)] px-5">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--accent)] text-white shadow-xs">
          <Shield className="h-4 w-4" />
        </div>
        <div className="flex flex-col">
          <span className="font-semibold text-sm tracking-tight text-[var(--text)]">
            LLM Gateway
          </span>
          <span className="text-[10px] text-[var(--text-muted)] tracking-wide uppercase font-mono">
            Self-Hosted
          </span>
        </div>
      </div>

      {/* Navigation menu */}
      <nav className="flex-1 space-y-1 p-3">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onClose}
              className={`flex items-center gap-3 rounded-md px-3 py-2 text-xs font-medium transition-colors ${
                isActive
                  ? "bg-[var(--accent)]/10 text-[var(--accent)] font-semibold"
                  : "text-[var(--text-muted)] hover:bg-[var(--muted)] hover:text-[var(--text)]"
              }`}
            >
              <Icon className="h-4 w-4" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Bottom user profile & logout */}
      <div className="border-t border-[var(--border)] p-3">
        <div className="flex items-center justify-between rounded-md p-2 hover:bg-[var(--muted)] transition-colors">
          <div className="flex flex-col overflow-hidden pr-2">
            <span className="truncate text-xs font-medium text-[var(--text)]">
              {user?.email || "Owner"}
            </span>
            <span className="text-[10px] text-[var(--text-muted)]">
              Administrator
            </span>
          </div>
          <button
            onClick={handleLogout}
            title="Log out"
            className="rounded p-1 text-[var(--text-muted)] hover:text-[var(--danger)] transition-colors"
            aria-label="Log out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
