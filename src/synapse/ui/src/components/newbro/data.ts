import { Home, Settings, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { BroCardModel, NavItem } from "./types";

export const navItems: Array<NavItem & { icon: LucideIcon }> = [
  { label: "Home", icon: Home, active: false },
  { label: "Bros", icon: Users, active: false },
  { label: "Settings", icon: Settings, active: false },
];

export const sampleBros: BroCardModel[] = [
  {
    id: "atlas",
    name: "Atlas",
    role: "Travel researcher",
    status: "busy",
    avatarType: "fox",
    taskTitle: "Compare routes and fares",
    progress: 72,
    progressLabel: "72% synced",
    progressDetails: [
      "Checked 12 route combinations across air and rail.",
      "Shortlisted 3 lower-fare options for review.",
      "Verifying refund rules and transfer risk.",
    ],
    idleNote: "Currently searching across airline and rail websites.",
    source: "sample",
  },
  {
    id: "scout",
    name: "Scout",
    role: "Availability checker",
    status: "idle",
    avatarType: "cat",
    taskTitle: "Waiting for assignment",
    progress: 0,
    progressLabel: "Idle",
    progressDetails: [
      "Ready to verify schedules and remaining inventory.",
      "Can jump in when a route is selected.",
    ],
    idleNote: "Can verify timing, inventory, and constraints.",
    source: "sample",
  },
  {
    id: "muse",
    name: "Muse",
    role: "Planner",
    status: "idle",
    avatarType: "bunny",
    taskTitle: "Waiting for assignment",
    progress: 0,
    progressLabel: "Idle",
    progressDetails: [
      "Ready to synthesize options into a final recommendation.",
      "Can structure tradeoffs and next steps clearly.",
    ],
    idleNote: "Can synthesize options into a clear next step.",
    source: "sample",
  },
  {
    id: "forge",
    name: "Forge",
    role: "Operator",
    status: "busy",
    avatarType: "bro",
    taskTitle: "Prepare execution steps",
    progress: 43,
    progressLabel: "43% prepared",
    progressDetails: [
      "Drafted booking sequence for the top 2 options.",
      "Checking hold windows and payment ordering.",
      "Preparing fallback flow if preferred option fails.",
    ],
    idleNote: "Can turn decisions into concrete actions.",
    source: "sample",
  },
];
