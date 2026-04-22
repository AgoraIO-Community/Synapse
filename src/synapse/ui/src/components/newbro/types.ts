import type { Persona } from "../../types";

export type NavItem = {
  label: string;
  active: boolean;
};

export type AvatarType = "fox" | "cat" | "bunny" | "bro";

export type BroStatus = "busy" | "idle";

export type BroCardModel = {
  id: string;
  name: string;
  role: string;
  status: BroStatus;
  avatarType: AvatarType;
  taskTitle: string;
  progress: number;
  progressLabel: string;
  progressDetails: string[];
  idleNote: string;
  source: "sample" | "runtime";
};

export type RuntimePersonaInput = Pick<Persona, "persona_id" | "name" | "avatar" | "status" | "current_task_id">;
