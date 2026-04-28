import { ArrowLeft, CircleDot } from "lucide-react";
import type { KeyboardEventHandler, PointerEventHandler, ReactNode } from "react";
import type { TaskSummary } from "../../types";
import { Button } from "../ui/button";
import { MarkdownText } from "../ui/markdown-text";
import { BroPortrait } from "./BroPortrait";
import { BroProgress } from "./BroProgress";
import type { BroCardModel, BroTaskRecord } from "./types";

export function WindowDots() {
  return (
    <div className="fixed right-5 top-5 z-50 hidden items-center gap-4 lg:flex">
      <span className="h-1 w-4 rounded-full bg-black" />
      <span className="h-4 w-4 rounded-[3px] bg-black" />
    </div>
  );
}

export function NewbroLogo() {
  return (
    <div className="flex items-start gap-3 lg:block">
      <div className="flex items-center gap-2">
        <div className="relative h-8 w-5 text-[#ff4b16] sm:h-10 sm:w-6" aria-hidden="true">
          <div className="absolute left-2 top-0 h-6 w-2.5 -skew-x-12 bg-[#ff4b16] sm:h-7 sm:w-3" />
          <div className="absolute left-0 top-3 h-7 w-2.5 -skew-x-12 bg-[#ff4b16] sm:top-4 sm:h-8 sm:w-3" />
        </div>
        <div className="newbro-condensed text-[28px] leading-none sm:text-[34px]">NEWBRO</div>
      </div>
      <p className="newbro-mono mt-3 hidden text-xs font-semibold uppercase leading-5 tracking-[0.14em] text-black/45 lg:block">
        Voice Command
        <br />
        Center
      </p>
    </div>
  );
}

export function VoicePad({
  active,
  disabled,
  onPointerDown,
  onPointerUp,
  onPointerCancel,
  onKeyDown,
  onKeyUp,
  onBlur,
  label = "Hold to Talk",
  statusLabel = "I'm listening",
}: {
  active: boolean;
  disabled?: boolean;
  onPointerDown: PointerEventHandler<HTMLButtonElement>;
  onPointerUp: PointerEventHandler<HTMLButtonElement>;
  onPointerCancel?: PointerEventHandler<HTMLButtonElement>;
  onKeyDown: KeyboardEventHandler<HTMLButtonElement>;
  onKeyUp: KeyboardEventHandler<HTMLButtonElement>;
  onBlur?: () => void;
  label?: string;
  statusLabel?: string;
}) {
  const ringCenter = { left: "30%", top: "47%" };
  const baseRings = [0, 1, 2, 3, 4].map((i) => ({
    width: 120 + i * 75,
    height: 64 + i * 48,
  }));
  const rippleBase = baseRings[2];

  return (
    <div className="voice-pad-stage relative mt-3 min-h-[130px] w-full max-w-[860px] overflow-hidden pt-1 sm:min-h-[150px] lg:min-h-[150px]">
      <button
        type="button"
        aria-label={active ? "Release to finish" : label}
        disabled={disabled}
        onPointerDown={onPointerDown}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerCancel ?? onPointerUp}
        onKeyDown={onKeyDown}
        onKeyUp={onKeyUp}
        onBlur={onBlur}
        className={`orange-pad paper-grain absolute bottom-[-10px] left-0 h-[145px] w-[min(100%,390px)] select-none touch-manipulation overflow-hidden bg-[#ff4b16] text-left text-black transition duration-300 focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-8px] focus-visible:outline-black disabled:cursor-not-allowed disabled:opacity-50 sm:left-[-24px] sm:h-[165px] sm:w-[500px] lg:left-[-36px] lg:h-[160px] lg:w-[520px] ${
          active ? "scale-[1.025] brightness-110" : "enabled:hover:scale-[1.01]"
        }`}
      >
        <div
          className="absolute inset-0 opacity-75 transition-opacity duration-300"
          style={{ animation: active ? "ringBreathe 1.9s ease-in-out infinite, ringGlow 1.9s ease-in-out infinite" : undefined }}
          aria-hidden="true"
        >
          {baseRings.map((ring, i) => (
            <span
              key={i}
              className="absolute rounded-full border-2 border-white/70"
              style={{
                left: ringCenter.left,
                top: ringCenter.top,
                width: ring.width,
                height: ring.height,
                transform: "translate(-50%, -50%) rotate(10deg)",
                animation: active ? `existingRingPulse 1.7s ease-in-out ${i * 0.055}s infinite` : undefined,
              }}
            />
          ))}
        </div>

        <div
          className={`pointer-events-none absolute inset-0 transition-opacity duration-200 ${active ? "opacity-100" : "opacity-0"}`}
          style={{
            WebkitMaskImage: "radial-gradient(ellipse 300px 210px at 30% 47%, black 0%, black 74%, transparent 88%)",
            maskImage: "radial-gradient(ellipse 300px 210px at 30% 47%, black 0%, black 74%, transparent 88%)",
          }}
          aria-hidden="true"
        >
          <span
            className="absolute rounded-full border-[4px] border-white/72"
            style={{
              left: ringCenter.left,
              top: ringCenter.top,
              width: rippleBase.width + 14,
              height: rippleBase.height + 10,
              animationName: "voiceRipple",
              animationDuration: "1.72s",
              animationTimingFunction: "ease-out",
              animationIterationCount: "infinite",
              filter: "drop-shadow(0 0 9px rgba(255,255,255,.32))",
            }}
          />
          <span
            className="absolute rounded-full border-[4px] border-white/42"
            style={{
              left: ringCenter.left,
              top: ringCenter.top,
              width: rippleBase.width + 14,
              height: rippleBase.height + 10,
              animationName: "voiceRipple",
              animationDuration: "1.72s",
              animationTimingFunction: "ease-out",
              animationIterationCount: "infinite",
              animationDelay: "0.48s",
              filter: "drop-shadow(0 0 9px rgba(255,255,255,.22))",
            }}
          />
        </div>

        <div
          className="newbro-condensed relative z-10 ml-[42px] mt-7 text-[34px] leading-[0.82] sm:ml-[72px] sm:mt-8 sm:text-[46px] lg:text-[48px]"
          style={{
            animation: active ? "textBreathe 1.85s ease-in-out infinite" : undefined,
            transformOrigin: "left center",
            filter: active ? "drop-shadow(0 0 11px rgba(255,255,255,.2))" : undefined,
          }}
        >
          HOLD
          <br />
          TO TALK
        </div>
      </button>

      <div className="absolute bottom-[18px] right-4 hidden rotate-[-8deg] sm:block lg:right-8" aria-hidden="true">
        <div
          style={{
            animationName: active ? "textBreatheSoft" : undefined,
            animationDuration: active ? "1.85s" : undefined,
            animationTimingFunction: active ? "ease-in-out" : undefined,
            animationIterationCount: active ? "infinite" : undefined,
            animationDelay: active ? "0.1s" : undefined,
            transformOrigin: "center center",
            filter: active ? "drop-shadow(0 0 9px rgba(255,255,255,.14))" : undefined,
          }}
        >
          <div className="newbro-mono text-base font-black leading-4 tracking-[0]">
            {statusLabel.toUpperCase().replace("'", "").split(" ").slice(0, 2).join("\n")}
          </div>
          <svg className="ml-3 mt-1.5 h-16 w-20" viewBox="0 0 110 80" fill="none">
            <path d="M98 4C88 43 50 49 14 54" stroke="black" strokeWidth="3" strokeLinecap="round" />
            <path d="M23 43L11 55L27 64" stroke="black" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
      </div>
    </div>
  );
}

export function LiveTranscriptPanel({
  active,
  transcriptText,
}: {
  active: boolean;
  transcriptText: string;
}) {
  return (
    <div className="flex h-full min-h-0 w-full flex-col">
      <div className="mb-2 flex flex-wrap items-center gap-2 sm:gap-3">
        <h2 className="text-lg font-black uppercase tracking-[0.08em] sm:text-xl">Live Transcript</h2>
        <span
          className="h-2.5 w-2.5 rounded-full bg-[#27d6d1]"
          style={{ animation: active ? "blink 1s infinite" : undefined }}
        />
        <span className="newbro-mono text-xs font-semibold uppercase tracking-[0.18em] text-[#129f9b]">
          {active ? "Listening..." : "Standby"}
        </span>
      </div>
      <div className="queue-card flex min-h-0 flex-1 rounded-[14px] border border-black/13 bg-white/46 px-4 py-3 sm:px-5">
        <p className="newbro-mono min-h-[44px] flex-1 overflow-auto text-[13px] leading-6 sm:text-sm subtle-scrollbar">
          {transcriptText ? (
            <span className="text-black/80">{transcriptText}</span>
          ) : (
            <span className="text-black/35">Latest transcript will appear here.</span>
          )}
        </p>
      </div>
    </div>
  );
}

export function DraftBrainPanel({
  draftText,
  summary,
  canSend,
  clearDisabled,
  sendDisabled,
  sending,
  clearing,
  error,
  onSend,
  onClear,
}: {
  draftText: string;
  summary?: string;
  canSend: boolean;
  clearDisabled: boolean;
  sendDisabled: boolean;
  sending: boolean;
  clearing: boolean;
  error?: string | null;
  onSend: () => void;
  onClear: () => void;
}) {
  return (
    <div className="queue-card flex h-full min-h-[170px] w-full flex-col rounded-[14px] border border-[#ff4b16] bg-white/32 px-4 py-4 backdrop-blur-sm sm:px-5">
      <div className="newbro-mono text-xs font-semibold uppercase tracking-[0.18em] text-[#ff4b16]">Current draft</div>
      {summary ? <p className="mt-2 text-[12px] leading-5 text-black/48">{summary}</p> : null}
      {draftText ? (
        <p className="mt-3 min-h-0 flex-1 overflow-auto whitespace-pre-wrap text-[14px] leading-7 text-black/78 subtle-scrollbar">
          {draftText}
        </p>
      ) : (
        <p className="newbro-mono mt-3 min-h-[58px] flex-1 text-sm leading-7 text-black/42">
          <span>No draft yet. Hold the mic to start shaping one.</span>
          <br />
          Tell your bro what to build.
        </p>
      )}
      {error ? (
        <div className="mt-4 rounded-[14px] border border-red-200 bg-red-50 px-4 py-3 text-[13px] leading-6 text-red-600" role="status">
          {error}
        </div>
      ) : null}
      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
        <button
          type="button"
          className="newbro-mono inline-flex min-h-[44px] w-full items-center justify-center gap-2 rounded-full border border-black/12 bg-white/45 px-3 py-2 text-[10px] font-black uppercase tracking-[0.12em] text-black/45 shadow-[0_8px_18px_rgba(0,0,0,.04)] transition duration-200 hover:-translate-y-0.5 hover:border-[#ff4b16]/35 hover:bg-white/70 hover:text-[#ff4b16] active:translate-y-0 disabled:pointer-events-none disabled:cursor-not-allowed disabled:translate-y-0 disabled:opacity-50 disabled:shadow-none sm:w-auto sm:text-[11px]"
          disabled={clearDisabled}
          onClick={onClear}
        >
          <span aria-hidden="true">↺</span>
          <span>{clearing ? "Clearing" : "Clear Draft"}</span>
        </button>
        <button
          type="button"
          className="group newbro-mono inline-flex min-h-[44px] w-full items-center justify-center gap-2 rounded-full border border-[#ff4b16]/80 bg-[#ff4b16] px-4 py-2.5 text-[11px] font-black uppercase tracking-[0.12em] text-white shadow-[0_10px_24px_rgba(255,75,22,.22)] transition duration-200 hover:-translate-y-0.5 hover:bg-[#ff5a2a] hover:shadow-[0_14px_30px_rgba(255,75,22,.28)] active:translate-y-0 active:shadow-[0_8px_18px_rgba(255,75,22,.2)] disabled:pointer-events-none disabled:cursor-not-allowed disabled:translate-y-0 disabled:opacity-50 disabled:shadow-none sm:w-auto sm:px-5 sm:text-xs"
          disabled={sendDisabled || !canSend}
          onClick={onSend}
        >
          <span>{sending ? "Sending" : "Send to Bro"}</span>
          <span className="transition-transform duration-200 group-hover:translate-x-1" aria-hidden="true">→</span>
        </button>
      </div>
    </div>
  );
}

function TaskHistoryCard({ record }: { record: BroTaskRecord }) {
  return (
    <article className="queue-card rounded-[14px] border border-black/11 bg-white/52 px-4 py-3 backdrop-blur-sm transition hover:-translate-y-0.5 hover:bg-white/62 lg:bg-white/43 lg:px-5 lg:py-4">
      <div className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:gap-4">
        <div className="min-w-0">
          <h4 className="text-[15px] font-black leading-snug tracking-tight text-black">{record.title}</h4>
          <MarkdownText className="mt-1.5 line-clamp-2 text-[12px] leading-5 text-black/58 lg:mt-2 lg:line-clamp-3">
            {record.summary}
          </MarkdownText>
        </div>
        <span className="shrink-0 rounded-lg bg-[#d5f5f2] px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.08em] text-[#087372] sm:mt-1 sm:py-1.5 sm:text-[11px]">
          {record.statusLabel}
        </span>
      </div>
    </article>
  );
}

export function RunnerBrainPanel({
  bro,
  summary,
  taskRecords = [],
  activeTaskId,
  stoppingTask,
  stopTaskError,
  onStopTask,
}: {
  bro: BroCardModel;
  summary: TaskSummary | null;
  taskRecords?: BroTaskRecord[];
  activeTaskId: string | null;
  stoppingTask: boolean;
  stopTaskError?: string | null;
  onStopTask: () => void;
}) {
  const canStopTask = Boolean(activeTaskId) && bro.status === "busy";

  return (
    <aside className="relative z-10 min-h-0 pb-4 lg:overflow-y-auto subtle-scrollbar">
      <h2 className="sr-only">Runner workspace</h2>
      <div className="runner-glow rounded-[14px] bg-gradient-to-br from-[#064a4d] to-[#02282b] p-4 text-white lg:p-6">
        <div className="grid grid-cols-[56px_minmax(0,1fr)] items-start gap-3 lg:flex lg:flex-row lg:flex-wrap lg:gap-5">
          <div className="origin-top-left scale-[0.82] lg:scale-100">
            <BroPortrait bro={bro} active={bro.status === "busy"} talking={false} />
          </div>
          <div className="min-w-0 flex-1 lg:min-w-[180px]">
            <div className="flex min-w-0 items-start justify-between gap-3 lg:block">
              <div className="min-w-0">
                <p className="newbro-mono text-[14px] font-black tracking-wide lg:text-base">
              Current task: <span className="text-[#25e0db]">{bro.status === "busy" ? "Running" : "Idle"}</span>
                </p>
                <p className="newbro-mono mt-1 text-[12px] leading-5 text-white/68 lg:mt-2 lg:text-sm">{bro.taskTitle || "Waiting for assignment"}</p>
              </div>
            </div>
            <BroProgress bro={bro} talking={false} compact />
          </div>
          <button
            type="button"
            aria-label="Stop Task"
            className="newbro-mono col-span-2 min-h-[40px] rounded-full border border-white/18 bg-white/8 px-4 py-2 text-[10px] font-black uppercase tracking-[0.12em] text-white/70 transition duration-200 hover:-translate-y-0.5 hover:border-[#ff4b16]/55 hover:bg-[#ff4b16]/18 hover:text-white active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:translate-y-0 disabled:hover:border-white/18 disabled:hover:bg-white/8 disabled:hover:text-white/70 lg:col-span-1 lg:min-h-[44px] lg:shrink-0 lg:py-2.5 lg:text-[11px]"
            disabled={!canStopTask || stoppingTask}
            onClick={onStopTask}
          >
            {stoppingTask ? "Stopping" : "Stop Task"}
          </button>
        </div>
      </div>
      {stopTaskError ? (
        <div className="mt-3 rounded-[14px] border border-red-200 bg-red-50 px-4 py-3 text-[13px] leading-6 text-red-600" role="status">
          {stopTaskError}
        </div>
      ) : null}

      {summary ? (
        <div className="queue-card mt-3 rounded-[14px] border border-black/11 bg-white/52 px-4 py-3 lg:mt-4 lg:bg-white/43 lg:px-5 lg:py-4">
          <div className="newbro-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-black/38">Latest summary</div>
          <MarkdownText className="mt-2 line-clamp-4 text-[13px] leading-6 text-black/75 lg:mt-3 lg:line-clamp-none">
            {summary.conversational_summary ?? summary.operational_summary ?? ""}
          </MarkdownText>
        </div>
      ) : null}

      <div className="mt-4 flex items-center justify-between gap-4 lg:mt-7 lg:justify-start">
        <div>
          <h3 className="text-xl font-black tracking-tight sm:text-2xl">Recent tasks</h3>
          <p className="newbro-mono mt-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-black/38 lg:mt-1 lg:text-xs">Recent to earliest</p>
        </div>
        <span className="grid h-8 w-8 place-items-center rounded-full bg-black text-sm font-black text-white">{taskRecords.length}</span>
      </div>

      <div className="mt-3 space-y-2.5 lg:mt-4 lg:space-y-3.5">
        {taskRecords.length > 0 ? (
          taskRecords.map((record) => <TaskHistoryCard key={record.taskId} record={record} />)
        ) : (
          <article className="queue-card rounded-[14px] border border-black/11 bg-white/52 px-4 py-4 text-[13px] text-black/52 lg:bg-white/43 lg:px-5 lg:py-5">
            No recent tasks yet.
          </article>
        )}
      </div>

    </aside>
  );
}

export function BroDetailHeader({
  bro,
  onBack,
}: {
  bro: BroCardModel;
  onBack: () => void;
}) {
  return (
    <div className="flex flex-col items-stretch justify-between gap-4 sm:flex-row sm:items-center">
      <div className="min-w-0">
        <div className="text-[11px] uppercase tracking-[0.22em] text-black/45">Bro detail</div>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <h1 className="newbro-condensed text-[34px] leading-none text-black">{bro.name}</h1>
          <span className="rounded-full border border-black/12 bg-white/44 px-2.5 py-1 text-[11px] text-black/58">{bro.role}</span>
          <span className="rounded-full border border-black/12 bg-white/44 px-2.5 py-1 text-[11px] text-black/58">{bro.liveState}</span>
        </div>
      </div>
      <Button type="button" variant="outline" className="hidden min-h-[44px] rounded-full border-black/15 bg-white/42 px-3 text-black sm:h-9 sm:min-h-9 lg:inline-flex" onClick={onBack}>
        <ArrowLeft className="mr-2 size-4" />
        Back home
      </Button>
    </div>
  );
}

export function StatusPill({ children }: { children: ReactNode }) {
  return (
    <span className="queue-card rounded-full border border-black/10 bg-white/50 px-3 py-1 text-[11px] text-black/52">
      {children}
    </span>
  );
}
