import {
  Fragment,
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
  ArrowUp,
  ArrowRight,
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
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "./components/ui/tooltip";
import { VoiceComposerAccessory } from "./components/VoiceComposerAccessory";
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

type TaskEventAnchorMap = Record<string, string>;

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

function MessageBubble({
  entry,
}: {
  entry: ConversationHistoryEntry;
}) {
  const isUser = entry.role === "user";
  return (
    <div className={cn("flex", isUser ? "justify-end pl-12" : "justify-start pr-10")}>
      <div
        className={cn(
          "max-w-[84%] shadow-[0_18px_34px_-28px_rgba(15,23,42,0.18)]",
          isUser
            ? "rounded-[1rem] rounded-tr-[0.3rem] border border-white/78 bg-[linear-gradient(180deg,rgba(255,255,255,0.94),rgba(249,248,246,0.82))] px-4 py-3 text-[#1b201d]"
            : "rounded-[1.05rem] border border-[rgba(214,255,100,0.08)] bg-[linear-gradient(180deg,rgba(29,31,35,0.96),rgba(24,26,30,0.92))] px-4 py-3 text-white backdrop-blur-xl",
        )}
      >
        {!isUser ? (
          <div className="mb-2 flex items-center gap-2 text-[0.66rem] font-bold uppercase tracking-[0.18em] text-[#d6ff64]">
            <Bot className="size-3.5" />
            <span>System</span>
          </div>
        ) : null}
        <p className={cn("whitespace-pre-wrap text-sm leading-6", isUser ? "text-[#1f2421]" : "text-white/82")}>
          {entry.text}
        </p>
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
      <div className="max-w-[84%] rounded-[1.05rem] border border-[rgba(214,255,100,0.12)] bg-[linear-gradient(180deg,rgba(29,31,35,0.96),rgba(24,26,30,0.92))] px-4 py-3 text-white shadow-[0_22px_40px_-32px_rgba(0,0,0,0.55)] backdrop-blur-xl">
        <div className="mb-2 flex items-center justify-between gap-3">
          <div className="inline-flex items-center gap-2 text-[0.66rem] font-bold uppercase tracking-[0.18em] text-[#d6ff64]">
            {liveAssistant.state === "failed" ? (
              <AlertCircle className="size-3.5" />
            ) : liveAssistant.state === "streaming" ? (
              <LoaderCircle className="size-3.5 animate-spin" />
            ) : (
              <CheckCircle2 className="size-3.5" />
            )}
            <span>{statusText}</span>
          </div>
          <span className="text-[0.62rem] font-black uppercase tracking-[0.18em] text-[#d6ff64]/88">
            Live
          </span>
        </div>
        <p className="whitespace-pre-wrap text-sm leading-6 text-white/82">
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
      className="relative w-full text-left"
    >
      <div className="rounded-[1.05rem] border border-[rgba(214,255,100,0.1)] bg-[linear-gradient(180deg,rgba(29,31,35,0.96),rgba(24,26,30,0.92))] px-4 py-3 text-white shadow-[0_22px_40px_-32px_rgba(0,0,0,0.55)] transition hover:-translate-y-0.5 hover:border-[rgba(214,255,100,0.18)]">
        <div className="mb-2 flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-2.5">
            <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-white/8 text-[#d6ff64]">
              <Icon className={cn("size-4", event.status === "running" && "animate-spin")} />
            </span>
            <div className="min-w-0">
              <div className="text-[0.62rem] font-bold uppercase tracking-[0.18em] text-white/40">
                Task update
              </div>
              <h3 className="mt-0.5 text-sm font-semibold tracking-tight text-white">{event.title}</h3>
            </div>
          </div>
          <span className="rounded-full bg-[#d6ff64]/10 px-2.5 py-1 text-[0.6rem] font-black uppercase tracking-[0.18em] text-[#d6ff64]">
            {event.label}
          </span>
        </div>
        <p className="text-sm leading-5 text-slate-300">{event.summary}</p>
        <div className="mt-3 inline-flex items-center gap-1.5 text-[0.64rem] font-bold uppercase tracking-[0.18em] text-white/42">
          <span>Open in workbench</span>
          <ArrowRight className="size-4" />
        </div>
      </div>
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
    <button
      type="button"
      className="flex w-full items-center gap-2.5 rounded-[1rem] border border-white/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(248,247,245,0.82))] px-3.5 py-3 text-left text-sm text-[#202622] shadow-[0_18px_30px_-28px_rgba(15,23,42,0.18),inset_0_1px_0_rgba(255,255,255,0.88)] transition hover:-translate-y-0.5 hover:border-[#d6ff64]/50 hover:bg-white"
      onClick={() => onSelect(prompt)}
    >
      <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#d6ff64]/20 text-[#5b7300]">
        <WandSparkles className="size-3.5" />
      </span>
      <span className="flex-1 leading-5">{prompt}</span>
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
      <div
        className={cn(
          "rounded-[1.1rem] border border-[rgba(214,255,100,0.1)] bg-[linear-gradient(180deg,rgba(29,31,35,0.96),rgba(24,26,30,0.92))] px-4 py-4 text-white shadow-[0_22px_40px_-30px_rgba(0,0,0,0.55)] transition hover:-translate-y-0.5 hover:border-[rgba(214,255,100,0.18)]",
          selected && "ring-1 ring-[#d7ff1f]/35",
        )}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <div className="flex items-center gap-2 text-[0.62rem] font-bold uppercase tracking-[0.18em] text-white/40">
              <Workflow className="size-3.5 text-[#d7ff1f]" />
              <span>{task.preferred_executor ?? "executor:auto"}</span>
              <span className="h-1 w-1 rounded-full bg-white/25" />
              <span>rev {task.task_revision}</span>
            </div>
            <h4 className="text-sm font-semibold text-white">{task.title}</h4>
            <p className="line-clamp-2 text-sm leading-5 text-slate-300">{task.goal}</p>
          </div>
          <span className="rounded-full bg-[#d7ff1f]/10 px-2.5 py-1 text-[0.6rem] font-black uppercase tracking-[0.18em] text-[#d7ff1f]">
            {statusLabel(task.status)}
          </span>
        </div>

        <div className="mt-4 flex items-center gap-3">
          <div className="h-1.5 flex-1 rounded-full bg-white/8 overflow-hidden">
            <div
              className="h-full rounded-full bg-[#d7ff1f] shadow-[0_0_12px_rgba(215,255,31,0.35)]"
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="text-[0.68rem] font-bold text-[#d7ff1f]">{progress}%</span>
        </div>

        <div className="mt-4 rounded-[0.95rem] bg-white/5 px-3 py-3 text-sm leading-5 text-slate-300">
          {summarizeTaskResultForCard(detail)}
        </div>
      </div>
    </button>
  );
}

function TaskFact({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="task-fact">
      <span className="task-fact-label">{label}</span>
      <strong className="task-fact-value">{value}</strong>
    </div>
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
  const [taskEventAnchors, setTaskEventAnchors] = useState<TaskEventAnchorMap>({});
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [taskSelectionPinned, setTaskSelectionPinned] = useState(false);
  const [selectedExecutionSessionId, setSelectedExecutionSessionId] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [pendingCommand, setPendingCommand] = useState<string | null>(null);
  const [mobileWorkbenchOpen, setMobileWorkbenchOpen] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);
  const conversationViewportRef = useRef<HTMLDivElement | null>(null);
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
    setTaskEventAnchors({});
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
          if (event.affected_task_ids.length > 0) {
            setTaskEventAnchors((current) => {
              const next = { ...current };
              for (const taskId of event.affected_task_ids) {
                next[taskId] = event.message_id;
              }
              return next;
            });
          }
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
  const anchoredTaskEventsByMessageId = useMemo(() => {
    const grouped = new Map<string, ConversationTaskEvent[]>();
    for (const event of conversationTaskEvents) {
      const messageId = taskEventAnchors[event.taskId];
      if (!messageId) {
        continue;
      }
      const current = grouped.get(messageId) ?? [];
      current.push(event);
      grouped.set(messageId, current);
    }
    return grouped;
  }, [conversationTaskEvents, taskEventAnchors]);
  const unanchoredConversationTaskEvents = useMemo(
    () => conversationTaskEvents.filter((event) => !taskEventAnchors[event.taskId]),
    [conversationTaskEvents, taskEventAnchors],
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
    if (typeof window !== "undefined" && window.matchMedia("(max-width: 1279px)").matches) {
      setMobileWorkbenchOpen(true);
    }
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
  const isConversationEmpty =
    conversation.length === 0 && !liveAssistant && conversationTaskEvents.length === 0;
  const recentWrites = diagnosticEvents.filter(
    (event) =>
      event.event_name.startsWith("bb.") ||
      event.event_name.startsWith("exec.") ||
      event.event_name.startsWith("notify."),
  );

  const workbench = (
    <Tabs defaultValue="overview" className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="mb-3 shrink-0">
        <div>
          <h2 className="font-['Noto_Sans_SC','Noto_Sans','Geist_Variable',sans-serif] text-[2rem] font-bold tracking-[-0.05em] text-[#1f2521]">
            Workbench
          </h2>
          <p className="mt-1 max-w-[22rem] text-sm leading-6 text-[#5f6863]">
            Task queue first. Execution and diagnostics stay available behind Debug.
          </p>
        </div>
      </div>

      <div className="mb-3 shrink-0 grid grid-cols-3 gap-3">
        <div className="relative rounded-[1.15rem] border border-[rgba(214,255,100,0.1)] bg-[linear-gradient(180deg,rgba(29,31,35,0.96),rgba(24,26,30,0.92))] px-4 py-4 text-white shadow-[0_22px_40px_-30px_rgba(0,0,0,0.55)] transition hover:-translate-y-1 hover:border-[rgba(214,255,100,0.16)]">
          <div className="pointer-events-none absolute inset-x-4 top-0 h-px bg-[linear-gradient(90deg,rgba(255,255,255,0),rgba(214,255,100,0.45),rgba(255,255,255,0))]" />
          <div className="text-[0.62rem] font-bold uppercase tracking-[0.2em] text-white/38">Active</div>
          <div className="mt-2 text-3xl font-black tracking-[-0.06em] text-white">{activeTasks.length}</div>
        </div>
        <div className="relative rounded-[1.15rem] border border-[rgba(214,255,100,0.1)] bg-[linear-gradient(180deg,rgba(29,31,35,0.96),rgba(24,26,30,0.92))] px-4 py-4 text-white shadow-[0_22px_40px_-30px_rgba(0,0,0,0.55)] transition hover:-translate-y-1 hover:border-[rgba(214,255,100,0.16)]">
          <div className="pointer-events-none absolute inset-x-4 top-0 h-px bg-[linear-gradient(90deg,rgba(255,255,255,0),rgba(255,255,255,0.24),rgba(255,255,255,0))]" />
          <div className="text-[0.62rem] font-bold uppercase tracking-[0.2em] text-white/38">Waiting</div>
          <div className="mt-2 text-3xl font-black tracking-[-0.06em] text-white">{blockedTasks.length}</div>
        </div>
        <div className="relative rounded-[1.15rem] border border-[rgba(214,255,100,0.14)] bg-[linear-gradient(180deg,rgba(29,31,35,0.96),rgba(24,26,30,0.92))] px-4 py-4 text-white shadow-[0_22px_40px_-30px_rgba(0,0,0,0.55)] transition hover:-translate-y-1 hover:border-[rgba(214,255,100,0.2)]">
          <div className="pointer-events-none absolute inset-x-4 top-0 h-px bg-[linear-gradient(90deg,rgba(255,255,255,0),rgba(214,255,100,0.55),rgba(255,255,255,0))]" />
          <div className="text-[0.62rem] font-bold uppercase tracking-[0.2em] text-[#d7ff1f]">Done</div>
          <div className="mt-2 text-3xl font-black tracking-[-0.06em] text-white">{completedTasks.length}</div>
        </div>
      </div>

      <div className="mb-3 shrink-0">
        <TabsList className="bg-white/68 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="debug">Debug</TabsTrigger>
        </TabsList>
      </div>

      <TabsContent value="overview" className="mt-0 flex-1 min-h-0 overflow-hidden">
        <ScrollArea className="h-full min-h-0 pr-2">
          <div className="space-y-6 pb-10">
            <section className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold tracking-tight text-[#212723]">Active Tasks</h3>
                <p className="text-[0.65rem] font-bold uppercase tracking-[0.18em] text-[#6d766f]">Queue</p>
              </div>
              {tasks.length === 0 ? (
                <div data-testid="workbench-queue-stack" className="relative pb-2 pt-5">
                  <div className="relative rounded-[1.15rem] border border-[rgba(214,255,100,0.1)] bg-[linear-gradient(180deg,rgba(29,31,35,0.96),rgba(24,26,30,0.92))] px-4 py-4 text-white shadow-[0_22px_40px_-30px_rgba(0,0,0,0.55)]">
                    <div className="text-[0.62rem] font-bold uppercase tracking-[0.18em] text-[#d7ff1f]">Idle</div>
                    <h4 className="mt-2 text-sm font-semibold text-white">No active tasks yet.</h4>
                    <p className="mt-1 text-sm leading-5 text-slate-300">
                      The execution brain has not opened any tasks yet.
                    </p>
                  </div>
                </div>
              ) : (
                <div data-testid="workbench-queue-stack" className="space-y-3">
                  {[...tasks].reverse().map((task) => {
                    const detail = getTaskResultDetail(task.task_id, summaryByTaskId, latestRunByTaskId);
                    const selected = selectedTaskId === task.task_id;
                    return (
                      <div key={task.task_id}>
                        <QueueCard
                          task={task}
                          detail={detail}
                          selected={selected}
                          onSelect={() => {
                            setSelectedTaskId(task.task_id);
                            setTaskSelectionPinned(true);
                          }}
                        />
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            <section className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h3 className="text-lg font-bold tracking-tight text-[#212723]">Task Detail</h3>
                  <p className="mt-1 text-sm text-[#6d766f]">
                    {selectedTask
                      ? "Focused task for execution status and controls."
                      : "Choose a task from the queue to inspect execution detail."}
                  </p>
                </div>
              </div>
              {selectedTask ? (
                <div className="relative rounded-[1.15rem] border border-[rgba(214,255,100,0.1)] bg-[linear-gradient(180deg,rgba(29,31,35,0.96),rgba(24,26,30,0.92))] px-4 py-4 text-white shadow-[0_24px_42px_-32px_rgba(0,0,0,0.55)]">
                  <div className="pointer-events-none absolute right-4 top-4 size-16 rounded-full bg-[radial-gradient(circle,rgba(214,255,100,0.16),rgba(214,255,100,0)_70%)]" />
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-[#d7ff1f]/10 px-2.5 py-1 text-[0.6rem] font-black uppercase tracking-[0.18em] text-[#d7ff1f]">
                      {statusLabel(selectedTask.status)}
                    </span>
                    <span className="rounded-full bg-white/8 px-2.5 py-1 text-[0.6rem] font-bold uppercase tracking-[0.16em] text-white/55">
                      Rev {selectedTask.task_revision}
                    </span>
                    <span className="rounded-full bg-white/8 px-2.5 py-1 text-[0.6rem] font-bold uppercase tracking-[0.16em] text-white/55">
                      {selectedTask.preferred_executor ?? "executor:auto"}
                    </span>
                  </div>
                  <h4 className="mt-3 text-lg font-bold tracking-tight text-white">{selectedTask.title}</h4>
                  <p className="mt-2 text-sm leading-5 text-slate-300">{selectedTask.goal}</p>

                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <div className="rounded-[0.95rem] bg-white/5 px-4 py-3">
                      <p className="text-[0.62rem] font-bold uppercase tracking-[0.18em] text-white/42">
                        Latest result
                      </p>
                      <p className="mt-2 text-sm leading-5 text-slate-300">
                        {selectedTaskResult?.fullText ?? "No result yet."}
                      </p>
                    </div>
                    <div className="rounded-[0.95rem] bg-white/5 px-4 py-3">
                      <p className="text-[0.62rem] font-bold uppercase tracking-[0.18em] text-white/42">
                        Latest instruction
                      </p>
                      <p className="mt-2 text-sm leading-5 text-slate-300">
                        {selectedTask.latest_instruction ?? "n/a"}
                      </p>
                    </div>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2">
                    {(["pause_task", "resume_task", "retry_task", "cancel_task"] as TaskCommandType[])
                      .filter(
                        (command) =>
                          canRunCommand(selectedTask, command) ||
                          pendingCommand === `${selectedTask.task_id}:${command}`,
                      )
                      .map((command) => {
                        const Icon = commandIcon(command);
                        return (
                          <Button
                            key={command}
                            type="button"
                            variant={command === "cancel_task" ? "destructive" : "secondary"}
                            size="sm"
                            disabled={pendingCommand === `${selectedTask.task_id}:${command}`}
                            onClick={() => void handleCommand(selectedTask.task_id, command)}
                            className="bg-white/8 text-white shadow-none hover:bg-white/12"
                          >
                            <Icon className="size-3.5" />
                            {pendingCommand === `${selectedTask.task_id}:${command}` ? "…" : commandLabel(command)}
                          </Button>
                        );
                      })}
                  </div>

                  {selectedSummary ? (
                    <div className="mt-3 rounded-[0.95rem] border border-white/8 bg-white/4 px-4 py-3">
                      <p className="text-[0.62rem] font-bold uppercase tracking-[0.18em] text-white/42">
                        User-facing summary
                      </p>
                      <p className="mt-2 text-sm leading-5 text-slate-300">
                        {selectedSummary.conversational_summary ??
                          selectedSummary.operational_summary ??
                          "n/a"}
                      </p>
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="rounded-[1.15rem] border border-[rgba(214,255,100,0.1)] bg-[linear-gradient(180deg,rgba(29,31,35,0.96),rgba(24,26,30,0.92))] px-4 py-4 text-white shadow-[0_22px_40px_-30px_rgba(0,0,0,0.55)]">
                  <div className="text-[0.62rem] font-bold uppercase tracking-[0.18em] text-white/42">Detail</div>
                  <h4 className="mt-2 text-sm font-semibold text-white">Pick a task from the queue.</h4>
                  <p className="mt-1 text-sm leading-5 text-slate-300">
                    Select a task to inspect its status, result, and controls.
                  </p>
                </div>
              )}
            </section>
          </div>
        </ScrollArea>
      </TabsContent>

      <TabsContent value="debug" className="mt-0 flex-1 min-h-0 overflow-hidden">
        <ScrollArea className="h-full min-h-0 pr-2">
          <div className="space-y-5 pb-10">
            <DebugFeedSection title="Snapshot Diff" empty="Waiting for snapshot changes.">
              {diffItems.length > 0 ? (
                <div className="space-y-3">
                  {diffItems.map((item) => (
                    <div
                      key={item.id}
                      className="rounded-[1rem] border border-[rgba(214,255,100,0.08)] bg-[linear-gradient(180deg,rgba(29,31,35,0.96),rgba(24,26,30,0.92))] px-4 py-4 text-white shadow-[0_22px_40px_-30px_rgba(0,0,0,0.55)]"
                    >
                      <div className="flex items-center gap-2 text-[0.62rem] font-bold uppercase tracking-[0.18em] text-white/40">
                        <span>{item.entityKind}</span>
                        <span>{item.changeType}</span>
                      </div>
                      <p className="mt-2 text-sm leading-5 text-slate-300">{item.details}</p>
                    </div>
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
                    <div
                      key={`${event.sequence}-${index}`}
                      className="rounded-[1rem] border border-[rgba(214,255,100,0.08)] bg-[linear-gradient(180deg,rgba(29,31,35,0.96),rgba(24,26,30,0.92))] px-4 py-4 text-white shadow-[0_22px_40px_-30px_rgba(0,0,0,0.55)]"
                    >
                      <div className="flex items-center justify-between gap-3 text-[0.62rem] font-bold uppercase tracking-[0.18em] text-white/40">
                        <span>{event.event_name}</span>
                        <span>{event.task_id ?? event.run_id ?? event.execution_session_id ?? "n/a"}</span>
                      </div>
                      <p className="mt-2 text-sm leading-5 text-slate-300">{summarizeDiagnosticEvent(event)}</p>
                    </div>
                  ))}
                </div>
              ) : undefined}
            </DebugFeedSection>

            {selectedRun ? (
              <DebugFeedSection title="Selected run" empty="No run selected.">
                <div className="rounded-[1rem] border border-[rgba(214,255,100,0.08)] bg-[linear-gradient(180deg,rgba(29,31,35,0.96),rgba(24,26,30,0.92))] px-4 py-4 text-white shadow-[0_22px_40px_-30px_rgba(0,0,0,0.55)]">
                  <div className="flex flex-wrap gap-2 text-[0.62rem] font-bold uppercase tracking-[0.18em] text-white/40">
                    <span>{selectedRun.executor_type}</span>
                    <span>{selectedRun.status}</span>
                  </div>
                  <p className="mt-2 text-sm leading-5 text-slate-300">
                    {selectedRun.output_summary ??
                      selectedRun.failure_reason ??
                      selectedRun.block_reason ??
                      selectedRun.latest_progress_message ??
                      "No run summary yet."}
                  </p>
                </div>
              </DebugFeedSection>
            ) : null}
          </div>
        </ScrollArea>
      </TabsContent>
    </Tabs>
  );

  useEffect(() => {
    if (isConversationEmpty) {
      return;
    }
    const viewport = conversationViewportRef.current;
    if (!viewport) {
      return;
    }
    viewport.scrollTo({ top: viewport.scrollHeight, behavior: "smooth" });
  }, [conversation.length, conversationTaskEvents.length, liveAssistant, isConversationEmpty]);

  return (
    <TooltipProvider delayDuration={200}>
      <div
        data-testid="workspace-atmosphere"
        className="relative h-screen overflow-hidden bg-[linear-gradient(135deg,#fff8ef_0%,#fcefd9_22%,#ebf4ff_50%,#f5eefe_78%,#edf4ea_100%)] text-[#18211d]"
      >
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 overflow-hidden"
        >
          <div className="absolute -left-[14%] top-[-18%] h-[38rem] w-[38rem] rounded-full bg-[radial-gradient(circle,rgba(255,255,255,0.92)_0%,rgba(255,244,225,0.58)_34%,rgba(255,244,225,0)_72%)] blur-3xl" />
          <div className="absolute left-[18%] top-[8%] h-[28rem] w-[28rem] rounded-full bg-[radial-gradient(circle,rgba(244,226,202,0.58)_0%,rgba(244,226,202,0.16)_42%,rgba(244,226,202,0)_72%)] blur-3xl" />
          <div className="absolute bottom-[-22%] left-[6%] h-[30rem] w-[34rem] rounded-full bg-[radial-gradient(circle,rgba(218,235,247,0.56)_0%,rgba(218,235,247,0.14)_46%,rgba(218,235,247,0)_76%)] blur-3xl" />
          <div className="absolute inset-y-0 right-0 w-full bg-[linear-gradient(90deg,rgba(255,255,255,0)_0%,rgba(64,74,62,0.06)_50%,rgba(17,21,19,0.2)_100%)] xl:w-[52%]" />
          <div className="absolute -right-[12%] top-[-10%] h-[42rem] w-[42rem] rounded-full bg-[radial-gradient(circle,rgba(39,45,41,0.34)_0%,rgba(39,45,41,0.18)_28%,rgba(39,45,41,0.04)_56%,rgba(39,45,41,0)_74%)] blur-3xl" />
          <div className="absolute bottom-[-26%] right-[-10%] h-[40rem] w-[38rem] rounded-full bg-[radial-gradient(circle,rgba(53,64,59,0.3)_0%,rgba(53,64,59,0.15)_32%,rgba(53,64,59,0.03)_58%,rgba(53,64,59,0)_76%)] blur-3xl" />
          <div className="absolute inset-y-0 right-0 hidden w-[48%] bg-[linear-gradient(180deg,rgba(18,22,21,0.06)_0%,rgba(18,22,21,0.16)_40%,rgba(18,22,21,0.28)_100%)] xl:block" />
        </div>

        <div className="app-shell relative h-full w-full overflow-hidden p-3 sm:p-5">
          <div className="app-grid relative grid h-full w-full min-w-0 gap-4 xl:grid-cols-[minmax(0,1.08fr)_minmax(420px,0.92fr)]">
            <section
              data-testid="workspace-left-pane"
              className="relative z-10 flex h-full min-h-0 min-w-0 flex-col px-3 pb-32 pt-5 sm:px-5 sm:pb-36 sm:pt-6 xl:pr-8"
            >
              <h1 className="sr-only">Conversation</h1>

              <div className="absolute right-3 top-4 z-20 sm:right-5 xl:hidden">
                <Sheet open={mobileWorkbenchOpen} onOpenChange={setMobileWorkbenchOpen}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <SheetTrigger asChild>
                        <Button
                          variant="secondary"
                          size="icon"
                          className="h-auto w-auto gap-2 rounded-full bg-white/78 px-3 py-2 shadow-[0_14px_34px_-24px_rgba(15,23,42,0.24)]"
                        >
                          <PanelRightOpen className="size-4" />
                          <span className="whitespace-nowrap text-[0.8rem] font-semibold text-[#1a2a23]">
                            Open workbench
                          </span>
                        </Button>
                      </SheetTrigger>
                    </TooltipTrigger>
                    <TooltipContent>Open workbench</TooltipContent>
                  </Tooltip>
                  <SheetContent
                    side="right"
                    className="border-l border-white/15 bg-[linear-gradient(180deg,rgba(255,248,239,0.96),rgba(236,241,251,0.92))] p-3 sm:p-4"
                  >
                    <div className="flex h-full min-h-0 flex-col rounded-[1.75rem] border border-white/55 bg-[linear-gradient(180deg,rgba(255,255,255,0.72),rgba(247,248,250,0.62))] shadow-[0_24px_50px_-34px_rgba(15,23,42,0.28)] backdrop-blur-xl">
                    <SheetHeader className="border-b border-border/60 px-5 py-5">
                      <SheetTitle>Workbench</SheetTitle>
                      <SheetDescription>
                        Task queue, details, and debug surfaces for the active session.
                      </SheetDescription>
                    </SheetHeader>
                    <div
                      data-testid="mobile-workbench-shell"
                      className="min-h-0 flex-1 px-4 py-4"
                    >
                      {workbench}
                    </div>
                    </div>
                  </SheetContent>
                </Sheet>
              </div>

              <ScrollArea viewportRef={conversationViewportRef} className="flex-1 pr-1 sm:pr-2">
                <div
                  className={cn(
                    "mx-auto flex min-h-full w-full max-w-3xl flex-col gap-4 pb-14",
                    isConversationEmpty ? "justify-center py-10" : "justify-start py-8",
                  )}
                >
                  {actionError ? (
                    <div className="mx-auto w-full max-w-[38rem] rounded-[1.2rem] border border-rose-500/18 bg-[linear-gradient(180deg,rgba(255,241,243,0.88),rgba(255,232,236,0.72))] px-4 py-3 text-sm text-rose-700 shadow-[0_18px_42px_-34px_rgba(190,24,93,0.3)]">
                      {actionError}
                    </div>
                  ) : null}

                  {isConversationEmpty ? (
                    <div className="flex min-h-full flex-col justify-center gap-7">
                      <div className="mx-auto max-w-[36rem] text-center">
                        <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/72 px-3 py-1 text-[0.65rem] font-bold uppercase tracking-[0.22em] text-[#68736c] shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]">
                          <Sparkles className="size-3.5 text-[#7e9862]" />
                          Fresh session
                        </div>
                        <h3 className="font-['Noto_Sans_SC','Noto_Sans','Geist_Variable',sans-serif] text-[2.15rem] leading-[1.02] font-bold tracking-[-0.05em] text-[#1f2521] sm:text-[2.6rem]">
                          Start with a clear instruction.
                        </h3>
                        <p className="mx-auto mt-4 max-w-[32rem] text-[1rem] leading-7 text-[#5e6761]">
                          Ask NewBro to plan, draft, review, summarize, or execute. The workbench
                          will light up as soon as the execution brain opens tasks.
                        </p>
                      </div>
                      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                        {STARTER_PROMPTS.map((prompt) => (
                          <StarterPromptButton key={prompt} prompt={prompt} onSelect={setComposer} />
                        ))}
                      </div>
                    </div>
                  ) : (
                    <>
                      {conversation.map((entry) => (
                        <Fragment key={entry.message_id}>
                          <MessageBubble entry={entry} />
                          {(anchoredTaskEventsByMessageId.get(entry.message_id) ?? []).map((event) => (
                            <TaskEventCard key={event.id} event={event} onSelectTask={focusTask} />
                          ))}
                        </Fragment>
                      ))}
                      {liveAssistant ? <LiveAssistantCard liveAssistant={liveAssistant} /> : null}
                      {unanchoredConversationTaskEvents.map((event) => (
                        <TaskEventCard key={event.id} event={event} onSelectTask={focusTask} />
                      ))}
                    </>
                  )}
                </div>
              </ScrollArea>

              <div className="pointer-events-none absolute inset-x-3 bottom-4 z-20 sm:inset-x-5 sm:bottom-5 xl:right-8">
                <div className="mx-auto max-w-3xl">
                  <div className="pointer-events-auto">
                    <VoiceComposerAccessory />
                  </div>
                  <form className="pointer-events-auto" onSubmit={handleSendMessage}>
                    <div
                      data-testid="conversation-composer-shell"
                      className="rounded-full border border-[rgba(214,255,100,0.12)] bg-[linear-gradient(180deg,rgba(33,35,39,0.98),rgba(28,30,34,0.94))] px-4 py-3 shadow-[0_30px_60px_-32px_rgba(0,0,0,0.58),inset_0_1px_0_rgba(255,255,255,0.05)] backdrop-blur-xl sm:px-5 sm:py-3.5"
                    >
                      <div className="flex items-center gap-2 sm:gap-3">
                        <input
                          value={composer}
                          onChange={(event) => setComposer(event.target.value)}
                          onKeyDown={(event: KeyboardEvent<HTMLInputElement>) => {
                            if (event.key === "Enter" && !event.nativeEvent.isComposing) {
                              event.preventDefault();
                              void handleSendMessage(event as unknown as FormEvent<HTMLFormElement>);
                            }
                          }}
                          placeholder="Issue a system directive..."
                          className="min-h-0 flex-1 border-none bg-transparent px-2 py-2 text-[0.98rem] font-medium text-white shadow-none outline-none placeholder:text-[#74819b] focus-visible:ring-0 sm:text-[1.06rem] sm:placeholder:text-[#7e89a0]"
                        />
                        <Button
                          data-testid="conversation-composer-send"
                          aria-label="Send"
                          type="submit"
                          variant="secondary"
                          disabled={!sessionId || !composer.trim() || isSending}
                          className="size-11 min-h-11 shrink-0 rounded-full bg-[#e9ff77] px-0 text-[#14180c] shadow-[0_18px_36px_-18px_rgba(233,255,119,0.85)] hover:translate-y-0 hover:scale-[1.03] disabled:opacity-100 disabled:bg-[#e9ff77]/82 disabled:text-[#14180c]/70 sm:size-12 sm:min-h-12"
                        >
                          <ArrowUp className="size-5 sm:size-6" />
                        </Button>
                      </div>
                    </div>
                  </form>
                </div>
              </div>
            </section>

            <aside
              data-testid="workspace-right-pane"
              className="relative hidden h-full min-w-0 overflow-hidden xl:flex xl:flex-col xl:py-2 xl:pl-3"
            >
              <div className="relative h-full min-h-0">{workbench}</div>
            </aside>
          </div>
        </div>
      </div>
    </TooltipProvider>
  );
}
