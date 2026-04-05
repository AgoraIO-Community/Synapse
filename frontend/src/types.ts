export type ConnectionStatus =
  | "booting"
  | "connecting"
  | "connected"
  | "disconnected"
  | "error";

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

export type BlackboardWriteKind =
  | "task"
  | "mutation"
  | "command"
  | "run"
  | "session"
  | "binding"
  | "summary";

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

export interface BlackboardWriteEvent {
  kind: BlackboardWriteKind;
  entity_id: string | null;
  task_id: string | null;
  payload: Record<string, unknown>;
}

export interface ConversationHistoryEntry {
  role: string;
  text: string;
  message_id: string;
}

export interface SessionSnapshot {
  session_id: string;
  tasks: Task[];
  mutations: TaskMutation[];
  commands: TaskCommand[];
  execution_sessions: ExecutionSession[];
  execution_runs: ExecutionRun[];
  bindings: SessionBinding[];
  summaries: TaskSummary[];
  recent_blackboard_writes: BlackboardWriteEvent[];
  conversation_history: ConversationHistoryEntry[];
}

export interface SessionResponse {
  session_id: string;
}

export interface ToolInvocationSummary {
  tool_name: string;
  args: Record<string, unknown>;
}

export interface MessageResponse {
  message_id: string;
  reply_text: string;
  conversational_act: string;
  affected_task_ids: string[];
  tool_invocations: ToolInvocationSummary[];
}

export interface CommandResponse {
  command_id: string;
  status: string;
  affected_task_ids: string[];
}

export interface SnapshotDiffItem {
  id: string;
  entityKind: string;
  entityId: string;
  changeType: string;
  taskId?: string | null;
  details: string;
}
