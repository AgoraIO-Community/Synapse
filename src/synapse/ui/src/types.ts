export type ConnectionStatus =
  | "booting"
  | "connecting"
  | "connected"
  | "disconnected"
  | "error";

export type SessionActionType = "send_message" | "send_command";

export type TaskStatus =
  | "created"
  | "queued"
  | "running"
  | "waiting_user_input"
  | "paused"
  | "completed"
  | "failed"
  | "cancelled";

export type RunStatus =
  | "created"
  | "assigned"
  | "running"
  | "blocked"
  | "paused"
  | "completed"
  | "failed"
  | "cancelled";

export type TaskCommandType =
  | "pause_task"
  | "cancel_task"
  | "preempt_task"
  | "resume_task"
  | "retry_task";

export interface Task {
  task_id: string;
  root_task_id: string;
  parent_task_id: string | null;
  title: string;
  goal: string;
  status: TaskStatus;
  priority: number;
  interruptible: boolean;
  requires_confirmation: boolean;
  preferred_executor: string | null;
  session_affinity: string | null;
  task_revision: number;
  latest_instruction: string | null;
  metadata: Record<string, unknown>;
}

export interface TaskMutation {
  mutation_id: string;
  task_id: string | null;
  mutation_type: string;
  patch: Record<string, unknown>;
  created_by: string;
  urgency: string;
  effective_scope: string;
  requires_replan: boolean;
}

export interface TaskCommand {
  command_id: string;
  task_id: string;
  command_type: TaskCommandType;
  payload: Record<string, unknown>;
  created_by: string;
  reason: string | null;
}

export interface AgentResumeHandle {
  executor_id: string;
  session_handle: string | null;
  turn_handle: string | null;
  opaque: Record<string, unknown>;
}

export interface QueuedRunRequest {
  queued_request_id: string;
  task_id: string;
  executor_config: Record<string, unknown>;
  latest_instruction: string;
  requested_by_message_id: string | null;
}

export interface ExecutionSession {
  execution_session_id: string;
  task_id: string;
  base_executor_id: string;
  run_ids: string[];
  active_run_id: string | null;
  latest_run_id: string | null;
  latest_resume_handle: AgentResumeHandle | null;
  queued_run_request: QueuedRunRequest | null;
}

export interface ExecutionRun {
  run_id: string;
  task_id: string;
  execution_session_id: string;
  executor_type: string;
  status: RunStatus;
  claimed_by: string | null;
  run_revision: number;
  latest_progress_message: string | null;
  output_summary: string | null;
  block_reason: string | null;
  failure_reason: string | null;
  metadata: Record<string, unknown>;
}

export type ExecutionMode = "undecided" | "lightweight" | "managed";

export interface TaskExecutionMode {
  task_id: string;
  mode: ExecutionMode;
  decided_from_run_id: string | null;
  elapsed_seconds: number;
}

export interface SessionBinding {
  task_id: string;
  execution_session_id: string | null;
  session_id: string | null;
  claimed_by: string | null;
  claim_expires_at: string | null;
  execution_revision: number;
  binding_status: string;
}

export interface TaskSummary {
  task_id: string;
  operational_summary: string | null;
  conversational_summary: string | null;
  latest_user_visible_status: string | null;
  needs_user_input: boolean;
}

export type NotificationCandidateType = "completed" | "blocked" | "needs_input";
export type NotificationDeliveryStatus = "pending" | "emitted" | "suppressed";

export interface NotificationCandidate {
  candidate_id: string;
  task_id: string;
  candidate_type: NotificationCandidateType;
  priority: string;
  summary_short: string;
  source_run_id: string | null;
  created_at: string;
  delivery_status: NotificationDeliveryStatus;
  merge_key: string;
  requires_immediate_delivery: boolean;
}

export interface ConversationHistoryEntry {
  role: string;
  text: string;
  message_id: string;
}

export interface SessionSnapshot {
  session_id: string;
  tasks: Task[];
  execution_sessions: ExecutionSession[];
  execution_runs: ExecutionRun[];
  execution_modes: TaskExecutionMode[];
  bindings: SessionBinding[];
  summaries: TaskSummary[];
  notification_candidates: NotificationCandidate[];
  personas: Persona[];
}

export interface Persona {
  persona_id: string;
  name: string;
  avatar: string;
  base_prompt: string;
  status: "idle" | "busy";
  current_task_id: string | null;
}

export interface ConversationSnapshot {
  session_id: string;
  conversation_history: ConversationHistoryEntry[];
}

export interface SessionResponse {
  session_id: string;
}

export type DiagnosticLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";

export interface DiagnosticEvent {
  sequence: number;
  ts: string;
  level: DiagnosticLevel;
  event_name: string;
  service: string;
  component: string;
  conversation_id: string | null;
  request_id: string | null;
  task_id: string | null;
  run_id: string | null;
  execution_session_id: string | null;
  executor_session_id: string | null;
  notification_id: string | null;
  trace_id: string | null;
  worker_id: string | null;
  executor_type: string | null;
  outcome: string | null;
  reason_code: string | null;
  summary: string;
  details: Record<string, unknown>;
  app_version: string | null;
  git_sha: string | null;
  model_name: string | null;
  settings_fingerprint: string | null;
}

export interface DiagnosticTimelineResponse {
  events: DiagnosticEvent[];
}

export interface SnapshotDiffItem {
  id: string;
  entityKind: string;
  entityId: string;
  changeType: string;
  taskId?: string | null;
  details: string;
}

export interface StreamEventBase {
  sequence: number;
  type: string;
}

export interface SnapshotStreamEvent extends StreamEventBase {
  type: "snapshot";
  snapshot: SessionSnapshot;
}

export interface ActionAcceptedStreamEvent extends StreamEventBase {
  type: "action_accepted";
  request_id: string;
  action_type: SessionActionType;
}

export interface ActionRejectedStreamEvent extends StreamEventBase {
  type: "action_rejected";
  request_id: string;
  action_type: SessionActionType | "unknown";
  error_code: string;
  message: string;
}

export interface AssistantResponseStartedStreamEvent extends StreamEventBase {
  type: "assistant_response_started";
  request_id: string;
}

export interface AssistantResponseDeltaStreamEvent extends StreamEventBase {
  type: "assistant_response_delta";
  request_id: string;
  delta: string;
}

export interface AssistantResponseCompletedStreamEvent extends StreamEventBase {
  type: "assistant_response_completed";
  request_id: string;
  message_id: string;
  reply_text: string;
  conversational_act: string;
  affected_task_ids: string[];
}

export interface AssistantResponseFailedStreamEvent extends StreamEventBase {
  type: "assistant_response_failed";
  request_id: string;
  message: string;
}

export interface ConversationAppendedStreamEvent extends StreamEventBase {
  type: "conversation_appended";
  message_id: string;
  role: "assistant";
  text: string;
  source: "notification" | "system_fallback";
}

export type SessionStreamEvent =
  | SnapshotStreamEvent
  | ActionAcceptedStreamEvent
  | ActionRejectedStreamEvent
  | AssistantResponseStartedStreamEvent
  | AssistantResponseDeltaStreamEvent
  | AssistantResponseCompletedStreamEvent
  | AssistantResponseFailedStreamEvent
  | ConversationAppendedStreamEvent;
