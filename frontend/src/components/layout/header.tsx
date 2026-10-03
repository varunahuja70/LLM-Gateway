"use client";

import { Menu } from "lucide-react";

interface HeaderProps {
  onOpenMobileMenu: () => void;
  title?: string;
}

export function Header({ onOpenMobileMenu, title }: HeaderProps) {
  return (
    <header className="flex h-14 items-center justify-between border-b border-[var(--border)] bg-[var(--surface)] px-4 sm:px-6">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onOpenMobileMenu}
          className="rounded-md p-1.5 text-[var(--text-muted)] hover:bg-[var(--muted)] hover:text-[var(--text)] md:hidden"
          aria-label="Open sidebar menu"
        >
          <Menu className="h-5 w-5" />
        </button>
        {title && (
          <h1 className="text-sm font-semibold text-[var(--text)]">
            {title}
          </h1>
        )}
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 text-xs text-[var(--text-muted)] font-mono">
          <span className="h-2 w-2 rounded-full bg-[var(--success)] animate-pulse" />
          <span>Gateway Online</span>
        </div>
      </div>
    </header>
  );
}
