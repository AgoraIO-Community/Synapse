import { useCallback, useEffect, useMemo, useState } from "react";
import { Cable, Copy, KeyRound, Pencil, RotateCcw, Server, Trash2, Plus } from "lucide-react";
import {
  buildExecutorRunCommand,
  createExecutorNode,
  deleteExecutorNode,
  listExecutorNodes,
  listPersonas,
  revealExecutorNodeConnectCommand,
  rotateExecutorNodeCredentials,
  updateExecutorNode,
} from "../../lib/session-client";
import { SectionHeader } from "./SectionHeader";
import type { ExecutorNodeCredentialIssue, ExecutorNodeRecord, Persona } from "../../types";

const EXECUTOR_OPTIONS = ["codex", "acpx"] as const;

function formatTimestamp(value: string | null) {
  if (!value) return "Never";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function NodeForm({
  initial,
  onSubmit,
  onCancel,
  submitLabel,
}: {
  initial?: {
    name: string;
    enabledExecutors: string[];
  };
  onSubmit: (data: { name: string; enabledExecutors: string[] }) => void;
  onCancel: () => void;
  submitLabel: string;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [enabledExecutors, setEnabledExecutors] = useState<string[]>(initial?.enabledExecutors ?? ["codex"]);

  function toggleExecutor(executorType: string) {
    setEnabledExecutors((current) =>
      current.includes(executorType)
        ? current.filter((item) => item !== executorType)
        : [...current, executorType],
    );
  }

  return (
    <div className="space-y-3 rounded-[24px] border border-neutral-200 bg-white px-6 py-5">
      <input
        type="text"
        placeholder="Node name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        className="w-full rounded-2xl border border-neutral-200 bg-[#f7f5f0] px-4 py-2.5 text-[14px] text-neutral-900 placeholder-neutral-400 outline-none transition focus:border-neutral-400 focus:ring-1 focus:ring-neutral-300"
      />

      <div className="space-y-2">
        <div className="text-[12px] uppercase tracking-[0.18em] text-neutral-400">Enabled Executors</div>
        <div className="flex flex-wrap gap-2">
          {EXECUTOR_OPTIONS.map((executorType) => (
            <button
              key={executorType}
              type="button"
              onClick={() => toggleExecutor(executorType)}
              className={`rounded-[14px] border px-3 py-1.5 text-[11px] uppercase tracking-[0.14em] transition ${
                enabledExecutors.includes(executorType)
                  ? "border-neutral-900 bg-neutral-950 text-white"
                  : "border-neutral-200 bg-[#f7f5f0] text-neutral-600 hover:border-neutral-300"
              }`}
            >
              {executorType}
            </button>
          ))}
        </div>
        <div className="text-[12px] leading-5 text-neutral-500">
          Pick the executor families this local machine will advertise to Synapse.
        </div>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() =>
            onSubmit({
              name: name.trim(),
              enabledExecutors,
            })
          }
          disabled={!name.trim() || enabledExecutors.length === 0}
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

function CredentialsPanel({
  issue,
  boundBroCount,
}: {
  issue: ExecutorNodeCredentialIssue;
  boundBroCount: number;
}) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState<string | null>(null);
  const command = buildExecutorRunCommand(issue.node.node_id, issue.token);

  async function handleCopy() {
    const clipboard = navigator.clipboard;
    if (!clipboard?.writeText) {
      throw new Error("Clipboard access is unavailable. Copy the visible command manually.");
    }
    await clipboard.writeText(command);
    setCopied(true);
    setCopyError(null);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <div className="rounded-[28px] border border-neutral-200 bg-white px-6 py-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-[11px] uppercase tracking-[0.22em] text-neutral-400">Enrollment Kit</div>
          <div className="mt-2 text-[28px] font-medium tracking-[-0.04em] text-neutral-950">
            {issue.node.name}
          </div>
          <div className="mt-2 max-w-[640px] text-[13px] leading-6 text-neutral-500">
            Keep this token now. Synapse will not show the raw token again unless you rotate it.
          </div>
        </div>
        <div className="rounded-full border border-neutral-200 bg-[#f6f5f2] px-3 py-1 text-[11px] text-neutral-500">
          {boundBroCount} Bros bound
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.08fr)_minmax(280px,0.92fr)]">
        <div className="space-y-3 rounded-[24px] border border-neutral-200 bg-[#fbfaf7] p-4">
          <div>
            <div className="text-[11px] uppercase tracking-[0.18em] text-neutral-400">Node Id</div>
            <div className="mt-2 rounded-2xl border border-neutral-200 bg-white px-4 py-3 font-mono text-[13px] text-neutral-800">
              {issue.node.node_id}
            </div>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.18em] text-neutral-400">Token</div>
            <div className="mt-2 rounded-2xl border border-neutral-200 bg-white px-4 py-3 font-mono text-[13px] leading-6 text-neutral-800">
              {issue.token}
            </div>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.18em] text-neutral-400">Connect Command</div>
            <div className="mt-2 rounded-2xl border border-neutral-200 bg-white px-4 py-3 font-mono text-[12px] leading-6 text-neutral-800">
              {command}
            </div>
          </div>
        </div>

        <div className="rounded-[24px] border border-neutral-200 bg-neutral-950 px-5 py-5 text-white">
          <div className="text-[11px] uppercase tracking-[0.18em] text-white/55">Local Machine</div>
          <div className="mt-3 text-[18px] font-medium tracking-[-0.03em]">Start the executor node</div>
          <div className="mt-3 space-y-3 text-[13px] leading-6 text-white/75">
            <div>1. Copy the command below onto the client machine that will run the node.</div>
            <div>2. Run it directly to connect back to this Synapse service.</div>
            <div>3. If local executor commands are missing, the run command will prompt for setup in a TTY.</div>
          </div>
          <button
            type="button"
            onClick={() => {
              void handleCopy().catch((error: unknown) => {
                setCopyError(error instanceof Error ? error.message : "Copy failed. Copy the visible command manually.");
              });
            }}
            className="mt-4 flex min-h-[44px] w-full items-center justify-center gap-2 rounded-full border border-white/10 bg-white/10 px-4 py-2 text-[12px] font-medium text-white transition hover:bg-white/15"
          >
            <Copy className="h-3.5 w-3.5" strokeWidth={1.8} />
            {copied ? "Copied" : "Copy connect command"}
          </button>
          {copyError && (
            <div className="mt-3 rounded-[18px] border border-red-400/20 bg-red-500/10 px-4 py-3 text-[12px] leading-5 text-red-100">
              {copyError}
            </div>
          )}
          <div className="mt-4 rounded-[18px] border border-white/10 bg-white/5 px-4 py-3 text-[12px] leading-5 text-white/60">
            The Bro becomes live only after this node connects back to Synapse with the matching node id and token.
          </div>
        </div>
      </div>
    </div>
  );
}

function NodeCard({
  node,
  boundBroCount,
  copied,
  onCopyCommand,
  onEdit,
  onRotate,
  onDelete,
}: {
  node: ExecutorNodeRecord;
  boundBroCount: number;
  copied: boolean;
  onCopyCommand: () => void;
  onEdit: () => void;
  onRotate: () => void;
  onDelete: () => void;
}) {
  const connected = node.connection_status === "connected";

  return (
    <div className="rounded-[26px] border border-neutral-200 bg-white px-5 py-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <div className="text-[18px] font-medium tracking-[-0.03em] text-neutral-950">{node.name}</div>
            <div
              className={`rounded-full border px-2.5 py-0.5 text-[10px] uppercase tracking-[0.16em] ${
                connected
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "border-amber-200 bg-amber-50 text-amber-700"
              }`}
            >
              {connected ? "connected" : "offline"}
            </div>
          </div>
          <div className="mt-2 text-[13px] text-neutral-500">{node.node_id}</div>
        </div>

        <div className="flex flex-wrap justify-end gap-1.5">
          <button
            onClick={onCopyCommand}
            className="flex min-h-[36px] items-center gap-1.5 rounded-full border border-neutral-200 px-3 py-1.5 text-[11px] font-medium text-neutral-600 transition hover:border-neutral-300 hover:bg-neutral-50 hover:text-neutral-800"
          >
            <Copy className="h-3.5 w-3.5" strokeWidth={1.8} />
            {copied ? "Copied" : "Copy command"}
          </button>
          <button
            onClick={onEdit}
            className="rounded-full border border-neutral-200 p-2 text-neutral-500 transition hover:border-neutral-300 hover:text-neutral-700"
          >
            <Pencil className="h-3.5 w-3.5" strokeWidth={1.8} />
          </button>
          <button
            onClick={onRotate}
            className="rounded-full border border-neutral-200 p-2 text-neutral-500 transition hover:border-neutral-300 hover:text-neutral-700"
          >
            <RotateCcw className="h-3.5 w-3.5" strokeWidth={1.8} />
          </button>
          <button
            onClick={onDelete}
            className="rounded-full border border-neutral-200 p-2 text-neutral-500 transition hover:border-red-300 hover:text-red-600"
          >
            <Trash2 className="h-3.5 w-3.5" strokeWidth={1.8} />
          </button>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
        <div className="rounded-[20px] border border-neutral-200 bg-[#fbfaf7] px-4 py-4">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-neutral-400">
            <Server className="h-3.5 w-3.5" strokeWidth={1.8} />
            Executors
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {node.enabled_executors.map((executorType) => (
              <div
                key={executorType}
                className={`rounded-full border px-2.5 py-1 text-[11px] uppercase tracking-[0.14em] ${
                  node.connected_executors.includes(executorType)
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "border-neutral-200 bg-white text-neutral-500"
                }`}
              >
                {executorType}
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-[20px] border border-neutral-200 bg-[#fbfaf7] px-4 py-4">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-neutral-400">
            <Cable className="h-3.5 w-3.5" strokeWidth={1.8} />
            Connection
          </div>
          <div className="mt-3 text-[20px] font-medium tracking-[-0.03em] text-neutral-950">
            {connected ? "Live" : "Waiting"}
          </div>
          <div className="mt-1 text-[12px] leading-5 text-neutral-500">
            Last connected: {formatTimestamp(node.last_connected_at)}
          </div>
        </div>
        <div className="rounded-[20px] border border-neutral-200 bg-[#fbfaf7] px-4 py-4">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-neutral-400">
            <KeyRound className="h-3.5 w-3.5" strokeWidth={1.8} />
            Credentials
          </div>
          <div className="mt-3 text-[13px] leading-6 text-neutral-700">
            <div>Token: {node.token_hint ?? "hidden"}</div>
          </div>
          <div className="mt-1 text-[12px] leading-5 text-neutral-500">
            {boundBroCount} Bros bound · last seen {formatTimestamp(node.last_seen_at)}
          </div>
          <div className="mt-2 text-[12px] leading-5 text-neutral-500">
            {copied ? "Connect command copied." : "Use Copy to reveal and copy the full connect command."}
          </div>
        </div>
      </div>
    </div>
  );
}

export function NodesPage({ sessionId }: { sessionId: string }) {
  const [nodes, setNodes] = useState<ExecutorNodeRecord[]>([]);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [mode, setMode] = useState<"list" | "add" | "edit">("list");
  const [editingNodeId, setEditingNodeId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [latestIssue, setLatestIssue] = useState<ExecutorNodeCredentialIssue | null>(null);
  const [copiedNodeId, setCopiedNodeId] = useState<string | null>(null);

  const refreshData = useCallback(async () => {
    try {
      const [loadedNodes, loadedPersonas] = await Promise.all([
        listExecutorNodes(sessionId),
        listPersonas(sessionId),
      ]);
      setNodes(Array.isArray(loadedNodes) ? loadedNodes : []);
      setPersonas(Array.isArray(loadedPersonas) ? loadedPersonas : []);
    } catch {
      // Preserve current UI on refresh failure.
    }
  }, [sessionId]);

  useEffect(() => {
    void refreshData();
  }, [refreshData]);

  async function handleCreate(data: { name: string; enabledExecutors: string[] }) {
    setError(null);
    setStatus(null);
    try {
      const issue = await createExecutorNode(sessionId, {
        name: data.name,
        enabled_executors: data.enabledExecutors,
      });
      setLatestIssue(issue);
      setMode("list");
      setStatus("Executor node created. Copy the connect command now.");
      await refreshData();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create executor node");
    }
  }

  async function handleUpdate(data: { name: string; enabledExecutors: string[] }) {
    if (!editingNodeId) return;
    setError(null);
    setStatus(null);
    try {
      await updateExecutorNode(sessionId, editingNodeId, {
        name: data.name,
        enabled_executors: data.enabledExecutors,
      });
      setMode("list");
      setEditingNodeId(null);
      setStatus("Executor node updated.");
      await refreshData();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to update executor node");
    }
  }

  async function handleRotate(nodeId: string) {
    setError(null);
    setStatus(null);
    try {
      const issue = await rotateExecutorNodeCredentials(sessionId, nodeId);
      setLatestIssue(issue);
      setStatus("Credentials rotated. Copy the new connect command now.");
      await refreshData();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to rotate credentials");
    }
  }

  async function handleDelete(nodeId: string) {
    setError(null);
    setStatus(null);
    try {
      await deleteExecutorNode(sessionId, nodeId);
      setStatus("Executor node deleted.");
      if (latestIssue?.node.node_id === nodeId) {
        setLatestIssue(null);
      }
      await refreshData();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to delete executor node");
    }
  }

  async function handleCopyCommand(nodeId: string) {
    setError(null);
    setStatus(null);
    try {
      const issue = await revealExecutorNodeConnectCommand(sessionId, nodeId);
      const command = buildExecutorRunCommand(issue.node.node_id, issue.token);
      const clipboard = navigator.clipboard;
      if (!clipboard?.writeText) {
        throw new Error("Clipboard access is unavailable. Copy the visible command manually.");
      }
      await clipboard.writeText(command);
      setLatestIssue(issue);
      setCopiedNodeId(nodeId);
      setStatus("Connect command copied.");
      window.setTimeout(() => setCopiedNodeId((current) => (current === nodeId ? null : current)), 1600);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Failed to copy connect command";
      if (message.includes("Rotate credentials first") || message.includes("legacy non-retrievable")) {
        setError("This node uses older credentials that cannot be revealed. Rotate credentials first.");
      } else {
        setError(message);
      }
    }
  }

  const personaCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const persona of personas) {
      if (!persona.executor_node_id) continue;
      counts.set(persona.executor_node_id, (counts.get(persona.executor_node_id) ?? 0) + 1);
    }
    return counts;
  }, [personas]);

  const connectedCount = nodes.filter((node) => node.connection_status === "connected").length;
  const editingNode = editingNodeId ? nodes.find((node) => node.node_id === editingNodeId) ?? null : null;

  return (
    <div className="space-y-6 overflow-auto px-8 py-8 xl:px-10 xl:py-10">
      <div className="rounded-[30px] border border-neutral-200 bg-white px-6 py-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-[11px] uppercase tracking-[0.22em] text-neutral-400">Executor Nodes</div>
            <div className="mt-2 text-[32px] font-medium tracking-[-0.05em] text-neutral-950">
              Local machine enrollment
            </div>
            <div className="mt-3 max-w-[720px] text-[13px] leading-6 text-neutral-500">
              Create a node, issue its credential pair, and bind Bros to that machine. A Bro only becomes live
              after its bound node reconnects to Synapse with the matching node id and token.
            </div>
          </div>

          {mode === "list" && (
            <button
              onClick={() => {
                setMode("add");
                setEditingNodeId(null);
                setError(null);
                setStatus(null);
              }}
              className="flex min-h-[44px] items-center gap-2 rounded-full border border-neutral-900 bg-neutral-950 px-4 py-2 text-[12px] font-medium text-white transition hover:bg-neutral-800"
            >
              <Plus className="h-3.5 w-3.5" strokeWidth={2} />
              New Node
            </button>
          )}
        </div>

        <div className="mt-6 grid grid-cols-1 gap-3 md:grid-cols-3">
          <div className="rounded-[22px] border border-neutral-200 bg-[#fbfaf7] px-4 py-4">
            <div className="text-[11px] uppercase tracking-[0.18em] text-neutral-400">Configured Nodes</div>
            <div className="mt-2 text-[24px] font-medium tracking-[-0.04em] text-neutral-950">{nodes.length}</div>
          </div>
          <div className="rounded-[22px] border border-neutral-200 bg-[#fbfaf7] px-4 py-4">
            <div className="text-[11px] uppercase tracking-[0.18em] text-neutral-400">Connected</div>
            <div className="mt-2 text-[24px] font-medium tracking-[-0.04em] text-neutral-950">{connectedCount}</div>
          </div>
          <div className="rounded-[22px] border border-neutral-200 bg-[#fbfaf7] px-4 py-4">
            <div className="text-[11px] uppercase tracking-[0.18em] text-neutral-400">Bound Bros</div>
            <div className="mt-2 text-[24px] font-medium tracking-[-0.04em] text-neutral-950">
              {personas.filter((persona) => Boolean(persona.executor_node_id)).length}
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-600">
          {error}
        </div>
      )}
      {status && (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-[13px] text-emerald-700">
          {status}
        </div>
      )}

      {latestIssue && (
        <CredentialsPanel
          issue={latestIssue}
          boundBroCount={personaCounts.get(latestIssue.node.node_id) ?? 0}
        />
      )}

      {(mode === "add" || editingNode) && (
        <div className="rounded-[28px] border border-neutral-200 bg-white px-6 py-6">
          <SectionHeader title={editingNode ? "Edit Node" : "Create Node"} />
          <NodeForm
            initial={
              editingNode
                ? {
                    name: editingNode.name,
                    enabledExecutors: editingNode.enabled_executors,
                  }
                : undefined
            }
            submitLabel={editingNode ? "Save" : "Create"}
            onSubmit={editingNode ? handleUpdate : handleCreate}
            onCancel={() => {
              setMode("list");
              setEditingNodeId(null);
            }}
          />
        </div>
      )}

      <div>
        <SectionHeader title="Node Fleet" />
        <div className="space-y-4">
          {nodes.length === 0 ? (
            <div className="rounded-[24px] border border-dashed border-neutral-300 bg-white/60 px-6 py-10 text-center">
              <div className="text-[14px] text-neutral-500">No executor nodes yet.</div>
              <div className="mt-1 text-[12px] text-neutral-400">
                Create one here, issue credentials, and start it from your local machine.
              </div>
            </div>
          ) : (
            nodes.map((node) => (
              <NodeCard
                key={node.node_id}
                node={node}
                boundBroCount={personaCounts.get(node.node_id) ?? 0}
                copied={copiedNodeId === node.node_id}
                onCopyCommand={() => {
                  void handleCopyCommand(node.node_id);
                }}
                onEdit={() => {
                  setMode("edit");
                  setEditingNodeId(node.node_id);
                  setError(null);
                  setStatus(null);
                }}
                onRotate={() => {
                  void handleRotate(node.node_id);
                }}
                onDelete={() => {
                  void handleDelete(node.node_id);
                }}
              />
            ))
          )}
        </div>
      </div>
    </div>
  );
}
