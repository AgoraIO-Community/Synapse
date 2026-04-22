/**
 * CommunicationPersonaConfig — editable prompt that controls the
 * communication brain's personality / tone / style for future sessions.
 */

import { useEffect, useState } from "react";
import { getSessionConfig, putSessionConfig } from "../lib/session-client";

interface Props {
  sessionId: string;
  currentSessionValue: string;
}

export function CommunicationPersonaConfig({ sessionId, currentSessionValue }: Props) {
  const [value, setValue] = useState("");
  const [persistedValue, setPersistedValue] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(true);
  const dirty = value !== persistedValue;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setStatus(null);
    void getSessionConfig(sessionId, "communication_persona_prompt")
      .then((response) => {
        if (cancelled) {
          return;
        }
        const nextValue = response.value ?? "";
        setPersistedValue(nextValue);
        setValue(nextValue);
      })
      .catch((nextError: unknown) => {
        if (cancelled) {
          return;
        }
        setError(nextError instanceof Error ? nextError.message : "Failed to load saved persona");
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  async function handleSave() {
    setSaving(true);
    setError(null);
    setStatus(null);
    try {
      await putSessionConfig(sessionId, "communication_persona_prompt", value);
      setPersistedValue(value);
      setStatus("Saved. This change applies to the next session.");
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
            Controls the communication brain's personality, tone, and style for new sessions.
          </p>
          <p className="text-[0.68rem] leading-4 text-white/40">
            Current session persona:
            {" "}
            {currentSessionValue.trim() ? "frozen at session start" : "default behavior"}
          </p>
          <textarea
            placeholder="e.g. You are a friendly and concise assistant who speaks casually in Chinese."
            value={value}
            onChange={(e) => setValue(e.target.value)}
            rows={3}
            disabled={loading}
            className="w-full rounded bg-[#2a2d33] border border-white/15 px-2 py-1.5 text-sm text-white placeholder-white/40 outline-none focus:ring-1 focus:ring-blue-500"
          />
          {error && (
            <div className="rounded bg-red-900/40 px-2 py-1 text-xs text-red-300">{error}</div>
          )}
          {status && (
            <div className="rounded bg-emerald-900/30 px-2 py-1 text-xs text-emerald-300">{status}</div>
          )}
          <div className="flex gap-2">
            <button
              onClick={handleSave}
              disabled={loading || !dirty || saving}
              className="rounded bg-blue-600 px-3 py-1 text-xs text-white hover:bg-blue-500 disabled:opacity-40"
            >
              {saving ? "Saving…" : "Save"}
            </button>
            {dirty && (
              <button
                onClick={() => {
                  setValue(persistedValue);
                  setStatus(null);
                }}
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
