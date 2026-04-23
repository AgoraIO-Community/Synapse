/**
 * BrosPage — full-page management view for communication brain persona
 * and worker bro configuration. Matches the newbro design language.
 */

import { useEffect, useState } from "react";
import { Plus, Pencil, Trash2, Brain } from "lucide-react";
import {
  createPersona,
  deletePersona,
  listPersonas,
  updatePersona,
  getSessionConfig,
  putSessionConfig,
} from "../../lib/session-client";
import { SectionHeader } from "./SectionHeader";
import { BroPortrait } from "./BroPortrait";
import type { BroCardModel, AvatarType } from "./types";
import type { Persona } from "../../types";

/* ------------------------------------------------------------------ */
/*  Communication Brain Persona                                       */
/* ------------------------------------------------------------------ */

function CommBrainSection({
  sessionId,
  initialValue,
  onSaved,
}: {
  sessionId: string;
  initialValue: string;
  onSaved?: () => void;
}) {
  const [value, setValue] = useState(initialValue);
  const [savedValue, setSavedValue] = useState(initialValue);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dirty = value !== savedValue;

  // Load the persisted (next-session) value on mount.
  useEffect(() => {
    let active = true;
    getSessionConfig(sessionId, "communication_persona_prompt")
      .then((result) => {
        if (!active) return;
        const persisted = result.value ?? "";
        setValue(persisted);
        setSavedValue(persisted);
      })
      .catch(() => {});
    return () => { active = false; };
  }, [sessionId]);

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await putSessionConfig(sessionId, "communication_persona_prompt", value);
      setSavedValue(value);
      setSaved(true);
      onSaved?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded-[24px] border border-neutral-200 bg-white px-6 py-5">
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-full border border-neutral-200 bg-[#f7f5f0]">
          <Brain className="h-4 w-4 text-neutral-600" strokeWidth={1.8} />
        </div>
        <div>
          <div className="text-[14px] font-medium text-neutral-900">Communication Persona</div>
          <div className="text-[12px] text-neutral-500">
            Controls the conversation brain's tone and style
          </div>
        </div>
      </div>

      <textarea
        placeholder="e.g. You are a friendly and concise assistant who speaks casually in Chinese."
        value={value}
        onChange={(e) => { setValue(e.target.value); setSaved(false); }}
        rows={3}
        className="w-full rounded-2xl border border-neutral-200 bg-[#f7f5f0] px-4 py-3 text-[14px] text-neutral-900 placeholder-neutral-400 outline-none transition focus:border-neutral-400 focus:ring-1 focus:ring-neutral-300"
      />

      {error && (
        <div className="mt-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-600">
          {error}
        </div>
      )}
      {saved && (
        <div className="mt-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-[12px] text-emerald-700">
          Saved. Takes effect on the next session.
        </div>
      )}

      <div className="mt-3 flex items-center gap-2">
        <button
          onClick={handleSave}
          disabled={!dirty || saving}
          className="rounded-full border border-neutral-900 bg-neutral-950 px-4 py-1.5 text-[12px] font-medium text-white transition hover:bg-neutral-800 disabled:opacity-30"
        >
          {saving ? "Saving…" : "Save"}
        </button>
        {dirty && (
          <button
            onClick={() => { setValue(savedValue); setSaved(false); }}
            className="rounded-full border border-neutral-200 px-4 py-1.5 text-[12px] font-medium text-neutral-600 transition hover:bg-neutral-100"
          >
            Reset
          </button>
        )}
      </div>
    </div>
  );
}


/* ------------------------------------------------------------------ */
/*  Worker Bro Form                                                   */
/* ------------------------------------------------------------------ */

const AVATAR_TYPES = ["fox", "cat", "bunny", "bro"] as const;

function BroForm({
  initial,
  onSubmit,
  onCancel,
  submitLabel,
}: {
  initial?: { name: string; basePrompt: string; avatarType: string };
  onSubmit: (data: { name: string; basePrompt: string; avatarType: string }) => void;
  onCancel: () => void;
  submitLabel: string;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [basePrompt, setBasePrompt] = useState(initial?.basePrompt ?? "");
  const [avatarType, setAvatarType] = useState(initial?.avatarType ?? "fox");

  return (
    <div className="space-y-3 rounded-[24px] border border-neutral-200 bg-white px-6 py-5">
      <input
        type="text"
        placeholder="Bro name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        className="w-full rounded-2xl border border-neutral-200 bg-[#f7f5f0] px-4 py-2.5 text-[14px] text-neutral-900 placeholder-neutral-400 outline-none transition focus:border-neutral-400 focus:ring-1 focus:ring-neutral-300"
      />

      <div className="flex gap-2">
        {AVATAR_TYPES.map((type) => (
          <button
            key={type}
            type="button"
            onClick={() => setAvatarType(type)}
            className={`rounded-[14px] border px-3 py-1.5 text-[11px] uppercase tracking-[0.14em] transition ${
              avatarType === type
                ? "border-neutral-900 bg-neutral-950 text-white"
                : "border-neutral-200 bg-[#f7f5f0] text-neutral-600 hover:border-neutral-300"
            }`}
          >
            {type}
          </button>
        ))}
      </div>

      <textarea
        placeholder="Base prompt — personality and instructions for this worker"
        value={basePrompt}
        onChange={(e) => setBasePrompt(e.target.value)}
        rows={2}
        className="w-full rounded-2xl border border-neutral-200 bg-[#f7f5f0] px-4 py-3 text-[14px] text-neutral-900 placeholder-neutral-400 outline-none transition focus:border-neutral-400 focus:ring-1 focus:ring-neutral-300"
      />

      <div className="flex gap-2">
        <button
          onClick={() => onSubmit({ name: name.trim(), basePrompt, avatarType })}
          disabled={!name.trim()}
          className="rounded-full border border-neutral-900 bg-neutral-950 px-4 py-1.5 text-[12px] font-medium text-white transition hover:bg-neutral-800 disabled:opacity-30"
        >
          {submitLabel}
        </button>
        <button
          onClick={onCancel}
          className="rounded-full border border-neutral-200 px-4 py-1.5 text-[12px] font-medium text-neutral-600 transition hover:bg-neutral-100"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Worker Bro Row                                                    */
/* ------------------------------------------------------------------ */

const VALID_AVATARS = new Set<string>(["fox", "cat", "bunny", "bro"]);

function personaToBroCard(persona: Persona): BroCardModel {
  const avatarType: AvatarType = VALID_AVATARS.has(persona.avatar) ? (persona.avatar as AvatarType) : "bro";
  return {
    id: persona.persona_id,
    name: persona.name,
    role: "",
    status: "idle",
    avatarType,
    taskTitle: "",
    progress: 0,
    progressLabel: "",
    progressDetails: [],
    idleNote: "",
    source: "runtime",
  };
}

function BroRow({
  persona,
  onEdit,
  onDelete,
}: {
  persona: Persona;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const avatarType = VALID_AVATARS.has(persona.avatar) ? persona.avatar : "bro";

  return (
    <div className="flex items-center gap-4 rounded-[24px] border border-neutral-200 bg-white px-5 py-4 transition hover:border-neutral-300">
      <BroPortrait bro={personaToBroCard(persona)} talking={false} />

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <div className="text-[15px] font-medium tracking-[-0.02em] text-neutral-900">
            {persona.name}
          </div>
          <div className="rounded-full border border-neutral-200 bg-[#f6f5f2] px-2 py-0.5 text-[10px] uppercase tracking-[0.16em] text-neutral-600">
            {avatarType}
          </div>
        </div>
        {persona.base_prompt ? (
          <div className="mt-1 line-clamp-2 text-[12px] leading-relaxed text-neutral-500">
            {persona.base_prompt}
          </div>
        ) : (
          <div className="mt-1 text-[12px] italic text-neutral-400">No prompt configured</div>
        )}
      </div>

      <div className="flex shrink-0 gap-1.5">
        <button
          onClick={onEdit}
          className="rounded-full border border-neutral-200 p-2 text-neutral-500 transition hover:border-neutral-300 hover:text-neutral-700"
        >
          <Pencil className="h-3.5 w-3.5" strokeWidth={1.8} />
        </button>
        <button
          onClick={onDelete}
          className="rounded-full border border-neutral-200 p-2 text-neutral-500 transition hover:border-red-300 hover:text-red-600"
        >
          <Trash2 className="h-3.5 w-3.5" strokeWidth={1.8} />
        </button>
      </div>
    </div>
  );
}


/* ------------------------------------------------------------------ */
/*  Main BrosPage                                                     */
/* ------------------------------------------------------------------ */

export function BrosPage({
  sessionId,
  communicationPersonaPrompt,
}: {
  sessionId: string;
  communicationPersonaPrompt: string;
}) {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [mode, setMode] = useState<"list" | "add" | "edit">("list");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  // Load the persisted persona list (from file, not the frozen session).
  async function refreshPersonas() {
    try {
      const result = await listPersonas(sessionId);
      setPersonas(Array.isArray(result) ? result : []);
    } catch {
      // keep whatever we had
    }
  }

  useEffect(() => {
    void refreshPersonas();
  }, [sessionId]);

  async function handleCreate(data: { name: string; basePrompt: string; avatarType: string }) {
    setError(null);
    setStatus(null);
    try {
      await createPersona(sessionId, {
        name: data.name,
        avatar: data.avatarType,
        base_prompt: data.basePrompt,
      });
      setMode("list");
      setStatus("Bro created. Takes effect on the next session.");
      await refreshPersonas();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create");
    }
  }

  async function handleUpdate(data: { name: string; basePrompt: string; avatarType: string }) {
    if (!editingId) return;
    setError(null);
    setStatus(null);
    try {
      await updatePersona(sessionId, editingId, {
        name: data.name,
        avatar: data.avatarType,
        base_prompt: data.basePrompt,
      });
      setMode("list");
      setEditingId(null);
      setStatus("Bro updated. Takes effect on the next session.");
      await refreshPersonas();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to update");
    }
  }

  async function handleDelete(personaId: string) {
    setError(null);
    setStatus(null);
    try {
      await deletePersona(sessionId, personaId);
      setStatus("Bro removed. Takes effect on the next session.");
      await refreshPersonas();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to delete");
    }
  }

  function startEdit(persona: Persona) {
    setEditingId(persona.persona_id);
    setMode("edit");
  }

  return (
    <div className="grid min-h-0 flex-1 grid-cols-1 gap-8 overflow-auto px-8 py-8 lg:grid-cols-[minmax(220px,0.56fr)_minmax(840px,1.74fr)] xl:px-10 xl:py-10">
      {/* Left column — Communication Brain Persona */}
      <section className="flex min-h-0 flex-col pt-4">
        <SectionHeader title="Brain Persona" />
        <CommBrainSection
          sessionId={sessionId}
          initialValue={communicationPersonaPrompt}
        />
      </section>

      {/* Right column — Worker Bros */}
      <section className="flex flex-col items-stretch lg:pt-4">
        <SectionHeader
          title="Worker Bros"
          trailing={
            <div className="flex items-center gap-3">
              <div className="rounded-full border border-neutral-200 px-2.5 py-1 text-[11px] text-neutral-500">
                {personas.length} configured
              </div>
              {!editingId && mode !== "add" && (
                <button
                  onClick={() => { setMode("add"); setEditingId(null); setError(null); setStatus(null); }}
                  className="flex items-center gap-1.5 rounded-full border border-neutral-200 px-3 py-1.5 text-[11px] font-medium text-neutral-600 transition hover:border-neutral-300 hover:bg-white"
                >
                  <Plus className="h-3 w-3" strokeWidth={2} />
                  New Bro
                </button>
              )}
            </div>
          }
        />

        {error && (
          <div className="mb-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-600">
            {error}
          </div>
        )}
        {status && (
          <div className="mb-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-[13px] text-emerald-700">
            {status}
          </div>
        )}

        {mode === "add" && (
          <div className="mb-4">
            <BroForm
              submitLabel="Create"
              onSubmit={handleCreate}
              onCancel={() => setMode("list")}
            />
          </div>
        )}

        <div className="space-y-3">
          {personas.length === 0 && mode !== "add" ? (
            <div className="rounded-[24px] border border-dashed border-neutral-300 bg-white/60 px-6 py-8 text-center">
              <div className="text-[14px] text-neutral-500">No worker bros yet.</div>
              <div className="mt-1 text-[12px] text-neutral-400">
                Create one to start delegating tasks.
              </div>
            </div>
          ) : (
            personas.map((persona) =>
              editingId === persona.persona_id ? (
                <BroForm
                  key={persona.persona_id}
                  initial={{
                    name: persona.name,
                    basePrompt: persona.base_prompt || "",
                    avatarType: VALID_AVATARS.has(persona.avatar) ? persona.avatar : "bro",
                  }}
                  submitLabel="Save"
                  onSubmit={handleUpdate}
                  onCancel={() => { setEditingId(null); setMode("list"); }}
                />
              ) : (
                <BroRow
                  key={persona.persona_id}
                  persona={persona}
                  onEdit={() => startEdit(persona)}
                  onDelete={() => handleDelete(persona.persona_id)}
                />
              ),
            )
          )}
        </div>
      </section>
    </div>
  );
}
