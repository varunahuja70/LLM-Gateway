"use client";

import { useState } from "react";
import { ArrowDown, ArrowUp, Plus, Trash2, ShieldAlert } from "lucide-react";

interface FallbackChainEditorProps {
  chain: string[];
  onChange: (newChain: string[]) => void;
  disabled?: boolean;
}

export function FallbackChainEditor({
  chain,
  onChange,
  disabled = false,
}: FallbackChainEditorProps) {
  const [newModel, setNewModel] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleAdd = () => {
    const trimmed = newModel.trim();
    if (!trimmed) return;

    if (!trimmed.includes("/")) {
      setError("Model name must include provider prefix (e.g. 'openai/gpt-4o-mini')");
      return;
    }

    if (chain.includes(trimmed)) {
      setError("Model is already in the fallback chain");
      return;
    }

    setError(null);
    onChange([...chain, trimmed]);
    setNewModel("");
  };

  const handleRemove = (index: number) => {
    const next = chain.filter((_, i) => i !== index);
    onChange(next);
  };

  const handleMoveUp = (index: number) => {
    if (index <= 0) return;
    const next = [...chain];
    const temp = next[index - 1];
    next[index - 1] = next[index];
    next[index] = temp;
    onChange(next);
  };

  const handleMoveDown = (index: number) => {
    if (index >= chain.length - 1) return;
    const next = [...chain];
    const temp = next[index + 1];
    next[index + 1] = next[index];
    next[index] = temp;
    onChange(next);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-[var(--text-muted)]">
          Ordered Fallback Targets (Attempted in sequence)
        </span>
        <span className="text-xs text-[var(--text-muted)]">{chain.length} models</span>
      </div>

      {chain.length === 0 ? (
        <div className="rounded-lg border border-dashed border-[var(--border)] p-4 text-center text-xs text-[var(--text-muted)]">
          No fallback models configured. If the primary model fails, the request will immediately return an error.
        </div>
      ) : (
        <ul className="space-y-2" role="list">
          {chain.map((model, idx) => (
            <li
              key={model}
              className="flex items-center justify-between rounded-md border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-2 text-xs"
            >
              <div className="flex items-center gap-2.5">
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[var(--surface)] text-[10px] font-mono font-semibold text-[var(--text-muted)]">
                  {idx + 1}
                </span>
                <span className="font-mono text-[var(--text)]">{model}</span>
                {idx === 0 && (
                  <span className="rounded bg-[var(--accent)]/10 px-1.5 py-0.5 text-[10px] font-medium text-[var(--accent)]">
                    Primary Fallback
                  </span>
                )}
              </div>

              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => handleMoveUp(idx)}
                  disabled={idx === 0 || disabled}
                  aria-label={`Move ${model} up`}
                  className="rounded p-1 text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface)] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  <ArrowUp className="h-3.5 w-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => handleMoveDown(idx)}
                  disabled={idx === chain.length - 1 || disabled}
                  aria-label={`Move ${model} down`}
                  className="rounded p-1 text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface)] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  <ArrowDown className="h-3.5 w-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => handleRemove(idx)}
                  disabled={disabled}
                  aria-label={`Remove ${model}`}
                  className="rounded p-1 text-[var(--text-muted)] hover:text-[var(--danger)] hover:bg-[var(--danger)]/10 disabled:opacity-30 transition-colors ml-1"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {error && (
        <div className="flex items-center gap-1.5 text-xs text-[var(--danger)]">
          <ShieldAlert className="h-3.5 w-3.5" />
          <span>{error}</span>
        </div>
      )}

      {!disabled && (
        <div className="flex gap-2 pt-1">
          <input
            type="text"
            value={newModel}
            onChange={(e) => {
              setNewModel(e.target.value);
              if (error) setError(null);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleAdd();
              }
            }}
            placeholder="provider/model (e.g. anthropic/claude-3-5-haiku)"
            className="flex-1 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs text-[var(--text)] focus:border-[var(--accent)] focus:outline-hidden"
          />
          <button
            type="button"
            onClick={handleAdd}
            className="inline-flex items-center gap-1 rounded-md bg-[var(--surface-raised)] border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--text)] hover:bg-[var(--muted)] transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Add Model</span>
          </button>
        </div>
      )}
    </div>
  );
}
