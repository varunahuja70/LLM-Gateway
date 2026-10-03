"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";

interface CodeSnippetProps {
  code: string;
  language?: string;
  filename?: string;
}

export function CodeSnippet({ code, language = "bash", filename }: CodeSnippetProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  return (
    <div className="relative rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] overflow-hidden">
      {(filename || language) && (
        <div className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs text-[var(--text-muted)]">
          <span className="font-mono">{filename || language}</span>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 text-[var(--text-muted)] hover:text-[var(--text)] transition-colors"
            aria-label="Copy code"
          >
            {copied ? (
              <>
                <Check className="h-3 w-3 text-[var(--success)]" />
                <span>Copied</span>
              </>
            ) : (
              <>
                <Copy className="h-3 w-3" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      )}
      <div className="p-3.5 overflow-x-auto font-mono text-xs text-[var(--text)] leading-relaxed select-all">
        <pre className="m-0 whitespace-pre">
          <code>{code}</code>
        </pre>
      </div>
      {!filename && !language && (
        <button
          onClick={handleCopy}
          className="absolute top-2 right-2 rounded-md bg-[var(--muted)] p-1.5 text-[var(--text-muted)] hover:text-[var(--text)] transition-colors"
          aria-label="Copy code"
        >
          {copied ? <Check className="h-3.5 w-3.5 text-[var(--success)]" /> : <Copy className="h-3.5 w-3.5" />}
        </button>
      )}
    </div>
  );
}
