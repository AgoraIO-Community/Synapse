import { motion } from "framer-motion";
import { useEffect, useRef } from "react";
import type { ConversationHistoryEntry } from "../../types";
import { SectionHeader } from "./SectionHeader";

export function ConversationMemory({
  phase,
  messages,
  error,
  lastToolkitMessage,
}: {
  phase: "idle" | "loading" | "connected" | "error";
  messages: ConversationHistoryEntry[];
  error: string | null;
  lastToolkitMessage: string | null;
}) {
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const messageItems = messages.filter((item) => Boolean(item.text?.trim()));
  const showMetaChips = messageItems.length > 0;

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) {
      return;
    }
    viewport.scrollTo({ top: viewport.scrollHeight, behavior: "smooth" });
  }, [phase, messageItems.length]);

  return (
    <div data-testid="conversation-memory" className="flex min-h-0 max-w-[400px] flex-1 flex-col space-y-3">
      <SectionHeader
        title="Interaction memory"
        trailing={
          showMetaChips ? (
            <div className="flex items-center gap-2">
              {messageItems.length > 0 ? (
                <div className="rounded-full border border-neutral-200 px-2.5 py-1 text-[11px] text-neutral-500">
                  {messageItems.length} turns
                </div>
              ) : null}
            </div>
          ) : null
        }
      />

      <div ref={viewportRef} className="min-h-[420px] flex-1 overflow-y-auto pr-2">
        {phase === "error" && messageItems.length === 0 ? (
          <div className="px-1 py-2 text-[13px] leading-6 text-rose-700">
            {error ?? lastToolkitMessage ?? "Voice session failed to start."}
          </div>
        ) : messageItems.length === 0 ? (
          <div className="flex h-full min-h-[280px] items-center justify-center text-center text-[13px] leading-6 text-neutral-400">
            Transcript will appear here.
          </div>
        ) : (
          <div className="space-y-3 pb-1">
            {messageItems.map((item, index) => {
              const localSpeaker = item.role === "user";
              return (
                <motion.div
                  key={`${item.message_id}-${index}`}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.28 }}
                  className={localSpeaker ? "ml-8" : "mr-8"}
                >
                  <div
                    className={`rounded-[22px] border px-4 py-3 ${
                      localSpeaker
                        ? "rounded-tr-md border-neutral-200 bg-white"
                        : "rounded-tl-md border-neutral-200 bg-[#f1ede5]"
                    }`}
                  >
                    <div className="mb-1 text-[11px] uppercase tracking-[0.18em] text-neutral-400">
                      {item.role === "user" ? "Me" : "NewBro"}
                    </div>
                    <div className="whitespace-pre-wrap text-[13px] leading-6 text-neutral-800">
                      {item.text}
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
