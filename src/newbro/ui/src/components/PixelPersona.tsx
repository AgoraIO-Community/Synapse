/**
 * PixelPersona — displays a persona's avatar image with status animation.
 */

import { cn } from "../lib/utils";

type PersonaState = "idle" | "working" | "done" | "failed" | "waiting";

const AVATAR_IMAGES = [
  "/avatars/avatar-01.png",
  "/avatars/avatar-02.png",
  "/avatars/avatar-03.png",
  "/avatars/avatar-04.png",
  "/avatars/avatar-05.png",
];

export { AVATAR_IMAGES };

export function PixelPersona({
  name,
  avatar,
  state = "idle",
  size = 32,
  className,
}: {
  name: string;
  avatar: string;
  state?: PersonaState;
  size?: number;
  className?: string;
}) {
  // avatar is either an image path like "/avatars/avatar-01.png" or a legacy emoji
  const isImage = avatar.startsWith("/");

  return (
    <div
      className={cn("relative inline-flex flex-col items-center gap-1", className)}
      title={name}
    >
      <div
        className={cn(
          "relative overflow-hidden rounded-full",
          state === "working" && "animate-pixel-bounce",
          state === "done" && "animate-pixel-celebrate",
          state === "failed" && "opacity-50",
          state === "waiting" && "animate-pulse",
        )}
        style={{ width: size, height: size }}
      >
        {isImage ? (
          <img
            src={avatar}
            alt={name}
            className="h-full w-full object-cover"
            draggable={false}
          />
        ) : (
          <span className="flex h-full w-full items-center justify-center text-lg">
            {avatar}
          </span>
        )}
      </div>
      <span className="text-[0.55rem] font-bold tracking-wide text-white/80">{name}</span>
    </div>
  );
}

export function taskStatusToPersonaState(status: string): PersonaState {
  switch (status) {
    case "running":
      return "working";
    case "completed":
      return "done";
    case "failed":
    case "cancelled":
      return "failed";
    case "waiting_user_input":
    case "waiting_executor":
    case "paused":
      return "waiting";
    default:
      return "idle";
  }
}
