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
    <div className="nb-card nb-form-card space-y-3 sm:px-6 sm:py-5">
      <input
        type="text"
        placeholder="Node name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        className="command-field w-full px-4 py-2.5 text-[14px] text-[#111827] placeholder-[#9ca3af] outline-none transition focus:border-[#ffb89e] focus:ring-2 focus:ring-[#ff6a3d]/10"
      />

      <div className="space-y-2">
        <div className="command-label text-[#9ca3af]">Enabled Executors</div>
        <div className="flex flex-wrap gap-2">
          {EXECUTOR_OPTIONS.map((executorType) => (
            <button
              key={executorType}
              type="button"
              onClick={() => toggleExecutor(executorType)}
              className={`nb-toggle-chip ${enabledExecutors.includes(executorType) ? "nb-toggle-chip-active" : ""}`}
            >
              {executorType}
            </button>
          ))}
        </div>
        <div className="text-[12px] leading-5 text-neutral-500">
          Pick the executor families this local machine will advertise to Newbro.
        </div>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row">
        <button
          onClick={() =>
            onSubmit({
              name: name.trim(),
              enabledExecutors,
            })
          }
          disabled={!name.trim() || enabledExecutors.length === 0}
          className="nb-page-primary-action"
        >
          {submitLabel}
        </button>
        <button
          onClick={onCancel}
          className="nb-secondary-action"
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
    <div className="nb-card px-4 py-5 sm:px-6 sm:py-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="command-label text-[#9ca3af]">Enrollment Kit</div>
          <div className="mt-2 text-[24px] font-bold tracking-[-0.03em] text-[#111827] sm:text-[28px]">
            {issue.node.name}
          </div>
          <div className="mt-2 max-w-[640px] text-[13px] leading-6 text-[#6b7280]">
            Keep this token now. Newbro will not show the raw token again unless you rotate it.
          </div>
        </div>
        <div className="nb-chip">
          {boundBroCount} Bros bound
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.08fr)_minmax(280px,0.92fr)]">
        <div className="nb-subcard space-y-3">
          <div>
            <div className="command-label text-[#9ca3af]">Node Id</div>
            <div className="nb-mono-field mt-2 px-4 py-3 text-[13px]">
              {issue.node.node_id}
            </div>
          </div>
          <div>
            <div className="command-label text-[#9ca3af]">Token</div>
            <div className="nb-mono-field mt-2 px-4 py-3 text-[13px] leading-6">
              {issue.token}
            </div>
          </div>
          <div>
            <div className="command-label text-[#9ca3af]">Connect Command</div>
            <div className="nb-mono-field subtle-scrollbar mt-2 overflow-x-auto px-4 py-3 text-[12px] leading-6">
              {command}
            </div>
          </div>
        </div>

        <div className="nb-subcard">
          <div className="command-label text-[#9ca3af]">Local Machine</div>
          <div className="mt-3 text-[18px] font-semibold tracking-[-0.03em] text-[#111827]">Start the executor node</div>
          <div className="mt-3 space-y-3 text-[13px] leading-6 text-[#6b7280]">
            <div>1. Copy the command below onto the client machine that will run the node.</div>
            <div>2. Run it directly to connect back to this Newbro service.</div>
            <div>3. If local executor commands are missing, the run command will prompt for setup in a TTY.</div>
          </div>
          <button
            type="button"
            onClick={() => {
              void handleCopy().catch((error: unknown) => {
                setCopyError(error instanceof Error ? error.message : "Copy failed. Copy the visible command manually.");
              });
            }}
            className="nb-page-primary-action mt-4 w-full"
          >
            <Copy className="h-3.5 w-3.5" strokeWidth={1.8} />
            {copied ? "Copied" : "Copy connect command"}
          </button>
          {copyError && (
            <div className="nb-status-banner nb-status-banner-error mt-3">
              {copyError}
            </div>
          )}
          <div className="mt-4 rounded-[12px] border border-[#e5e7eb] bg-white px-4 py-3 text-[12px] leading-5 text-[#6b7280]">
            The Bro becomes live only after this node connects back to Newbro with the matching node id and token.
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
    <div className="nb-card nb-list-card sm:px-5 sm:py-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <div className="text-[18px] font-semibold tracking-[-0.03em] text-[#111827]">{node.name}</div>
            <div
              className={`nb-chip uppercase ${
                connected
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "border-amber-200 bg-amber-50 text-amber-700"
              }`}
            >
              {connected ? "connected" : "offline"}
            </div>
          </div>
          <div className="mt-2 break-all text-[13px] text-neutral-500">{node.node_id}</div>
        </div>

        <div className="flex w-full flex-wrap justify-start gap-1.5 sm:w-auto sm:justify-end">
          <button
            onClick={onCopyCommand}
            className="nb-secondary-action"
          >
            <Copy className="h-3.5 w-3.5" strokeWidth={1.8} />
            {copied ? "Copied" : "Copy command"}
          </button>
          <button
            onClick={onEdit}
            aria-label={`Edit ${node.name}`}
            className="nb-icon-action"
          >
            <Pencil className="h-3.5 w-3.5" strokeWidth={1.8} />
          </button>
          <button
            onClick={onRotate}
            aria-label={`Rotate credentials for ${node.name}`}
            className="nb-icon-action"
          >
            <RotateCcw className="h-3.5 w-3.5" strokeWidth={1.8} />
          </button>
          <button
            onClick={onDelete}
            aria-label={`Delete ${node.name}`}
            className="nb-icon-action nb-danger-action"
          >
            <Trash2 className="h-3.5 w-3.5" strokeWidth={1.8} />
          </button>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
        <div className="nb-subcard">
          <div className="flex items-center gap-2 command-label text-[#9ca3af]">
            <Server className="h-3.5 w-3.5" strokeWidth={1.8} />
            Executors
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {node.enabled_executors.map((executorType) => (
              <div
                key={executorType}
                className={`nb-chip uppercase ${
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
        <div className="nb-subcard">
          <div className="flex items-center gap-2 command-label text-[#9ca3af]">
            <Cable className="h-3.5 w-3.5" strokeWidth={1.8} />
            Connection
          </div>
          <div className="mt-3 text-[20px] font-semibold tracking-[-0.03em] text-[#111827]">
            {connected ? "Live" : "Waiting"}
          </div>
          <div className="mt-1 text-[12px] leading-5 text-neutral-500">
            Last connected: {formatTimestamp(node.last_connected_at)}
          </div>
        </div>
        <div className="nb-subcard">
          <div className="flex items-center gap-2 command-label text-[#9ca3af]">
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

export function NodesPage({
  sessionId,
  initialNodes,
  initialPersonas,
}: {
  sessionId: string;
  initialNodes: ExecutorNodeRecord[];
  initialPersonas: Persona[];
}) {
  const [nodes, setNodes] = useState<ExecutorNodeRecord[]>(initialNodes);
  const [personas, setPersonas] = useState<Persona[]>(initialPersonas);
  const [mode, setMode] = useState<"list" | "add" | "edit">("list");
  const [editingNodeId, setEditingNodeId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [latestIssue, setLatestIssue] = useState<ExecutorNodeCredentialIssue | null>(null);
  const [copiedNodeId, setCopiedNodeId] = useState<string | null>(null);

  useEffect(() => {
    setNodes(initialNodes);
  }, [initialNodes]);

  useEffect(() => {
    setPersonas(initialPersonas);
  }, [initialPersonas]);

  const refreshData = useCallback(async () => {
    try {
      const [loadedNodes, loadedPersonas] = await Promise.all([
        listExecutorNodes(sessionId),
        listPersonas(sessionId),
      ]);
      setNodes(Array.isArray(loadedNodes) ? loadedNodes : []);
      setPersonas(Array.isArray(loadedPersonas) ? loadedPersonas : []);
      setError(null);
    } catch (e: unknown) {
      const detail = e instanceof Error ? e.message : "Could not refresh node data.";
      setError(`${detail} Showing the latest shell snapshot instead.`);
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
    <div className="nb-detail-shell nb-detail-shell-full">
      <section className="nb-detail-main">
        <div className="nb-detail-topbar">
          <div className="nb-detail-crumb">
            <span>Workspace</span>
            <span className="nb-detail-crumb-sep">/</span>
            <span className="nb-detail-crumb-current">Nodes</span>
          </div>
        </div>

        <div className="nb-detail-bro-header">
          <div className="nb-detail-bro-title">
            <h1>Executor Nodes</h1>
            <span className="nb-chip">{nodes.length} configured</span>
            <span className="nb-chip nb-chip-online">
              <span className="nb-pulse" />
              {connectedCount} connected
            </span>
            <span className="nb-chip">
              {personas.filter((persona) => Boolean(persona.executor_node_id)).length} bound
            </span>
          </div>

          {mode === "list" && (
            <button
              onClick={() => {
                setMode("add");
                setEditingNodeId(null);
                setError(null);
                setStatus(null);
              }}
              className="nb-page-primary-action"
            >
              <Plus strokeWidth={2} />
              New Node
            </button>
          )}
        </div>

        <div className="nb-detail-scroll space-y-5 sm:space-y-6">
          <div className="nb-page-copy">
            Create a node, issue its credential pair, and bind Bros to that machine. A Bro only becomes live
            after its bound node reconnects to Newbro with the matching node id and token.
          </div>

          {error && (
            <div className="nb-status-banner nb-status-banner-error">
              {error}
            </div>
          )}
          {status && (
            <div className="nb-status-banner nb-status-banner-success">
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
            <div>
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
                <div className="nb-empty-state">
                  <div>No executor nodes yet.</div>
                  <div className="mt-1">
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
      </section>
    </div>
  );
}
