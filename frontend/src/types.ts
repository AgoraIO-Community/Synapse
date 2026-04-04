export type ConnectionStatus = "booting" | "connecting" | "connected" | "disconnected" | "error";

export type StreamCategory = "communication" | "task" | "execution" | "context" | "system";

export type TaskStatus =
  | "queued"
  | "running"
  | "blocked"
  | "paused"
  | "canceled"
  | "failed"
  | "done";

export type CommandType = "pause_task" | "resume_task" | "cancel_task";

export interface SessionResponse {
  session_id: string;
}

export interface MessageResponse {
  message_id: string;
  routing_decision: Record<string, unknown>;
  action_bundle: Record<string, unknown>;
}

export interface Task {
  task_id: string;
  root_task_id: string;
  parent_task_id: string | null;
  title: string;
  goal: string;
  status: TaskStatus;
  priority: string;
  assigned_executor: string | null;
  candidate_executors: string[];
  output_summary: string | null;
  block_reason: string | null;
  failure_reason: string | null;
  latest_instruction: string | null;
  updated_at: string;
}

export interface SessionSnapshot {
  session_id: string;
  conversation_state: Record<string, unknown>;
  task_registry: Task[];
  strategy_state: Record<string, unknown>;
  pending_clarifications: Array<Record<string, unknown>>;
  last_sequence: number;
  timestamp: string;
}

export interface CommunicationAction {
  action_id: string;
  action_type: string;
  target_task_id: string | null;
  reason: string | null;
  render_text: string | null;
}

export interface CommunicationEventPayload {
  event_id: string;
  session_id: string;
  source: string;
  action: CommunicationAction;
  timestamp: string;
}

export interface ExecutionEventPayload {
  event_id: string;
  task_id: string;
  executor_id: string;
  event_type: string;
  status: TaskStatus;
  progress_message: string | null;
  progress_percent: number | null;
  source: string;
  timestamp: string;
}

export interface StreamEvent {
  sequence: number;
  stream_event_id: string;
  session_id: string;
  category: StreamCategory;
  event_type: string;
  source: string;
  related_task_id: string | null;
  related_message_id: string | null;
  timestamp: string;
  payload: Record<string, unknown>;
}

export interface TimelineMessage {
  id: string;
  kind: "user" | "assistant";
  text: string;
  timestamp: string;
  taskId?: string | null;
}
