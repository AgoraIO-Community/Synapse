import type { ExecutorNodeRecord, Persona, TaskStatus } from "../../types";

export type NavItem = {
  label: string;
  active: boolean;
};

export type AvatarType = "fox" | "cat" | "bunny" | "bro";

export type BroStatus = "busy" | "idle";
export type BroLiveState = "live" | "offline" | "unbound";

export type BroCardModel = {
  id: string;
  name: string;
  role: string;
  status: BroStatus;
  liveState: BroLiveState;
  executorNodeId: string | null;
  nodeName: string | null;
  avatarType: AvatarType;
  taskTitle: string;
  progress: number;
  progressLabel: string;
  progressDetails: string[];
  idleNote: string;
  source: "sample" | "runtime";
};

export type BroTaskRecord = {
  taskId: string;
  title: string;
  status: TaskStatus;
  statusLabel: string;
  description: string;
  summary: string;
  timeLabel?: string;
};

export type RuntimePersonaInput = Pick<
  Persona,
  "persona_id" | "name" | "avatar" | "status" | "current_task_id" | "executor_node_id" | "bro_detail_session_id"
>;

export type RuntimeExecutorNodeInput = Pick<
  ExecutorNodeRecord,
  "node_id" | "name" | "connection_status"
>;
