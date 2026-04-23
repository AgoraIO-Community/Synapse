import type { BroCardModel, RuntimeExecutorNodeInput, RuntimePersonaInput } from "./types";
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

function buildLiveState(
  persona: RuntimePersonaInput,
  nodesById: Map<string, RuntimeExecutorNodeInput>,
): BroCardModel["liveState"] {
  if (!persona.executor_node_id) {
    return "unbound";
  }
  const node = nodesById.get(persona.executor_node_id);
  if (node?.connection_status === "connected") {
    return "live";
  }
  return "offline";
}

function buildBusyDetails(
  persona: RuntimePersonaInput,
  liveState: BroCardModel["liveState"],
  nodeName: string | null,
) {
  const taskHandle = persona.current_task_id ? persona.current_task_id.slice(0, 8) : "current queue";
  const nodeLabel = nodeName ?? "an unbound route";
  return [
    `Tracking live runtime work for ${taskHandle}.`,
    "Preparing the next handoff and status update.",
    liveState === "live"
      ? `Bound to ${nodeLabel} and ready for local execution.`
      : liveState === "offline"
        ? `${nodeLabel} is offline, so this bro is standing by for reconnection.`
        : "Needs an executor node binding before this bro can go live.",
  ];
}

function buildIdleDetails(liveState: BroCardModel["liveState"], nodeName: string | null) {
  const nodeLabel = nodeName ?? "an executor node";
  return [
    "Ready to pick up the next runtime assignment.",
    liveState === "live"
      ? `Available for routing through ${nodeLabel}.`
      : liveState === "offline"
        ? `Bound to ${nodeLabel}, but waiting for it to reconnect.`
        : "Bind this bro to an executor node to make it live.",
  ];
}

function buildIdleNote(liveState: BroCardModel["liveState"], nodeName: string | null): string {
  const nodeLabel = nodeName ?? "a node";
  if (liveState === "live") {
    return `${nodeLabel} is connected. This bro can pick up the next task immediately.`;
  }
  if (liveState === "offline") {
    return `${nodeLabel} is assigned but offline. This bro will stay dark until it reconnects.`;
  }
  return "No executor node is bound yet. Bind one from Bros or Nodes to bring this bro online.";
}

export function buildBroCardModels(
  personas?: RuntimePersonaInput[] | null,
  executorNodes?: RuntimeExecutorNodeInput[] | null,
): BroCardModel[] {
  if (!personas || personas.length === 0) {
    return sampleBros;
  }
  const nodesById = new Map((executorNodes ?? []).map((node) => [node.node_id, node]));

  return personas.map((persona) => {
    const busy = persona.status === "busy" || persona.current_task_id !== null;
    const progress = busy ? 42 + (hashValue(persona.persona_id) % 37) : 0;
    const nodeName = persona.executor_node_id ? (nodesById.get(persona.executor_node_id)?.name ?? null) : null;
    const liveState = buildLiveState(persona, nodesById);
    return {
      id: persona.persona_id,
      name: persona.name.trim() || "Unnamed Bro",
      role: busy ? "Runtime operator" : "Runtime standby",
      status: busy ? "busy" : "idle",
      liveState,
      executorNodeId: persona.executor_node_id,
      nodeName,
      avatarType: selectAvatarType(persona),
      taskTitle: busy ? "Handle active runtime work" : "Waiting for assignment",
      progress,
      progressLabel: busy ? `${progress}% synced` : "Idle",
      progressDetails: busy
        ? buildBusyDetails(persona, liveState, nodeName)
        : buildIdleDetails(liveState, nodeName),
      idleNote: busy
        ? buildIdleNote(liveState, nodeName)
        : buildIdleNote(liveState, nodeName),
      source: "runtime",
    };
  });
}
