import { motion } from "framer-motion";
import { useEffect, useRef } from "react";
import type { ConnectorActivateResponse } from "../../lib/connector-client";
import type { VoiceTranscriptTurn } from "../../lib/voice-runtime";
import { SectionHeader } from "./SectionHeader";
import {
  formatTranscriptTime,
  isLocalSpeaker,
  resolveTranscriptSpeakerLabel,
} from "./transcript-utils";

export function ConversationMemory({
  phase,
  transcript,
  transcriptSession,
  error,
  lastTranscriptUpdateAt,
  lastToolkitMessage,
}: {
  phase: "idle" | "loading" | "connected" | "error";
  transcript: VoiceTranscriptTurn[];
  transcriptSession: ConnectorActivateResponse | null;
  error: string | null;
  lastTranscriptUpdateAt: string | null;
  lastToolkitMessage: string | null;
}) {
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const transcriptItems = transcript.filter((item) => Boolean(item.text?.trim()));
  const lastUpdateLabel = formatTranscriptTime(lastTranscriptUpdateAt);
  const showMetaChips = transcriptItems.length > 0 || Boolean(lastUpdateLabel);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) {
      return;
    }
    viewport.scrollTo({ top: viewport.scrollHeight, behavior: "smooth" });
  }, [phase, transcriptItems.length, lastTranscriptUpdateAt]);

  return (
    <div data-testid="conversation-memory" className="flex min-h-0 max-w-[400px] flex-1 flex-col space-y-3">
      <SectionHeader
        title="Interaction memory"
        trailing={
          showMetaChips ? (
            <div className="flex items-center gap-2">
              {transcriptItems.length > 0 ? (
                <div className="rounded-full border border-neutral-200 px-2.5 py-1 text-[11px] text-neutral-500">
                  {transcriptItems.length} turns
                </div>
              ) : null}
              {lastUpdateLabel ? (
                <div className="rounded-full border border-neutral-200 px-2.5 py-1 text-[11px] text-neutral-500">
                  {lastUpdateLabel}
                </div>
              ) : null}
            </div>
          ) : null
        }
      />

      <div ref={viewportRef} className="min-h-[420px] flex-1 overflow-y-auto pr-2">
        {phase === "loading" ? (
          <div className="px-1 py-2 text-[13px] leading-6 text-neutral-500">
            Preparing voice session and waiting for live transcript.
          </div>
        ) : phase === "error" && transcriptItems.length === 0 ? (
          <div className="px-1 py-2 text-[13px] leading-6 text-rose-700">
            {error ?? lastToolkitMessage ?? "Voice session failed to start."}
          </div>
        ) : transcriptItems.length === 0 ? (
          <div className="flex h-full min-h-[280px] items-center justify-center text-center text-[13px] leading-6 text-neutral-400">
            Transcript will appear here.
          </div>
        ) : (
          <div className="space-y-3 pb-1">
            {transcriptItems.map((item, index) => {
              const localSpeaker = isLocalSpeaker(item, transcriptSession);
              return (
                <motion.div
                  key={`${item.turn_id ?? "turn"}-${item.uid ?? "uid"}-${index}`}
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
                      {resolveTranscriptSpeakerLabel(item, transcriptSession)}
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
