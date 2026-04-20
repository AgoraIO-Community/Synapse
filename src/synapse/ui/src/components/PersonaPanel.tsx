/**
 * PersonaPanel — manage user-defined personas (create, edit, delete).
 * Shown as a collapsible panel above the task board.
 */

import { useState } from "react";
import type { Persona } from "../types";
import {
  createPersona,
  deletePersona,
  updatePersona,
} from "../lib/session-client";
import { PixelPersona, taskStatusToPersonaState, AVATAR_IMAGES } from "./PixelPersona";

interface PersonaPanelProps {
  sessionId: string;
  personas: Persona[];
  onRefresh: () => void;
}

export function PersonaPanel({ sessionId, personas, onRefresh }: PersonaPanelProps) {
  const [isAdding, setIsAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [avatar, setAvatar] = useState(AVATAR_IMAGES[0]);
  const [basePrompt, setBasePrompt] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleCreate() {
    if (!name.trim()) return;
    setError(null);
    try {
      await createPersona(sessionId, { name: name.trim(), avatar, base_prompt: basePrompt });
      setName("");
      setBasePrompt("");
      setIsAdding(false);
      onRefresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create persona");
    }
  }

  async function handleDelete(personaId: string) {
    setError(null);
    try {
      await deletePersona(sessionId, personaId);
      onRefresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to delete persona");
    }
  }

  async function handleUpdate(personaId: string) {
    setError(null);
    try {
      await updatePersona(sessionId, personaId, {
        name: name.trim() || undefined,
        avatar,
        base_prompt: basePrompt,
      });
      setEditingId(null);
      setName("");
      setBasePrompt("");
      onRefresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to update persona");
    }
  }

  function startEdit(p: Persona) {
    setEditingId(p.persona_id);
    setName(p.name);
    setAvatar(p.avatar || AVATAR_IMAGES[0]);
    setBasePrompt(p.base_prompt || "");
    setIsAdding(false);
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-white/80">
          Bros ({personas.length})
        </h3>
        {!isAdding && !editingId && (
          <button
            onClick={() => { setIsAdding(true); setName(""); setBasePrompt(""); }}
            className="text-xs font-medium text-blue-400 hover:text-blue-300"
          >
            + New Bro
          </button>
        )}
      </div>

      {error && (
        <div className="rounded bg-red-900/40 px-2 py-1 text-xs text-red-300">{error}</div>
      )}

      {/* Persona list */}
      <div className="flex flex-wrap gap-3">
        {personas.map((p) => (
          <div
            key={p.persona_id}
            className="group relative flex flex-col items-center gap-1 rounded-lg bg-[#1e2024] border border-white/10 px-3 py-2 hover:bg-[#262930] cursor-pointer"
            onClick={() => editingId !== p.persona_id && startEdit(p)}
          >
            <PixelPersona
              name={p.name}
              avatar={p.avatar}
              state={p.status === "busy" ? "working" : "idle"}
              size={40}
            />
            <span className="text-[0.6rem] font-medium text-white/60">
              {p.status === "busy" ? "busy" : "idle"}
            </span>
            {p.status === "idle" && (
              <button
                onClick={(e) => { e.stopPropagation(); handleDelete(p.persona_id); }}
                className="absolute -right-1 -top-1 hidden rounded-full bg-red-600 px-1 text-[0.5rem] text-white group-hover:block"
              >
                ✕
              </button>
            )}
          </div>
        ))}
      </div>

      {/* Add / Edit form */}
      {(isAdding || editingId) && (
        <div className="space-y-2 rounded-lg bg-[#1e2024] border border-white/10 p-3">
          <input
            type="text"
            placeholder="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded bg-[#2a2d33] border border-white/15 px-2 py-1.5 text-sm text-white placeholder-white/40 outline-none focus:ring-1 focus:ring-blue-500"
          />
          <div className="flex gap-2">
            {AVATAR_IMAGES.map((a) => (
              <button
                key={a}
                onClick={() => setAvatar(a)}
                className={`rounded-full overflow-hidden ${avatar === a ? "ring-2 ring-blue-500" : "ring-1 ring-white/10 hover:ring-white/30"}`}
                style={{ width: 36, height: 36 }}
              >
                <img src={a} alt="" className="h-full w-full object-cover" draggable={false} />
              </button>
            ))}
          </div>
          <textarea
            placeholder="Base prompt (personality / instructions for this worker)"
            value={basePrompt}
            onChange={(e) => setBasePrompt(e.target.value)}
            rows={2}
            className="w-full rounded bg-[#2a2d33] border border-white/15 px-2 py-1.5 text-sm text-white placeholder-white/40 outline-none focus:ring-1 focus:ring-blue-500"
          />
          <div className="flex gap-2">
            {isAdding ? (
              <button
                onClick={handleCreate}
                disabled={!name.trim()}
                className="rounded bg-blue-600 px-3 py-1 text-xs text-white hover:bg-blue-500 disabled:opacity-40"
              >
                Create
              </button>
            ) : (
              <button
                onClick={() => editingId && handleUpdate(editingId)}
                className="rounded bg-blue-600 px-3 py-1 text-xs text-white hover:bg-blue-500"
              >
                Save
              </button>
            )}
            <button
              onClick={() => { setIsAdding(false); setEditingId(null); }}
              className="rounded bg-white/10 px-3 py-1 text-xs text-white/60 hover:bg-white/20"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
