import {
  startTransition,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertCircle,
  Bot,
  CheckCircle2,
  ChevronsRight,
  LoaderCircle,
  MessageSquare,
  PauseCircle,
  PanelRightOpen,
  PlayCircle,
  RotateCcw,
  Sparkles,
  Timer,
  WandSparkles,
  Workflow,
  XCircle,
} from "lucide-react";
import {
  createSession,
  getConversationSnapshot,
  getDiagnosticTimeline,
  getSessionSnapshot,
  openSessionStream,
  sendSocketCommand,
  sendSocketMessage,
} from "./lib/session-client";
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
import { Badge } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "./components/ui/card";
import { ScrollArea } from "./components/ui/scroll-area";
import { Separator } from "./components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "./components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./components/ui/tabs";
import { Textarea } from "./components/ui/textarea";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "./components/ui/tooltip";
import { cn } from "./lib/utils";

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

type ConversationTaskEvent = {
  id: string;
  taskId: string;
  label: string;
  title: string;
  summary: string;
  tone: "success" | "warning" | "destructive" | "default";
  status: Task["status"];
};

const STARTER_PROMPTS = [
  "Draft a clear release note for the current sprint.",
  "Review the active tasks and tell me what needs attention.",
  "Create a plan for polishing the onboarding experience.",
];

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

function commandIcon(command: TaskCommandType) {
  if (command === "pause_task") {
    return PauseCircle;
  }
  if (command === "resume_task") {
    return PlayCircle;
  }
  if (command === "retry_task") {
    return RotateCcw;
  }
  return XCircle;
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

function pickAutoSelectedTask(
  nextSnapshot: SessionSnapshot,
  previous: SessionSnapshot | null,
  currentSelectedTaskId: string | null,
) {
  const previousTasks = new Map(previous?.tasks.map((task) => [task.task_id, task]) ?? []);
  const promotedStatuses = new Set(["completed", "failed", "waiting_user_input", "running"]);
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

function summarizeDiagnosticEvent(event: DiagnosticEvent) {
  const detailKeys = Object.keys(event.details ?? {});
  return detailKeys.length > 0
    ? `${event.event_name} (${detailKeys.join(", ")})`
    : event.event_name;
}

function statusTone(status: Task["status"]): ConversationTaskEvent["tone"] {
  if (status === "completed") {
    return "success";
  }
  if (status === "failed" || status === "cancelled") {
    return "destructive";
  }
  if (status === "waiting_user_input" || status === "paused") {
    return "warning";
  }
  return "default";
}

function statusLabel(status: Task["status"]) {
  if (status === "running" || status === "queued" || status === "created") {
    return "In progress";
  }
  if (status === "waiting_user_input") {
    return "Needs input";
  }
  return status.replaceAll("_", " ");
}

function statusProgress(status: Task["status"]) {
  if (status === "created") return 12;
  if (status === "queued") return 28;
  if (status === "running") return 62;
  if (status === "waiting_user_input") return 76;
  if (status === "paused") return 58;
  if (status === "completed") return 100;
  if (status === "failed") return 100;
  if (status === "cancelled") return 100;
  return 0;
}

function taskStatusVariant(status: Task["status"]): "default" | "secondary" | "success" | "warning" | "destructive" {
  if (status === "completed") {
    return "success";
  }
  if (status === "failed" || status === "cancelled") {
    return "destructive";
  }
  if (status === "waiting_user_input" || status === "paused") {
    return "warning";
  }
  if (status === "running") {
    return "default";
  }
  return "secondary";
}

function eventIcon(status: Task["status"]) {
  if (status === "completed") {
    return CheckCircle2;
  }
  if (status === "failed" || status === "cancelled") {
    return XCircle;
  }
  if (status === "waiting_user_input" || status === "paused") {
    return AlertCircle;
  }
  return LoaderCircle;
}

function buildConversationTaskEvents(
  snapshot: SessionSnapshot | null,
  summaryByTaskId: Map<string, TaskSummary>,
  latestRunByTaskId: Map<string, ExecutionRun>,
): ConversationTaskEvent[] {
  if (!snapshot) {
    return [];
  }
  const tasks = [...snapshot.tasks];
  tasks.sort((a, b) => {
    const rank = (status: Task["status"]) =>
      ({
        running: 0,
        waiting_user_input: 1,
        failed: 2,
        completed: 3,
        paused: 4,
        queued: 5,
        created: 6,
        cancelled: 7,
      })[status];
    return rank(a.status) - rank(b.status);
  });
  return tasks.slice(0, 6).map((task) => {
    const detail = getTaskResultDetail(task.task_id, summaryByTaskId, latestRunByTaskId);
    return {
      id: `event-${task.task_id}-${task.task_revision}`,
      taskId: task.task_id,
      label: statusLabel(task.status),
      title: task.title,
      summary:
        detail?.fullText ||
        task.latest_instruction ||
        task.goal ||
        "The execution brain is tracking this task.",
      tone: statusTone(task.status),
      status: task.status,
    };
  });
}

function statusDotClass(status: ConnectionStatus) {
  if (status === "connected") {
    return "bg-emerald-500";
  }
  if (status === "error" || status === "disconnected") {
    return "bg-rose-500";
  }
  return "bg-amber-500";
}

function MessageBubble({
  entry,
}: {
  entry: ConversationHistoryEntry;
}) {
  const isUser = entry.role === "user";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "chat-bubble max-w-[86%] rounded-[28px] px-4 py-3 shadow-sm sm:px-5",
          isUser ? "chat-bubble-user" : "chat-bubble-assistant",
        )}
      >
        <div className="mb-2 flex items-center justify-between gap-3 text-[11px] font-semibold uppercase tracking-[0.18em] opacity-80">
          <span>{isUser ? "You" : "Assistant"}</span>
          <span className="truncate">{entry.message_id}</span>
        </div>
        <p className="whitespace-pre-wrap text-sm leading-6">{entry.text}</p>
      </div>
    </div>
  );
}

function LiveAssistantCard({ liveAssistant }: { liveAssistant: LiveAssistantBubble }) {
  const statusText =
    liveAssistant.state === "streaming"
      ? "Streaming"
      : liveAssistant.state === "failed"
        ? "Failed"
        : "Completed";
  return (
    <div className="flex justify-start">
      <div className="chat-bubble live-bubble max-w-[86%] rounded-[28px] px-5 py-3">
        <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-700">
          <Bot className="size-3.5" />
          <span>{statusText}</span>
        </div>
        <p className="whitespace-pre-wrap text-sm leading-6 text-foreground">
          {liveAssistant.text || "..."}
        </p>
      </div>
    </div>
  );
}

function TaskEventCard({
  event,
  onSelectTask,
}: {
  event: ConversationTaskEvent;
  onSelectTask: (taskId: string) => void;
}) {
  const Icon = eventIcon(event.status);
  return (
    <button
      type="button"
      onClick={() => onSelectTask(event.taskId)}
      className="w-full text-left"
    >
      <Card className="border-white/70 bg-white/75 transition hover:-translate-y-0.5 hover:bg-white">
        <CardContent className="p-4">
          <div className="mb-3 flex items-start justify-between gap-3">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                <Workflow className="size-3.5" />
                <span>Task update</span>
              </div>
              <h3 className="font-serif text-lg text-foreground">{event.title}</h3>
            </div>
            <Badge variant={taskStatusVariant(event.status)}>{event.label}</Badge>
          </div>
          <div className="flex items-start gap-3 text-sm text-muted-foreground">
            <Icon className={cn("mt-0.5 size-4 shrink-0", event.status === "running" && "animate-spin")} />
            <p className="line-clamp-3">{event.summary}</p>
          </div>
        </CardContent>
      </Card>
    </button>
  );
}

function StarterPromptButton({
  prompt,
  onSelect,
}: {
  prompt: string;
  onSelect: (value: string) => void;
}) {
  return (
    <button type="button" className="starter-chip" onClick={() => onSelect(prompt)}>
      <span className="starter-chip-icon">
        <Sparkles className="size-3.5" />
      </span>
      <span>{prompt}</span>
      <ChevronsRight className="size-4 text-muted-foreground" />
    </button>
  );
}

function QueueCard({
  task,
  detail,
  selected,
  onSelect,
}: {
  task: Task;
  detail: TaskResultDetail | null;
  selected: boolean;
  onSelect: () => void;
}) {
  const progress = statusProgress(task.status);
  return (
    <button type="button" className="w-full text-left" onClick={onSelect}>
      <Card
        className={cn(
          "queue-card border-white/70 bg-white/70 transition hover:-translate-y-0.5 hover:bg-white",
          selected && "ring-2 ring-primary/30",
        )}
      >
        <CardContent className="space-y-4 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1">
              <div className="queue-card-kicker">
                <Workflow className="size-3.5" />
                <span>{task.preferred_executor ?? "executor:auto"}</span>
              </div>
              <h4 className="font-medium text-foreground">{task.title}</h4>
              <p className="text-sm text-muted-foreground">{task.goal}</p>
            </div>
            <Badge variant={taskStatusVariant(task.status)}>{statusLabel(task.status)}</Badge>
          </div>

          <div className="queue-progress">
            <div className="queue-progress-track">
              <div className="queue-progress-fill" style={{ width: `${progress}%` }} />
            </div>
            <span className="queue-progress-value">{progress}%</span>
          </div>

          <div className="rounded-2xl bg-muted/70 p-3 text-sm text-muted-foreground">
            {summarizeTaskResultForCard(detail)}
          </div>
        </CardContent>
      </Card>
    </button>
  );
}

function DebugFeedSection({
  title,
  empty,
  children,
}: {
  title: string;
  empty: string;
  children?: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-serif text-lg text-foreground">{title}</h3>
      </div>
      {children || (
        <Card className="border-dashed border-border/80 bg-white/55">
          <CardContent className="p-4 text-sm text-muted-foreground">{empty}</CardContent>
        </Card>
      )}
    </section>
  );
}

export default function App() {
  const queryClient = useQueryClient();
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
  const [mobileWorkbenchOpen, setMobileWorkbenchOpen] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);
  const latestSnapshotRef = useRef<SessionSnapshot | null>(null);
  const latestDiagnosticSequenceRef = useRef(0);
  const refreshDiagnosticsRef = useRef<(() => Promise<void>) | null>(null);
  const isPageVisibleRef = useRef(isPageVisible);
  const taskSelectionPinnedRef = useRef(false);
  const pendingCommandRequestsRef = useRef<Map<string, string>>(new Map());

  const sessionQuery = useQuery<SessionResponse>({
    queryKey: ["session"],
    queryFn: createSession,
    staleTime: Infinity,
    retry: false,
  });

  const sessionId = sessionQuery.data?.session_id ?? null;

  const snapshotQuery = useQuery<SessionSnapshot>({
    queryKey: ["session", sessionId, "snapshot"],
    queryFn: () => getSessionSnapshot(sessionId!),
    enabled: Boolean(sessionId),
    staleTime: Infinity,
    retry: false,
  });

  const conversationQuery = useQuery<ConversationSnapshot>({
    queryKey: ["session", sessionId, "conversation"],
    queryFn: () => getConversationSnapshot(sessionId!),
    enabled: Boolean(sessionId),
    staleTime: Infinity,
    retry: false,
  });

  useEffect(() => {
    if (sessionQuery.error) {
      setConnectionStatus("error");
      setActionError(
        sessionQuery.error instanceof Error ? sessionQuery.error.message : "Failed to create session.",
      );
    }
  }, [sessionQuery.error]);

  useEffect(() => {
    if (!sessionId) {
      return;
    }
    setDiagnosticEvents([]);
    latestDiagnosticSequenceRef.current = 0;
  }, [sessionId]);

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
    if (snapshotQuery.data) {
      startTransition(() => {
        setSnapshot(snapshotQuery.data);
        latestSnapshotRef.current = snapshotQuery.data;
        setConnectionStatus((current) => {
          if (current === "booting") {
            return "connecting";
          }
          return current;
        });
      });
    }
  }, [snapshotQuery.data]);

  useEffect(() => {
    if (snapshotQuery.error) {
      setConnectionStatus("error");
      setActionError(
        snapshotQuery.error instanceof Error ? snapshotQuery.error.message : "Failed to load session data.",
      );
    }
  }, [snapshotQuery.error]);

  useEffect(() => {
    if (conversationQuery.data) {
      startTransition(() => {
        setConversationSnapshot(conversationQuery.data);
      });
    }
  }, [conversationQuery.data]);

  useEffect(() => {
    if (conversationQuery.error) {
      setActionError(
        conversationQuery.error instanceof Error
          ? conversationQuery.error.message
          : "Failed to refresh conversation projection.",
      );
    }
  }, [conversationQuery.error]);

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
        startTransition(() => {
          setDiagnosticEvents((current) => {
            const next = [...current, ...response.events];
            return next.length > 200 ? next.slice(next.length - 200) : next;
          });
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
          queryClient.setQueryData(["session", sessionId, "snapshot"], nextSnapshot);
          startTransition(() => {
            setConnectionStatus("connected");
            setPreviousSnapshot(previous);
            setSnapshot(nextSnapshot);
            latestSnapshotRef.current = nextSnapshot;
            setSelectedTaskId((current) =>
              taskSelectionPinnedRef.current
                ? current
                : pickAutoSelectedTask(nextSnapshot, previous, current),
            );
          });
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
          queryClient.setQueryData(
            ["session", sessionId, "conversation"],
            (current: ConversationSnapshot | undefined) => {
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
            },
          );
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
          queryClient.setQueryData(
            ["session", sessionId, "conversation"],
            (current: ConversationSnapshot | undefined) => {
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
            },
          );
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
  const conversationTaskEvents = useMemo(
    () => buildConversationTaskEvents(snapshot, summaryByTaskId, latestRunByTaskId),
    [snapshot, summaryByTaskId, latestRunByTaskId],
  );

  const selectedTask = snapshot?.tasks.find((task) => task.task_id === selectedTaskId) ?? null;
  const selectedSummary = selectedTaskId ? summaryByTaskId.get(selectedTaskId) ?? null : null;
  const toolCallHistory = useMemo(
    () =>
      diagnosticEvents.filter((event) => event.event_name === "comm.tool.called").slice(-50).reverse(),
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
    queryClient.setQueryData(
      ["session", sessionId, "conversation"],
      (current: ConversationSnapshot | undefined) => {
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
      },
    );
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

  function focusTask(taskId: string) {
    setSelectedTaskId(taskId);
    setTaskSelectionPinned(true);
    setMobileWorkbenchOpen(true);
  }

  const tasks = snapshot?.tasks ?? [];
  const activeTasks = tasks.filter(
    (task) => !["completed", "failed", "cancelled"].includes(task.status),
  );
  const completedTasks = tasks.filter((task) => task.status === "completed");
  const blockedTasks = tasks.filter((task) =>
    ["failed", "paused", "waiting_user_input"].includes(task.status),
  );
  const conversation = conversationSnapshot?.conversation_history ?? [];
  const recentWrites = diagnosticEvents.filter(
    (event) =>
      event.event_name.startsWith("bb.") ||
      event.event_name.startsWith("exec.") ||
      event.event_name.startsWith("notify."),
  );

  const workbench = (
    <Card className="h-full overflow-hidden flex flex-col">
      <CardHeader className="gap-4 border-b border-border/60 bg-white/60 pb-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              <Sparkles className="size-3.5" />
              <span>Execution visibility</span>
            </div>
            <CardTitle className="text-2xl">Workbench</CardTitle>
            <CardDescription>
              Task queue first. Execution and diagnostics stay available behind Debug.
            </CardDescription>
          </div>
          <Badge variant="secondary">{tasks.length} tracked</Badge>
        </div>
        <div className="workbench-summary-grid">
          <div className="workbench-summary-card">
            <span className="workbench-summary-label">Active</span>
            <strong>{activeTasks.length}</strong>
          </div>
          <div className="workbench-summary-card">
            <span className="workbench-summary-label">Waiting</span>
            <strong>{blockedTasks.length}</strong>
          </div>
          <div className="workbench-summary-card">
            <span className="workbench-summary-label">Done</span>
            <strong>{completedTasks.length}</strong>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex flex-1 min-h-0 flex-col p-0">
        <Tabs defaultValue="overview" className="flex h-full min-h-0 flex-col">
          <div className="border-b border-border/60 px-6 py-4">
            <TabsList>
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="debug">Debug</TabsTrigger>
            </TabsList>
          </div>
          <TabsContent value="overview" className="mt-0 flex-1 min-h-0 overflow-hidden">
            <ScrollArea className="h-full">
              <div className="space-y-6 p-6">
                <section className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="font-serif text-xl text-foreground">Active Tasks</h3>
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                      Queue
                    </p>
                  </div>
                  {tasks.length === 0 ? (
                    <Card className="border-dashed border-border/80 bg-white/55">
                      <CardContent className="p-4 text-sm text-muted-foreground workbench-empty">
                        <div className="workbench-empty-kicker">Idle</div>
                        <p>The execution brain has not opened any tasks yet.</p>
                      </CardContent>
                    </Card>
                  ) : (
                    <div className="space-y-3">
                      {tasks.map((task) => {
                        const detail = getTaskResultDetail(task.task_id, summaryByTaskId, latestRunByTaskId);
                        const selected = selectedTaskId === task.task_id;
                        return (
                          <QueueCard
                            key={task.task_id}
                            task={task}
                            detail={detail}
                            selected={selected}
                            onSelect={() => {
                              setSelectedTaskId(task.task_id);
                              setTaskSelectionPinned(true);
                            }}
                          />
                        );
                      })}
                    </div>
                  )}
                </section>

                <Separator />

                <section className="space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <h3 className="font-serif text-xl text-foreground">Task Detail</h3>
                      <p className="text-sm text-muted-foreground">
                        {selectedTask
                          ? "Focused task for execution status and controls."
                          : "Choose a task from the queue to inspect execution detail."}
                      </p>
                    </div>
                  </div>
                  {selectedTask ? (
                    <Card className="border-white/75 bg-white/80">
                      <CardContent className="space-y-5 p-5">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant={taskStatusVariant(selectedTask.status)}>
                            {statusLabel(selectedTask.status)}
                          </Badge>
                          <Badge variant="secondary">Rev {selectedTask.task_revision}</Badge>
                          <Badge variant="secondary">
                            {selectedTask.preferred_executor ?? "executor:auto"}
                          </Badge>
                        </div>
                        <div className="space-y-2">
                          <div className="detail-kicker">
                            <Activity className="size-3.5" />
                            <span>Selected task</span>
                          </div>
                          <h4 className="font-serif text-2xl">{selectedTask.title}</h4>
                          <p className="text-sm text-muted-foreground">{selectedTask.goal}</p>
                        </div>
                        <div className="grid gap-3 md:grid-cols-2">
                          <div className="rounded-2xl bg-muted/70 p-4">
                            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                              Latest result
                            </p>
                            <p className="mt-2 text-sm leading-6 text-foreground">
                              {selectedTaskResult?.fullText ?? "No result yet."}
                            </p>
                          </div>
                          <div className="rounded-2xl bg-muted/70 p-4">
                            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                              Latest instruction
                            </p>
                            <p className="mt-2 text-sm leading-6 text-foreground">
                              {selectedTask.latest_instruction ?? "n/a"}
                            </p>
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-2 command-pill-row">
                          {(["pause_task", "resume_task", "retry_task", "cancel_task"] as TaskCommandType[]).map(
                            (command) => {
                              const Icon = commandIcon(command);
                              return (
                              <Button
                                key={command}
                                type="button"
                                variant={command === "cancel_task" ? "destructive" : "secondary"}
                                size="sm"
                                disabled={
                                  !canRunCommand(selectedTask, command) ||
                                  pendingCommand === `${selectedTask.task_id}:${command}`
                                }
                                onClick={() => void handleCommand(selectedTask.task_id, command)}
                              >
                                <Icon className="size-3.5" />
                                {pendingCommand === `${selectedTask.task_id}:${command}` ? "…" : commandLabel(command)}
                              </Button>
                            );
                            },
                          )}
                        </div>
                        {selectedSummary ? (
                          <div className="rounded-2xl border border-border/60 bg-background/60 p-4">
                            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                              User-facing summary
                            </p>
                            <p className="mt-2 text-sm leading-6 text-foreground">
                              {selectedSummary.conversational_summary ??
                                selectedSummary.operational_summary ??
                                "n/a"}
                            </p>
                          </div>
                        ) : null}
                      </CardContent>
                    </Card>
                  ) : (
                    <Card className="border-dashed border-border/80 bg-white/55">
                      <CardContent className="p-4 text-sm text-muted-foreground">
                        Select a task to inspect its status, result, and controls.
                      </CardContent>
                    </Card>
                  )}
                </section>
              </div>
            </ScrollArea>
          </TabsContent>
          <TabsContent value="debug" className="mt-0 flex-1 min-h-0 overflow-hidden">
            <ScrollArea className="h-full">
              <div className="space-y-6 p-6">
                <DebugFeedSection title="Snapshot Diff" empty="Waiting for snapshot changes.">
                  {diffItems.length > 0 ? (
                    <div className="space-y-3">
                      {diffItems.map((item) => (
                        <Card key={item.id} className="border-white/70 bg-white/70">
                          <CardContent className="space-y-2 p-4">
                            <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                              <Badge variant="secondary">{item.entityKind}</Badge>
                              <span>{item.changeType}</span>
                            </div>
                            <p className="text-sm text-foreground">{item.details}</p>
                            <code className="text-xs text-muted-foreground">{item.entityId}</code>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  ) : undefined}
                </DebugFeedSection>

                <DebugFeedSection
                  title="Execution & diagnostics"
                  empty="No execution diagnostics have been recorded yet."
                >
                  {recentWrites.length > 0 ? (
                    <div className="space-y-3">
                      {[...recentWrites].reverse().map((event, index) => (
                        <Card
                          key={`${event.sequence}-${index}`}
                          className="border-white/70 bg-white/70"
                        >
                          <CardContent className="space-y-2 p-4">
                            <div className="flex items-center justify-between gap-3 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                              <span>{event.event_name}</span>
                              <span>
                                {event.task_id ?? event.run_id ?? event.execution_session_id ?? "n/a"}
                              </span>
                            </div>
                            <p className="text-sm text-foreground">{summarizeDiagnosticEvent(event)}</p>
                            {Object.keys(event.details ?? {}).length ? (
                              <pre className="overflow-x-auto rounded-2xl bg-muted/70 p-3 text-xs text-muted-foreground">
                                {formatJson(event.details)}
                              </pre>
                            ) : null}
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  ) : undefined}
                </DebugFeedSection>

                <DebugFeedSection title="Tool calls" empty="No tool calls recorded yet.">
                  {toolCallHistory.length > 0 ? (
                    <div className="space-y-3">
                      {toolCallHistory.map((event) => (
                        <Card key={event.sequence} className="border-white/70 bg-white/70">
                          <CardContent className="space-y-2 p-4">
                            <div className="flex items-center justify-between gap-3 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                              <span>{event.event_name}</span>
                              <span>{event.outcome ?? "n/a"}</span>
                            </div>
                            <p className="text-sm text-foreground">{event.summary}</p>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  ) : undefined}
                </DebugFeedSection>

                {selectedRun ? (
                  <DebugFeedSection title="Selected run" empty="No run selected.">
                    <Card className="border-white/70 bg-white/70">
                      <CardContent className="space-y-3 p-4">
                        <div className="flex flex-wrap gap-2">
                          <Badge variant="secondary">{selectedRun.executor_type}</Badge>
                          <Badge variant={taskStatusVariant(selectedRun.status as Task["status"])}>
                            {selectedRun.status}
                          </Badge>
                        </div>
                        <p className="text-sm text-foreground">
                          {selectedRun.output_summary ??
                            selectedRun.failure_reason ??
                            selectedRun.block_reason ??
                            selectedRun.latest_progress_message ??
                            "No run summary yet."}
                        </p>
                        <pre className="overflow-x-auto rounded-2xl bg-muted/70 p-3 text-xs text-muted-foreground">
                          {formatJson(selectedRun.metadata)}
                        </pre>
                      </CardContent>
                    </Card>
                  </DebugFeedSection>
                ) : null}
              </div>
            </ScrollArea>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );

  return (
    <TooltipProvider delayDuration={200}>
      <div className="h-screen overflow-hidden p-3 sm:p-5">
        <div className="grid h-full gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(380px,0.9fr)]">
          <Card className="h-full overflow-hidden flex flex-col">
            <CardHeader className="gap-5 border-b border-border/60 bg-white/60 pb-5">
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                    <WandSparkles className="size-3.5" />
                    <span>Synapse Runtime</span>
                  </div>
                  <div>
                    <CardTitle className="text-3xl sm:text-4xl">Conversation</CardTitle>
                    <CardDescription className="mt-2 max-w-2xl text-sm leading-6">
                      Chat-first control surface for the communication brain. Task updates stay visible
                      in context while the execution brain works in the background.
                    </CardDescription>
                  </div>
                </div>
                <div className="flex flex-col items-end gap-3">
                  <div className="inline-flex items-center gap-3 rounded-full border border-border/70 bg-white/85 px-4 py-2 text-sm text-muted-foreground shadow-sm status-pill-modern">
                    <span className={cn("size-2.5 rounded-full", statusDotClass(connectionStatus))} />
                    <span className="capitalize">{connectionStatus}</span>
                    {sessionId ? <code className="hidden text-xs sm:inline">{sessionId}</code> : null}
                  </div>
                  <Sheet open={mobileWorkbenchOpen} onOpenChange={setMobileWorkbenchOpen}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <SheetTrigger asChild>
                          <Button variant="secondary" size="icon" className="xl:hidden">
                            <PanelRightOpen className="size-4" />
                            <span className="sr-only">Open workbench</span>
                          </Button>
                        </SheetTrigger>
                      </TooltipTrigger>
                      <TooltipContent>Open workbench</TooltipContent>
                    </Tooltip>
                    <SheetContent side="right" className="p-0">
                      <SheetHeader className="border-b border-border/60 p-6">
                        <SheetTitle>Workbench</SheetTitle>
                        <SheetDescription>
                          Task queue, details, and debug surfaces for the active session.
                        </SheetDescription>
                      </SheetHeader>
                      <div className="h-[calc(100%-98px)]">{workbench}</div>
                    </SheetContent>
                  </Sheet>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <Badge variant="secondary" className="gap-1.5">
                  <MessageSquare className="size-3.5" />
                  {conversation.length} messages
                </Badge>
                <Badge variant="secondary" className="gap-1.5">
                  <PlayCircle className="size-3.5" />
                  {activeTasks.length} live tasks
                </Badge>
                <Badge variant="secondary" className="gap-1.5">
                  <Timer className="size-3.5" />
                  {conversationTaskEvents.length} task updates
                </Badge>
                {lastCommandStatus ? (
                  <Badge variant={lastCommandStatus === "accepted" ? "success" : "destructive"}>
                    command {lastCommandStatus}
                  </Badge>
                ) : null}
              </div>

              {activeTasks.length > 0 ? (
                <div className="activity-rail">
                  {activeTasks.slice(0, 3).map((task) => (
                    <button
                      key={task.task_id}
                      type="button"
                      className="activity-rail-item"
                      onClick={() => focusTask(task.task_id)}
                    >
                      <div className="activity-rail-item-top">
                        <span className={cn("activity-rail-dot", task.status === "running" && "is-live")} />
                        <span>{task.title}</span>
                      </div>
                      <span className="activity-rail-item-bottom">{statusLabel(task.status)}</span>
                    </button>
                  ))}
                </div>
              ) : conversation.length === 0 ? (
                <div className="starter-grid">
                  {STARTER_PROMPTS.map((prompt) => (
                    <StarterPromptButton key={prompt} prompt={prompt} onSelect={setComposer} />
                  ))}
                </div>
              ) : null}

              {actionError ? (
                <div className="rounded-3xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-700">
                  {actionError}
                </div>
              ) : null}
            </CardHeader>

            <CardContent className="flex flex-1 min-h-0 flex-col p-0">
              <ScrollArea className="flex-1 px-3 py-4 sm:px-5">
                <div className="mx-auto flex max-w-3xl flex-col gap-4 pb-6">
                  {conversation.length === 0 && !liveAssistant && conversationTaskEvents.length === 0 ? (
                    <Card className="border-dashed border-border/80 bg-white/55 empty-chat-card">
                      <CardContent className="p-6 text-sm text-muted-foreground">
                        <div className="empty-chat-eyebrow">Fresh session</div>
                        <h3 className="font-serif text-2xl text-foreground">
                          Start with a clear instruction.
                        </h3>
                        <p className="empty-chat-copy">
                          Ask Synapse to plan, draft, review, summarize, or execute. The workbench
                          will light up as soon as the execution brain opens tasks.
                        </p>
                      </CardContent>
                    </Card>
                  ) : null}
                  {conversation.map((entry) => (
                    <MessageBubble key={entry.message_id} entry={entry} />
                  ))}
                  {liveAssistant ? <LiveAssistantCard liveAssistant={liveAssistant} /> : null}
                  {conversationTaskEvents.map((event) => (
                    <TaskEventCard key={event.id} event={event} onSelectTask={focusTask} />
                  ))}
                </div>
              </ScrollArea>

              <div className="border-t border-border/60 bg-white/60 p-3 sm:p-5 composer-shell">
                <div className="mx-auto max-w-3xl">
                  <form className="space-y-3" onSubmit={handleSendMessage}>
                    <Textarea
                      value={composer}
                      onChange={(event) => setComposer(event.target.value)}
                      onKeyDown={(event: KeyboardEvent<HTMLTextAreaElement>) => {
                        if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                          event.preventDefault();
                          void handleSendMessage(event as unknown as FormEvent<HTMLFormElement>);
                        }
                      }}
                      placeholder="Ask Synapse to plan, execute, or inspect work..."
                      rows={4}
                    />
                    <div className="composer-actions flex flex-wrap items-center justify-between gap-3">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                        Shift + Enter for a newline
                      </p>
                      <Button type="submit" disabled={!sessionId || !composer.trim() || isSending}>
                        {isSending ? "Sending…" : "Send"}
                      </Button>
                    </div>
                  </form>

                  {lastAssistantResponse ? (
                    <div className="reply-summary-card mt-4 rounded-[28px] border border-border/60 bg-background/65 p-4">
                      <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                        <Bot className="size-3.5" />
                        <span>Latest assistant reply</span>
                      </div>
                      <p className="text-sm leading-6 text-foreground">{lastAssistantResponse.reply_text}</p>
                    </div>
                  ) : null}
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="hidden h-full xl:block">{workbench}</div>
        </div>
      </div>
    </TooltipProvider>
  );
}
