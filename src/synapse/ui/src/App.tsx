import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import {
  createSession,
  getConversationSnapshot,
  getDiagnosticTimeline,
  getSessionSnapshot,
  openSessionStream,
  sendSocketCommand,
  sendSocketMessage,
} from "./client";
import type {
  AssistantResponseCompletedStreamEvent,
  ConnectionStatus,
  ConversationSnapshot,
  ConversationHistoryEntry,
  DiagnosticEvent,
  ExecutionRun,
  ExecutionSession,
  SessionBinding,
  SessionStreamEvent,
  SessionResponse,
  SessionSnapshot,
  SnapshotDiffItem,
  Task,
  TaskCommandType,
  TaskSummary,
} from "./types";

type TaskResultDetail = {
  shortText: string;
  fullText: string;
  source:
    | "summary_conversational"
    | "summary_operational"
    | "run_output"
    | "run_failure"
    | "run_block"
    | "run_progress"
    | "none";
};

type LiveAssistantBubble = {
  requestId: string;
  text: string;
  state: "streaming" | "completed" | "failed";
  messageId?: string;
  conversationalAct?: string;
  affectedTaskIds: string[];
};

function makeRequestId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `req-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function makeLocalMessageId(kind: "user", requestId: string) {
  const compact = requestId.replace(/[^a-zA-Z0-9]/g, "").slice(0, 8) || "local";
  return `local-${kind}-${compact}`;
}

function formatTime(value: string | null | undefined) {
  if (!value) {
    return "n/a";
  }
  const date = new Date(value);
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(
    2,
    "0",
  )}:${String(date.getSeconds()).padStart(2, "0")}`;
}

function formatJson(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function buildDiffItems(
  current: SessionSnapshot | null,
  previous: SessionSnapshot | null,
): SnapshotDiffItem[] {
  if (!current) {
    return [];
  }

  const items: SnapshotDiffItem[] = [];

  const previousTasks = new Map(previous?.tasks.map((task) => [task.task_id, task]) ?? []);
  for (const task of current.tasks) {
    const prev = previousTasks.get(task.task_id);
    if (!prev) {
      items.push({
        id: `task-created-${task.task_id}`,
        entityKind: "task",
        entityId: task.task_id,
        changeType: "created",
        taskId: task.task_id,
        details: `Task created: ${task.title}`,
      });
      continue;
    }
    if (prev.status !== task.status) {
      items.push({
        id: `task-status-${task.task_id}-${task.status}`,
        entityKind: "task",
        entityId: task.task_id,
        changeType: "status_changed",
        taskId: task.task_id,
        details: `Task status ${prev.status} -> ${task.status}`,
      });
    }
    if (prev.task_revision !== task.task_revision) {
      items.push({
        id: `task-revision-${task.task_id}-${task.task_revision}`,
        entityKind: "task",
        entityId: task.task_id,
        changeType: "revision_bumped",
        taskId: task.task_id,
        details: `Task revision ${prev.task_revision} -> ${task.task_revision}`,
      });
    }
  }

  const previousRuns = new Map(previous?.execution_runs.map((run) => [run.run_id, run]) ?? []);
  for (const run of current.execution_runs) {
    const prev = previousRuns.get(run.run_id);
    if (!prev) {
      items.push({
        id: `run-created-${run.run_id}`,
        entityKind: "run",
        entityId: run.run_id,
        changeType: "created",
        taskId: run.task_id,
        details: `Run created: ${run.run_id}`,
      });
      continue;
    }
    if (prev.status !== run.status) {
      items.push({
        id: `run-status-${run.run_id}-${run.status}`,
        entityKind: "run",
        entityId: run.run_id,
        changeType: "status_changed",
        taskId: run.task_id,
        details: `Run status ${prev.status} -> ${run.status}`,
      });
    }
  }

  return items.reverse();
}

function commandLabel(command: TaskCommandType) {
  return command.replace("_task", "").replace("_", " ");
}

function canRunCommand(task: Task, command: TaskCommandType) {
  if (command === "pause_task") {
    return ["created", "queued", "running", "waiting_user_input"].includes(task.status);
  }
  if (command === "cancel_task") {
    return !["completed", "cancelled", "failed"].includes(task.status);
  }
  if (command === "retry_task") {
    return ["completed", "failed", "cancelled", "paused"].includes(task.status);
  }
  if (command === "resume_task") {
    return task.status === "paused";
  }
  return false;
}

function buildTaskSummaryMap(snapshot: SessionSnapshot | null) {
  return new Map(snapshot?.summaries.map((summary) => [summary.task_id, summary]) ?? []);
}

function buildLatestRunMap(snapshot: SessionSnapshot | null) {
  const runMap = new Map<string, ExecutionRun>();
  const sessionsByTask = new Map(
    snapshot?.execution_sessions.map((session) => [session.task_id, session]) ?? [],
  );
  const runsById = new Map(snapshot?.execution_runs.map((run) => [run.run_id, run]) ?? []);

  for (const task of snapshot?.tasks ?? []) {
    const session = sessionsByTask.get(task.task_id);
    const latestRun =
      (session?.latest_run_id ? runsById.get(session.latest_run_id) : null) ??
      [...(snapshot?.execution_runs ?? [])]
        .reverse()
        .find((run) => run.task_id === task.task_id) ??
      null;
    if (latestRun) {
      runMap.set(task.task_id, latestRun);
    }
  }

  return runMap;
}

function getTaskResultDetail(
  taskId: string,
  summaryMap: Map<string, TaskSummary>,
  latestRunMap: Map<string, ExecutionRun>,
): TaskResultDetail | null {
  const summary = summaryMap.get(taskId);
  if (summary?.conversational_summary?.trim()) {
    return {
      shortText: summary.conversational_summary.trim(),
      fullText: summary.conversational_summary.trim(),
      source: "summary_conversational",
    };
  }
  if (summary?.operational_summary?.trim()) {
    return {
      shortText: summary.operational_summary.trim(),
      fullText: summary.operational_summary.trim(),
      source: "summary_operational",
    };
  }

  const run = latestRunMap.get(taskId);
  if (!run) {
    return null;
  }
  if (run.output_summary?.trim()) {
    return {
      shortText: run.output_summary.trim(),
      fullText: run.output_summary.trim(),
      source: "run_output",
    };
  }
  if (run.failure_reason?.trim()) {
    return {
      shortText: run.failure_reason.trim(),
      fullText: run.failure_reason.trim(),
      source: "run_failure",
    };
  }
  if (run.block_reason?.trim()) {
    return {
      shortText: run.block_reason.trim(),
      fullText: run.block_reason.trim(),
      source: "run_block",
    };
  }
  if (run.latest_progress_message?.trim()) {
    return {
      shortText: run.latest_progress_message.trim(),
      fullText: run.latest_progress_message.trim(),
      source: "run_progress",
    };
  }
  return null;
}

function summarizeTaskResultForCard(detail: TaskResultDetail | null) {
  if (!detail) {
    return "No result yet.";
  }
  return detail.shortText.length > 120 ? `${detail.shortText.slice(0, 117)}...` : detail.shortText;
}

function summarizeToolArgs(args: Record<string, unknown>) {
  const preferredKeys = [
    "task_id",
    "reference",
    "command_type",
    "title",
    "goal",
    "note",
    "constraint",
  ];
  const parts = preferredKeys
    .filter((key) => args[key] !== undefined && args[key] !== null)
    .map((key) => `${key}=${String(args[key])}`);
  if (parts.length > 0) {
    return parts.join(", ");
  }
  const keys = Object.keys(args);
  return keys.length > 0 ? `keys: ${keys.join(", ")}` : "no args";
}

function pickAutoSelectedTask(
  nextSnapshot: SessionSnapshot,
  previous: SessionSnapshot | null,
  currentSelectedTaskId: string | null,
) {
  const previousTasks = new Map(previous?.tasks.map((task) => [task.task_id, task]) ?? []);
  const promotedStatuses = new Set(["completed", "failed", "waiting_user_input"]);
  const transitioned = nextSnapshot.tasks.find((task) => {
    const prev = previousTasks.get(task.task_id);
    return prev && prev.status !== task.status && promotedStatuses.has(task.status);
  });
  if (transitioned) {
    return transitioned.task_id;
  }
  if (
    currentSelectedTaskId &&
    nextSnapshot.tasks.some((task) => task.task_id === currentSelectedTaskId)
  ) {
    return currentSelectedTaskId;
  }
  return nextSnapshot.tasks[0]?.task_id ?? null;
}

function getDetailRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function getDetailString(value: unknown) {
  return typeof value === "string" ? value : null;
}

function getDetailStringArray(value: unknown) {
  return Array.isArray(value) ? value.map((item) => String(item)) : [];
}

function summarizeDiagnosticEvent(event: DiagnosticEvent) {
  const detailKeys = Object.keys(event.details ?? {});
  return detailKeys.length > 0
    ? `${event.event_name} (${detailKeys.join(", ")})`
    : event.event_name;
}

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("booting");
  const [composer, setComposer] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [snapshot, setSnapshot] = useState<SessionSnapshot | null>(null);
  const [conversationSnapshot, setConversationSnapshot] = useState<ConversationSnapshot | null>(null);
  const [diagnosticEvents, setDiagnosticEvents] = useState<DiagnosticEvent[]>([]);
  const [isPageVisible, setIsPageVisible] = useState(
    typeof document === "undefined" ? true : document.visibilityState === "visible",
  );
  const [previousSnapshot, setPreviousSnapshot] = useState<SessionSnapshot | null>(null);
  const [lastAssistantResponse, setLastAssistantResponse] =
    useState<AssistantResponseCompletedStreamEvent | null>(null);
  const [liveAssistant, setLiveAssistant] = useState<LiveAssistantBubble | null>(null);
  const [lastCommandStatus, setLastCommandStatus] = useState<string | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [taskSelectionPinned, setTaskSelectionPinned] = useState(false);
  const [selectedExecutionSessionId, setSelectedExecutionSessionId] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [pendingCommand, setPendingCommand] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const latestSnapshotRef = useRef<SessionSnapshot | null>(null);
  const latestDiagnosticSequenceRef = useRef(0);
  const refreshDiagnosticsRef = useRef<(() => Promise<void>) | null>(null);
  const isPageVisibleRef = useRef(isPageVisible);
  const taskSelectionPinnedRef = useRef(false);
  const pendingCommandRequestsRef = useRef<Map<string, string>>(new Map());

  useEffect(() => {
    let active = true;
    async function boot() {
      setConnectionStatus("booting");
      try {
        const session: SessionResponse = await createSession();
        if (!active) {
          return;
        }
        setSessionId(session.session_id);
        setDiagnosticEvents([]);
        latestDiagnosticSequenceRef.current = 0;
      } catch (error) {
        if (!active) {
          return;
        }
        setConnectionStatus("error");
        setActionError(error instanceof Error ? error.message : "Failed to create session.");
      }
    }
    void boot();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    latestSnapshotRef.current = snapshot;
  }, [snapshot]);

  useEffect(() => {
    isPageVisibleRef.current = isPageVisible;
  }, [isPageVisible]);

  useEffect(() => {
    taskSelectionPinnedRef.current = taskSelectionPinned;
  }, [taskSelectionPinned]);

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }
    const handleVisibilityChange = () => {
      setIsPageVisible(document.visibilityState === "visible");
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);

  useEffect(() => {
    if (!sessionId) {
      return;
    }
    const activeSessionId = sessionId;
    let active = true;
    async function loadInitialStateSnapshot() {
      try {
        const stateSnapshot = await getSessionSnapshot(activeSessionId);
        if (!active) {
          return;
        }
        setSnapshot(stateSnapshot);
        latestSnapshotRef.current = stateSnapshot;
        setConnectionStatus("connecting");
      } catch (error) {
        if (!active) {
          return;
        }
        setConnectionStatus("error");
        setActionError(error instanceof Error ? error.message : "Failed to load session data.");
      }
    }
    void loadInitialStateSnapshot();
    return () => {
      active = false;
    };
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId) {
      return;
    }
    const activeSessionId = sessionId;
    let active = true;
    async function loadConversationProjection() {
      try {
        const chatSnapshot = await getConversationSnapshot(activeSessionId);
        if (!active) {
          return;
        }
        setConversationSnapshot(chatSnapshot);
      } catch (error) {
        if (!active) {
          return;
        }
        setActionError(error instanceof Error ? error.message : "Failed to refresh conversation projection.");
      }
    }
    void loadConversationProjection();
    return () => {
      active = false;
    };
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId) {
      refreshDiagnosticsRef.current = null;
      return;
    }
    const activeSessionId = sessionId;
    let active = true;

    async function refreshDiagnostics() {
      try {
        const response = await getDiagnosticTimeline(activeSessionId, {
          afterSequence:
            latestDiagnosticSequenceRef.current > 0
              ? latestDiagnosticSequenceRef.current
              : undefined,
          minLevel: "DEBUG",
          limit: latestDiagnosticSequenceRef.current > 0 ? undefined : 200,
        });
        if (!active || response.events.length === 0) {
          return;
        }
        setDiagnosticEvents((current) => {
          const next = [...current, ...response.events];
          return next.length > 200 ? next.slice(next.length - 200) : next;
        });
        latestDiagnosticSequenceRef.current =
          response.events[response.events.length - 1].sequence;
      } catch (error) {
        if (!active) {
          return;
        }
        setActionError(error instanceof Error ? error.message : "Failed to refresh diagnostics.");
      }
    }

    refreshDiagnosticsRef.current = refreshDiagnostics;
    if (isPageVisible) {
      void refreshDiagnostics();
    }
    const interval = isPageVisible
      ? window.setInterval(() => {
          void refreshDiagnostics();
        }, 1000)
      : null;
    return () => {
      active = false;
      if (interval !== null) {
        window.clearInterval(interval);
      }
      if (refreshDiagnosticsRef.current === refreshDiagnostics) {
        refreshDiagnosticsRef.current = null;
      }
    };
  }, [sessionId, isPageVisible]);

  useEffect(() => {
    if (!isPageVisible || refreshDiagnosticsRef.current === null) {
      return;
    }
    void refreshDiagnosticsRef.current();
  }, [isPageVisible]);

  useEffect(() => {
    if (!liveAssistant || !conversationSnapshot) {
      return;
    }
    if (liveAssistant.messageId) {
      const persisted = conversationSnapshot.conversation_history.some(
        (entry) => entry.message_id === liveAssistant.messageId,
      );
      if (persisted) {
        setLiveAssistant(null);
      }
      return;
    }
    const persisted = conversationSnapshot.conversation_history.some(
      (entry) => entry.role === "assistant" && entry.text === liveAssistant.text,
    );
    if (persisted) {
      setLiveAssistant(null);
    }
  }, [liveAssistant, conversationSnapshot]);

  useEffect(() => {
    if (!sessionId) {
      return;
    }
    setConnectionStatus("connecting");
    setActionError(null);
    const socket = openSessionStream(sessionId, {
      onOpen: () => setConnectionStatus("connecting"),
      onClose: () => {
        socketRef.current = null;
        setConnectionStatus((current) => (current === "error" ? current : "disconnected"));
      },
      onError: () => {
        socketRef.current = null;
        setConnectionStatus("error");
        setActionError("Failed to connect to the session stream.");
      },
      onMessage: (event: SessionStreamEvent) => {
        if (event.type === "snapshot") {
          const nextSnapshot = event.snapshot;
          const previous = latestSnapshotRef.current;
          setConnectionStatus("connected");
          setPreviousSnapshot(previous);
          setSnapshot(nextSnapshot);
          latestSnapshotRef.current = nextSnapshot;
          setSelectedTaskId((current) =>
            taskSelectionPinnedRef.current
              ? current
              : pickAutoSelectedTask(nextSnapshot, previous, current),
          );
          if (isPageVisibleRef.current && refreshDiagnosticsRef.current) {
            void refreshDiagnosticsRef.current();
          }
          return;
        }

        if (event.type === "action_accepted") {
          if (event.action_type === "send_message") {
            setIsSending(false);
          }
          if (event.action_type === "send_command") {
            const commandKey = pendingCommandRequestsRef.current.get(event.request_id) ?? null;
            if (commandKey) {
              setPendingCommand((current) => (current === commandKey ? null : current));
              pendingCommandRequestsRef.current.delete(event.request_id);
            }
            setLastCommandStatus("accepted");
          }
          return;
        }

        if (event.type === "action_rejected") {
          setActionError(event.message);
          if (event.action_type === "send_message") {
            setIsSending(false);
          }
          if (event.action_type === "send_command") {
            const commandKey = pendingCommandRequestsRef.current.get(event.request_id) ?? null;
            if (commandKey) {
              setPendingCommand((current) => (current === commandKey ? null : current));
              pendingCommandRequestsRef.current.delete(event.request_id);
            }
            setLastCommandStatus("rejected");
          }
          return;
        }

        if (event.type === "assistant_response_started") {
          setLiveAssistant({
            requestId: event.request_id,
            text: "",
            state: "streaming",
            affectedTaskIds: [],
          });
          return;
        }

        if (event.type === "assistant_response_delta") {
          setLiveAssistant((current) => {
            if (!current || current.requestId !== event.request_id) {
              return {
                requestId: event.request_id,
                text: event.delta,
                state: "streaming",
                affectedTaskIds: [],
              };
            }
            return {
              ...current,
              text: `${current.text}${event.delta}`,
            };
          });
          return;
        }

        if (event.type === "assistant_response_completed") {
          setLastAssistantResponse(event);
          setConversationSnapshot((current) => {
            if (!current) {
              return current;
            }
            if (current.conversation_history.some((entry) => entry.message_id === event.message_id)) {
              return current;
            }
            return {
              ...current,
              conversation_history: [
                ...current.conversation_history,
                {
                  role: "assistant",
                  text: event.reply_text,
                  message_id: event.message_id,
                },
              ],
            };
          });
          setLiveAssistant({
            requestId: event.request_id,
            text: event.reply_text,
            state: "completed",
            messageId: event.message_id,
            conversationalAct: event.conversational_act,
            affectedTaskIds: event.affected_task_ids,
          });
          if (isPageVisibleRef.current && refreshDiagnosticsRef.current) {
            void refreshDiagnosticsRef.current();
          }
          return;
        }

        if (event.type === "assistant_response_failed") {
          setActionError(event.message);
          setLiveAssistant({
            requestId: event.request_id,
            text: event.message,
            state: "failed",
            affectedTaskIds: [],
          });
          if (isPageVisibleRef.current && refreshDiagnosticsRef.current) {
            void refreshDiagnosticsRef.current();
          }
          return;
        }

        if (event.type === "conversation_appended") {
          setConversationSnapshot((current) => {
            if (!current) {
              return current;
            }
            if (current.conversation_history.some((entry) => entry.message_id === event.message_id)) {
              return current;
            }
            return {
              ...current,
              conversation_history: [
                ...current.conversation_history,
                {
                  role: event.role,
                  text: event.text,
                  message_id: event.message_id,
                },
              ],
            };
          });
          return;
        }
      },
    });
    socketRef.current = socket;
    return () => {
      socketRef.current = null;
      socket.close();
    };
  }, [sessionId]);

  useEffect(() => {
    if (!snapshot?.tasks.length) {
      setSelectedTaskId(null);
      setTaskSelectionPinned(false);
      return;
    }
    if (!selectedTaskId || !snapshot.tasks.some((task) => task.task_id === selectedTaskId)) {
      setSelectedTaskId((current) =>
        pickAutoSelectedTask(snapshot, previousSnapshot, current),
      );
    }
  }, [snapshot, previousSnapshot, selectedTaskId]);

  const diffItems = useMemo(
    () => buildDiffItems(snapshot, previousSnapshot),
    [snapshot, previousSnapshot],
  );
  const summaryByTaskId = useMemo(() => buildTaskSummaryMap(snapshot), [snapshot]);
  const latestRunByTaskId = useMemo(() => buildLatestRunMap(snapshot), [snapshot]);

  const selectedTask = snapshot?.tasks.find((task) => task.task_id === selectedTaskId) ?? null;
  const selectedSummary = selectedTaskId ? summaryByTaskId.get(selectedTaskId) ?? null : null;
  const toolCallHistory = useMemo(
    () => diagnosticEvents.filter((event) => event.event_name === "comm.tool.called").slice(-50).reverse(),
    [diagnosticEvents],
  );
  const selectedMutations = useMemo(
    () =>
      diagnosticEvents.filter(
        (event) =>
          event.event_name === "bb.mutation.appended" && event.task_id === selectedTaskId,
      ),
    [diagnosticEvents, selectedTaskId],
  );
  const selectedCommands = useMemo(
    () =>
      diagnosticEvents.filter(
        (event) =>
          event.event_name === "bb.command.appended" && event.task_id === selectedTaskId,
      ),
    [diagnosticEvents, selectedTaskId],
  );
  const selectedBindings =
    snapshot?.bindings.filter((binding) => binding.task_id === selectedTaskId) ?? [];
  const selectedSessions =
    snapshot?.execution_sessions.filter((session) => session.task_id === selectedTaskId) ?? [];
  const selectedRuns =
    snapshot?.execution_runs.filter((run) => run.task_id === selectedTaskId) ?? [];

  useEffect(() => {
    if (!selectedSessions.length) {
      setSelectedExecutionSessionId(null);
      return;
    }
    if (
      !selectedExecutionSessionId ||
      !selectedSessions.some((session) => session.execution_session_id === selectedExecutionSessionId)
    ) {
      setSelectedExecutionSessionId(selectedSessions[0].execution_session_id);
    }
  }, [selectedExecutionSessionId, selectedSessions]);

  const sessionRuns =
    snapshot?.execution_runs.filter(
      (run) => run.execution_session_id === selectedExecutionSessionId,
    ) ?? [];

  useEffect(() => {
    if (!sessionRuns.length) {
      setSelectedRunId(null);
      return;
    }
    if (!selectedRunId || !sessionRuns.some((run) => run.run_id === selectedRunId)) {
      setSelectedRunId(sessionRuns[0].run_id);
    }
  }, [selectedRunId, sessionRuns]);

  const selectedRun = sessionRuns.find((run) => run.run_id === selectedRunId) ?? null;
  const selectedTaskResult = selectedTaskId
    ? getTaskResultDetail(selectedTaskId, summaryByTaskId, latestRunByTaskId)
    : null;

  async function handleSendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!sessionId || !composer.trim()) {
      return;
    }
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setActionError("Session socket is not connected.");
      return;
    }
    setActionError(null);
    setIsSending(true);
    const requestId = makeRequestId();
    const text = composer.trim();
    setConversationSnapshot((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        conversation_history: [
          ...current.conversation_history,
          {
            role: "user",
            text,
            message_id: makeLocalMessageId("user", requestId),
          },
        ],
      };
    });
    sendSocketMessage(socket, requestId, text);
    setComposer("");
  }

  async function handleCommand(taskId: string, commandType: TaskCommandType) {
    if (!sessionId) {
      return;
    }
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setActionError("Session socket is not connected.");
      return;
    }
    setActionError(null);
    const commandKey = `${taskId}:${commandType}`;
    const requestId = makeRequestId();
    pendingCommandRequestsRef.current.set(requestId, commandKey);
    setPendingCommand(commandKey);
    sendSocketCommand(socket, requestId, commandType, taskId);
  }

  const tasks = snapshot?.tasks ?? [];
  const conversation = conversationSnapshot?.conversation_history ?? [];
  const recentWrites = diagnosticEvents.filter(
    (event) =>
      event.event_name.startsWith("bb.") ||
      event.event_name.startsWith("exec.") ||
      event.event_name.startsWith("notify."),
  );

  return (
    <main className="shell debug-shell">
      <header className="hero debug-hero">
        <div>
          <p className="eyebrow">Synapse Runtime Debugger</p>
          <h1>Blackboard Inspector</h1>
          <p className="intro">
            Inspect how the communication brain writes to the blackboard, how the execution brain
            claims and runs work, and how the runtime snapshot changes over time.
          </p>
        </div>
        <div className={`status-pill status-${connectionStatus}`}>
          <span className="status-dot" />
          <span>{connectionStatus}</span>
          {sessionId ? <code>{sessionId}</code> : null}
        </div>
      </header>

      {actionError ? <div className="error-banner">{actionError}</div> : null}

      <section className="debug-grid">
        <section className="panel debug-panel">
          <div className="panel-header sticky-header">
            <div>
              <p className="panel-kicker">Communication</p>
              <h2>Conversation</h2>
            </div>
          </div>
          <div className="inspector-scroll conversation-panel">
            {conversation.length === 0 && !liveAssistant ? (
              <div className="empty-state">Waiting for the first conversation turn.</div>
            ) : (
              <>
                {conversation.map((entry: ConversationHistoryEntry) => (
                  <article key={entry.message_id} className={`bubble bubble-${entry.role}`}>
                    <div className="bubble-meta">
                      <span>{entry.role === "user" ? "User" : "Assistant"}</span>
                      <span>{entry.message_id}</span>
                    </div>
                    <p>{entry.text}</p>
                  </article>
                ))}
                {liveAssistant ? (
                  <article key={liveAssistant.requestId} className="bubble bubble-assistant">
                    <div className="bubble-meta">
                      <span>Assistant</span>
                      <span>{liveAssistant.state}</span>
                    </div>
                    <p>{liveAssistant.text || "..."}</p>
                  </article>
                ) : null}
              </>
            )}
          </div>
          <form className="composer" onSubmit={handleSendMessage}>
            <textarea
              value={composer}
              onChange={(event) => setComposer(event.target.value)}
              onKeyDown={(event: KeyboardEvent<HTMLTextAreaElement>) => {
                if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                  event.preventDefault();
                  void handleSendMessage(event as unknown as FormEvent<HTMLFormElement>);
                }
              }}
              placeholder="Send an instruction to inspect how the blackboard changes..."
              rows={4}
            />
            <button type="submit" disabled={!sessionId || !composer.trim() || isSending}>
              {isSending ? "Sending..." : "Send"}
            </button>
          </form>
          <div className="inspector-footer">
            <section className="meta-card">
              <h3>Last Reply</h3>
              {lastAssistantResponse ? (
                <>
                  <p>{lastAssistantResponse.reply_text}</p>
                  <dl className="kv">
                    <div>
                      <dt>Act</dt>
                      <dd>{lastAssistantResponse.conversational_act}</dd>
                    </div>
                    <div>
                      <dt>Tasks</dt>
                      <dd>{lastAssistantResponse.affected_task_ids.join(", ") || "none"}</dd>
                    </div>
                  </dl>
                </>
              ) : (
                <p className="muted-copy">No message response yet.</p>
              )}
            </section>
            <section className="meta-card">
              <h3>Client Stream</h3>
              <p className="muted-copy">
                The websocket now carries only assistant text, acks, and durable snapshots.
                Diagnostic inspection panels are rebuilt from the log timeline instead of a
                separate debug channel.
              </p>
            </section>
          </div>
          <div className="panel-inline-section">
            <section className="inspector-section">
              <h3>Tool Call History</h3>
              {toolCallHistory.length === 0 ? (
                <div className="empty-state">No tool call diagnostics in this session yet.</div>
              ) : (
                <div className="stack compact-stack">
                  {toolCallHistory.map((event) => {
                    const details = getDetailRecord(event.details);
                    const args = getDetailRecord(details.args);
                    const resultPreview =
                      details.result_preview && typeof details.result_preview === "object"
                        ? getDetailRecord(details.result_preview)
                        : null;
                    const error =
                      details.error && typeof details.error === "object"
                        ? getDetailRecord(details.error)
                        : null;
                    const affectedTaskIds = getDetailStringArray(details.affected_task_ids);
                    const toolName = getDetailString(details.tool_name) ?? event.summary;
                    return (
                    <details key={`${event.sequence}:${toolName}`} className="log-card llm-trace-card">
                      <summary className="entity-head llm-trace-summary">
                        <strong>{toolName}</strong>
                        <span>{event.outcome ?? "n/a"}</span>
                      </summary>
                      <div className="llm-trace-body">
                        <p>{getDetailString(details.result_summary) ?? event.summary}</p>
                        <dl className="kv compact">
                          <div>
                            <dt>Request</dt>
                            <dd>{event.request_id ?? "n/a"}</dd>
                          </div>
                          <div>
                            <dt>Tasks</dt>
                            <dd>{affectedTaskIds.join(", ") || "none"}</dd>
                          </div>
                          <div>
                            <dt>Args</dt>
                            <dd>{summarizeToolArgs(args)}</dd>
                          </div>
                        </dl>
                        {error ? (
                          <div className="summary-block">
                            <h4>Error</h4>
                            <pre>{formatJson(error)}</pre>
                          </div>
                        ) : null}
                        <div className="summary-block">
                          <h4>Arguments</h4>
                          <pre>{formatJson(args)}</pre>
                        </div>
                        {resultPreview ? (
                          <div className="summary-block">
                            <h4>Result Preview</h4>
                            <pre>{formatJson(resultPreview)}</pre>
                          </div>
                        ) : null}
                      </div>
                    </details>
                  )})}
                </div>
              )}
            </section>
          </div>
        </section>

        <section className="panel debug-panel">
          <div className="panel-header sticky-header">
            <div>
              <p className="panel-kicker">Blackboard</p>
              <h2>State</h2>
            </div>
          </div>
          <div className="inspector-scroll">
            <section className="inspector-section">
              <h3>Tasks</h3>
              {tasks.length === 0 ? (
                <div className="empty-state">No tasks yet.</div>
              ) : (
                <div className="stack">
                  {tasks.map((task) => (
                    <button
                      key={task.task_id}
                      type="button"
                      className={`entity-card ${selectedTaskId === task.task_id ? "selected" : ""}`}
                      onClick={() => {
                        setTaskSelectionPinned(true);
                        setSelectedTaskId(task.task_id);
                      }}
                    >
                      <div className="entity-head">
                        <strong>{task.title}</strong>
                        <span className={`status-chip status-${task.status}`}>{task.status}</span>
                      </div>
                      <p>{task.goal}</p>
                      <p className="muted-copy">{summarizeTaskResultForCard(getTaskResultDetail(task.task_id, summaryByTaskId, latestRunByTaskId))}</p>
                      <dl className="kv compact">
                        <div>
                          <dt>ID</dt>
                          <dd><code>{task.task_id}</code></dd>
                        </div>
                        <div>
                          <dt>Revision</dt>
                          <dd>{task.task_revision}</dd>
                        </div>
                        <div>
                          <dt>Priority</dt>
                          <dd>{task.priority}</dd>
                        </div>
                        <div>
                          <dt>Executor</dt>
                          <dd>{task.preferred_executor ?? "n/a"}</dd>
                        </div>
                      </dl>
                    </button>
                  ))}
                </div>
              )}
            </section>

            <section className="inspector-section">
              <h3>Selected Task Detail</h3>
              {selectedTask ? (
                <div className="detail-card">
                  <dl className="kv">
                    <div><dt>ID</dt><dd><code>{selectedTask.task_id}</code></dd></div>
                    <div><dt>Status</dt><dd>{selectedTask.status}</dd></div>
                    <div><dt>Revision</dt><dd>{selectedTask.task_revision}</dd></div>
                    <div><dt>Latest Instruction</dt><dd>{selectedTask.latest_instruction ?? "n/a"}</dd></div>
                    <div><dt>Requires Confirmation</dt><dd>{selectedTask.requires_confirmation ? "yes" : "no"}</dd></div>
                    <div><dt>Interruptible</dt><dd>{selectedTask.interruptible ? "yes" : "no"}</dd></div>
                  </dl>
                  <div className="summary-block">
                    <h4>Latest Result</h4>
                    <p>{selectedTaskResult?.fullText ?? "No result yet."}</p>
                  </div>
                  <div className="command-bar">
                    {(["pause_task", "resume_task", "retry_task", "cancel_task"] as TaskCommandType[]).map(
                      (command) => (
                        <button
                          key={command}
                          type="button"
                          className="ghost-button"
                          disabled={!canRunCommand(selectedTask, command) || pendingCommand === `${selectedTask.task_id}:${command}`}
                          onClick={() => void handleCommand(selectedTask.task_id, command)}
                        >
                          {pendingCommand === `${selectedTask.task_id}:${command}` ? "..." : commandLabel(command)}
                        </button>
                      ),
                    )}
                  </div>
                </div>
              ) : (
                <div className="empty-state">Select a task to inspect mutations, commands, and summaries.</div>
              )}
            </section>

            <section className="inspector-section">
              <h3>Mutations</h3>
              {selectedMutations.length === 0 ? (
                <div className="empty-state">No mutations for the selected task.</div>
              ) : (
                <div className="stack compact-stack">
                  {selectedMutations.map((event) => {
                    const details = getDetailRecord(event.details);
                    return (
                    <article key={String(details.mutation_id ?? event.sequence)} className="log-card">
                      <div className="entity-head">
                        <strong>{String(details.mutation_type ?? event.event_name)}</strong>
                        <code>{String(details.mutation_id ?? event.sequence)}</code>
                      </div>
                      <dl className="kv compact">
                        <div><dt>By</dt><dd>{String(details.created_by ?? "n/a")}</dd></div>
                        <div><dt>Scope</dt><dd>{String(details.effective_scope ?? "n/a")}</dd></div>
                        <div><dt>Replan</dt><dd>{details.requires_replan ? "yes" : "no"}</dd></div>
                      </dl>
                      <pre>{formatJson(details.patch ?? {})}</pre>
                    </article>
                  )})}
                </div>
              )}
            </section>

            <section className="inspector-section">
              <h3>Commands</h3>
              {selectedCommands.length === 0 ? (
                <div className="empty-state">No commands for the selected task.</div>
              ) : (
                <div className="stack compact-stack">
                  {selectedCommands.map((event) => {
                    const details = getDetailRecord(event.details);
                    return (
                    <article key={String(details.command_id ?? event.sequence)} className="log-card">
                      <div className="entity-head">
                        <strong>{String(details.command_type ?? event.event_name)}</strong>
                        <code>{String(details.command_id ?? event.sequence)}</code>
                      </div>
                      <dl className="kv compact">
                        <div><dt>By</dt><dd>{String(details.created_by ?? "n/a")}</dd></div>
                        <div><dt>Reason</dt><dd>{String(details.reason ?? "n/a")}</dd></div>
                      </dl>
                      <pre>{formatJson(details.payload ?? {})}</pre>
                    </article>
                  )})}
                </div>
              )}
            </section>

            <section className="inspector-section">
              <h3>Summaries</h3>
              {selectedSummary ? (
                <article className="detail-card">
                  <dl className="kv">
                    <div><dt>User Status</dt><dd>{selectedSummary.latest_user_visible_status ?? "n/a"}</dd></div>
                    <div><dt>Needs Input</dt><dd>{selectedSummary.needs_user_input ? "yes" : "no"}</dd></div>
                  </dl>
                  <div className="summary-block">
                    <h4>Conversational</h4>
                    <p>{selectedSummary.conversational_summary ?? "n/a"}</p>
                  </div>
                  <div className="summary-block">
                    <h4>Operational</h4>
                    <p>{selectedSummary.operational_summary ?? "n/a"}</p>
                  </div>
                </article>
              ) : (
                <div className="empty-state">No summary for the selected task.</div>
              )}
            </section>
          </div>
        </section>

        <section className="panel debug-panel">
          <div className="panel-header sticky-header">
            <div>
              <p className="panel-kicker">Execution</p>
              <h2>Sessions & Runs</h2>
            </div>
          </div>
          <div className="inspector-scroll">
            <section className="inspector-section">
              <h3>Bindings</h3>
              {selectedBindings.length === 0 ? (
                <div className="empty-state">No binding for the selected task.</div>
              ) : (
                selectedBindings.map((binding: SessionBinding) => (
                  <article key={`${binding.task_id}-${binding.session_id ?? "none"}`} className="detail-card">
                    <dl className="kv">
                      <div><dt>Session</dt><dd><code>{binding.session_id ?? "n/a"}</code></dd></div>
                      <div><dt>Owner</dt><dd>{binding.claimed_by ?? "n/a"}</dd></div>
                      <div><dt>Lease</dt><dd>{formatTime(binding.claim_expires_at)}</dd></div>
                      <div><dt>Exec Revision</dt><dd>{binding.execution_revision}</dd></div>
                      <div><dt>Status</dt><dd>{binding.binding_status}</dd></div>
                    </dl>
                  </article>
                ))
              )}
            </section>

            <section className="inspector-section">
              <h3>Execution Sessions</h3>
              {selectedSessions.length === 0 ? (
                <div className="empty-state">No execution sessions for the selected task.</div>
              ) : (
                <div className="stack">
                  {selectedSessions.map((session: ExecutionSession) => (
                    <button
                      key={session.execution_session_id}
                      type="button"
                      className={`entity-card ${selectedExecutionSessionId === session.execution_session_id ? "selected" : ""}`}
                      onClick={() => setSelectedExecutionSessionId(session.execution_session_id)}
                    >
                      <div className="entity-head">
                        <strong>{session.base_executor_id}</strong>
                        <code>{session.execution_session_id}</code>
                      </div>
                      <dl className="kv compact">
                        <div><dt>Active Run</dt><dd>{session.active_run_id ?? "n/a"}</dd></div>
                        <div><dt>Latest Run</dt><dd>{session.latest_run_id ?? "n/a"}</dd></div>
                        <div><dt>Run Count</dt><dd>{session.run_ids.length}</dd></div>
                      </dl>
                    </button>
                  ))}
                </div>
              )}
            </section>

            <section className="inspector-section">
              <h3>Execution Runs</h3>
              {sessionRuns.length === 0 ? (
                <div className="empty-state">No runs for the selected execution session.</div>
              ) : (
                <div className="stack">
                  {sessionRuns.map((run: ExecutionRun) => (
                    <button
                      key={run.run_id}
                      type="button"
                      className={`entity-card ${selectedRunId === run.run_id ? "selected" : ""}`}
                      onClick={() => setSelectedRunId(run.run_id)}
                    >
                      <div className="entity-head">
                        <strong>{run.executor_type}</strong>
                        <span className={`status-chip status-${run.status}`}>{run.status}</span>
                      </div>
                      <dl className="kv compact">
                        <div><dt>ID</dt><dd><code>{run.run_id}</code></dd></div>
                        <div><dt>Revision</dt><dd>{run.run_revision}</dd></div>
                        <div><dt>Owner</dt><dd>{run.claimed_by ?? "n/a"}</dd></div>
                      </dl>
                    </button>
                  ))}
                </div>
              )}
            </section>

            <section className="inspector-section">
              <h3>Selected Run Detail</h3>
              {selectedRun ? (
                <article className="detail-card">
                  <dl className="kv">
                    <div><dt>ID</dt><dd><code>{selectedRun.run_id}</code></dd></div>
                    <div><dt>Status</dt><dd>{selectedRun.status}</dd></div>
                    <div><dt>Progress</dt><dd>{selectedRun.latest_progress_message ?? "n/a"}</dd></div>
                    <div><dt>Output</dt><dd>{selectedRun.output_summary ?? "n/a"}</dd></div>
                    <div><dt>Blocked</dt><dd>{selectedRun.block_reason ?? "n/a"}</dd></div>
                    <div><dt>Failure</dt><dd>{selectedRun.failure_reason ?? "n/a"}</dd></div>
                  </dl>
                  <pre>{formatJson(selectedRun.metadata)}</pre>
                </article>
              ) : (
                <div className="empty-state">Select a run to inspect execution detail.</div>
              )}
            </section>
          </div>
        </section>
      </section>

      <section className="panel change-feed-panel">
        <div className="panel-header sticky-header">
          <div>
            <p className="panel-kicker">Diff & Writes</p>
            <h2>Change Feed</h2>
          </div>
          <div className="feed-meta">
            <span>{diffItems.length} diffs</span>
            <span>{recentWrites.length} writes</span>
            {lastCommandStatus ? <span>last command: {lastCommandStatus}</span> : null}
          </div>
        </div>
        <div className="change-feed-grid">
          <section className="inspector-section">
            <h3>Snapshot Diff</h3>
            {diffItems.length === 0 ? (
              <div className="empty-state">Waiting for snapshot changes.</div>
            ) : (
              <div className="stack compact-stack">
                {diffItems.map((item) => (
                  <article key={item.id} className="diff-row">
                    <div className="diff-head">
                      <span className="entity-badge">{item.entityKind}</span>
                      <strong>{item.changeType}</strong>
                      <code>{item.entityId}</code>
                    </div>
                    <p>{item.details}</p>
                  </article>
                ))}
              </div>
            )}
          </section>

          <section className="inspector-section">
            <h3>Recent Blackboard Diagnostics</h3>
            {recentWrites.length === 0 ? (
              <div className="empty-state">No writes published yet.</div>
            ) : (
              <div className="stack compact-stack">
                {[...recentWrites].reverse().map((event, index) => (
                  <article key={`${event.sequence}-${index}`} className="diff-row">
                    <div className="diff-head">
                      <span className="entity-badge">{event.event_name}</span>
                      <code>{event.task_id ?? event.run_id ?? event.execution_session_id ?? "n/a"}</code>
                    </div>
                    <p>{summarizeDiagnosticEvent(event)}</p>
                    {Object.keys(event.details ?? {}).length ? <pre>{formatJson(event.details)}</pre> : null}
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      </section>
    </main>
  );
}
