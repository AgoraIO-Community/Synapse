import type { BroCardModel, RuntimePersonaInput } from "./types";
import { sampleBros } from "./data";

const avatarCycle = ["fox", "cat", "bunny", "bro"] as const;

function hashValue(value: string) {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash;
}

function selectAvatarType(persona: RuntimePersonaInput): BroCardModel["avatarType"] {
  const seed = `${persona.persona_id}:${persona.name}:${persona.avatar ?? ""}`;
  return avatarCycle[hashValue(seed) % avatarCycle.length];
}

function buildBusyDetails(persona: RuntimePersonaInput) {
  const taskHandle = persona.current_task_id ? persona.current_task_id.slice(0, 8) : "current queue";
  return [
    `Tracking live runtime work for ${taskHandle}.`,
    "Preparing the next handoff and status update.",
    "Waiting for the operator to continue or redirect the task.",
  ];
}

function buildIdleDetails() {
  return [
    "Ready to pick up the next runtime assignment.",
    "Available for routing, synthesis, or follow-up work.",
  ];
}

export function buildBroCardModels(personas?: RuntimePersonaInput[] | null): BroCardModel[] {
  if (!personas || personas.length === 0) {
    return sampleBros;
  }

  return personas.map((persona) => {
    const busy = persona.status === "busy" || persona.current_task_id !== null;
    const progress = busy ? 42 + (hashValue(persona.persona_id) % 37) : 0;
    return {
      id: persona.persona_id,
      name: persona.name.trim() || "Unnamed Bro",
      role: busy ? "Runtime operator" : "Runtime standby",
      status: busy ? "busy" : "idle",
      avatarType: selectAvatarType(persona),
      taskTitle: busy ? "Handle active runtime work" : "Waiting for assignment",
      progress,
      progressLabel: busy ? `${progress}% synced` : "Idle",
      progressDetails: busy ? buildBusyDetails(persona) : buildIdleDetails(),
      idleNote: busy
        ? "Currently following runtime state and preparing the next move."
        : "Available to pick up the next session task.",
      source: "runtime",
    };
  });
}
