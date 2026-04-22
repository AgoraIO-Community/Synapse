/**
 * CommunicationPersonaConfig — editable prompt that controls the
 * communication brain's personality / tone / style.
 */

import { useEffect, useRef, useState } from "react";
import { putSessionConfig } from "../lib/session-client";

interface Props {
  sessionId: string;
  initialValue: string;
  onSaved?: () => void;
}

export function CommunicationPersonaConfig({ sessionId, initialValue, onSaved }: Props) {
  const [value, setValue] = useState(initialValue);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(true);
  const dirty = value !== initialValue;
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setValue(initialValue);
  }, [initialValue]);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      await putSessionConfig(sessionId, "communication_persona_prompt", value);
      onSaved?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="flex w-full items-center justify-between text-xs font-semibold uppercase tracking-wider text-white/80"
      >
        <span>Communication Persona</span>
        <span className="text-[0.6rem] font-normal normal-case text-white/40">
          {collapsed ? "▸ expand" : "▾ collapse"}
        </span>
      </button>

      {!collapsed && (
        <div className="space-y-2 rounded-lg border border-white/10 bg-[#1e2024] p-3">
          <p className="text-[0.68rem] leading-4 text-white/50">
            Controls the communication brain's personality, tone, and style when talking to you.
          </p>
          <textarea
            ref={textareaRef}
            placeholder="e.g. You are a friendly and concise assistant who speaks casually in Chinese."
            value={value}
            onChange={(e) => setValue(e.target.value)}
            rows={3}
            className="w-full rounded bg-[#2a2d33] border border-white/15 px-2 py-1.5 text-sm text-white placeholder-white/40 outline-none focus:ring-1 focus:ring-blue-500"
          />
          {error && (
            <div className="rounded bg-red-900/40 px-2 py-1 text-xs text-red-300">{error}</div>
          )}
          <div className="flex gap-2">
            <button
              onClick={handleSave}
              disabled={!dirty || saving}
              className="rounded bg-blue-600 px-3 py-1 text-xs text-white hover:bg-blue-500 disabled:opacity-40"
            >
              {saving ? "Saving…" : "Save"}
            </button>
            {dirty && (
              <button
                onClick={() => setValue(initialValue)}
                className="rounded bg-white/10 px-3 py-1 text-xs text-white/60 hover:bg-white/20"
              >
                Reset
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
