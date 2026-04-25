import { ArrowLeft, CircleDot, Mic, SendHorizontal, Square } from "lucide-react";
import { useEffect } from "react";
import { Button } from "../ui/button";
import { BroPortrait } from "./BroPortrait";
import { BroProgress } from "./BroProgress";
import type { BroCardModel } from "./types";
import type { TaskSummary } from "../../types";
import type { useSttSession } from "./useSttSession";

function liveStateText(bro: BroCardModel) {
  if (bro.liveState === "live") return "Live and ready";
  if (bro.liveState === "offline") return "Bound node offline";
  return "Needs node binding";
}

export function BroDetailPage({
  bro,
  sessionId,
  summary,
  sttSession,
  onBack,
}: {
  bro: BroCardModel;
  sessionId: string | null;
  summary: TaskSummary | null;
  sttSession: ReturnType<typeof useSttSession>;
  onBack: () => void;
}) {
  const { state: sttState, setActiveBro, setMicMuted } = sttSession;

  useEffect(() => {
    setActiveBro(bro.id);
    return () => {
      setActiveBro(null);
      void setMicMuted(true);
    };
  }, [bro.id, setActiveBro, setMicMuted]);

  const listening = sttState.phase === "listening" && !sttState.isMicMuted && sttState.activeBroId === bro.id;

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 px-4 pb-4 pt-4 md:px-6 md:pb-6 md:pt-5 xl:px-8 xl:pb-8 xl:pt-6">
      <div className="glass-panel rounded-[32px] border border-white/75 px-5 py-5 md:px-6">
        <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
          <div className="flex items-start gap-4">
            <BroPortrait bro={bro} active={bro.status === "busy"} talking={listening} />
            <div>
              <div className="text-[11px] uppercase tracking-[0.24em] text-muted-foreground">Bro detail</div>
              <h1 className="serif-flow mt-2 text-[44px] leading-none tracking-[-0.06em] text-foreground">{bro.name}</h1>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-[12px] text-muted-foreground">
                <span className="rounded-full border border-border/70 bg-white/60 px-3 py-1">{bro.role}</span>
                <span className="rounded-full border border-border/70 bg-white/60 px-3 py-1">{liveStateText(bro)}</span>
                <span className="rounded-full border border-border/70 bg-white/60 px-3 py-1">{bro.nodeName ?? "No node bound"}</span>
              </div>
            </div>
          </div>
          <Button type="button" variant="outline" className="rounded-full" onClick={onBack}>
            <ArrowLeft className="mr-2 size-4" />
            Back home
          </Button>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 xl:grid-cols-[1.25fr_0.75fr]">
        <section className="glass-panel min-h-[520px] rounded-[32px] border border-white/75 p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-[11px] uppercase tracking-[0.24em] text-primary">Draft Brain</div>
              <h2 className="serif-flow mt-2 text-[32px] tracking-[-0.05em]">Draft for {bro.name}</h2>
            </div>
            <span className="rounded-full border border-primary/15 bg-primary/10 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-primary">
              {sttState.phase}{sttState.isMicMuted ? " · muted" : " · live"}
            </span>
          </div>
          <div className="mt-8 rounded-[28px] border border-dashed border-border/70 bg-white/50 px-5 py-8 text-center">
            <Mic className="mx-auto size-8 text-primary" />
            <div className="serif-flow mt-4 text-[26px] tracking-[-0.04em]">Speak to draft</div>
            <p className="mx-auto mt-3 max-w-[560px] text-[14px] leading-7 text-muted-foreground">Realtime STT is already started from Home with the local mic muted. Unmute here to send live transcript turns to this Bro.</p>
            <div className="mt-5 flex justify-center gap-3">
              {listening ? (
                <Button type="button" variant="outline" className="rounded-full" onClick={() => void setMicMuted(true)}>
                  <Square className="mr-2 size-4" />
                  Mute mic
                </Button>
              ) : (
                <Button type="button" className="rounded-full" disabled={!sessionId || sttState.phase === "starting"} onClick={() => void setMicMuted(false)}>
                  <Mic className="mr-2 size-4" />
                  {sttState.phase === "starting" ? "Starting..." : "Unmute mic"}
                </Button>
              )}
            </div>
            {sttState.error ? <div className="mt-4 text-[13px] text-[#8d5a62]">{sttState.error}</div> : null}
            {sttState.sttSession ? (
              <div className="mt-4 text-[11px] leading-5 text-muted-foreground">
                STT agent {sttState.sttSession.agent_id} · pub {sttState.sttSession.pub_bot_uid} · sub {sttState.sttSession.sub_bot_uid}
              </div>
            ) : null}
            <div className="mt-5 text-[12px] text-muted-foreground">Session {sessionId ?? "not connected"}</div>
          </div>
          <div className="mt-5 rounded-[24px] border border-white/75 bg-white/58 p-4">
            <div className="text-[12px] uppercase tracking-[0.18em] text-muted-foreground">Live transcript</div>
            <p className="mt-3 min-h-8 text-[15px] leading-7 text-foreground/80">{sttState.interimText || "Interim transcript appears here after you unmute."}</p>
            <div className="mt-4 grid gap-2">
              {sttState.finalTurns.map((turn) => <div key={turn} className="rounded-2xl bg-white/70 px-3 py-2 text-[13px] text-foreground/80">{turn}</div>)}
            </div>
          </div>
          <div className="mt-5 flex flex-wrap gap-3">
            <Button type="button" className="rounded-full" disabled>
              <SendHorizontal className="mr-2 size-4" />
              Send to Bro
            </Button>
            <Button type="button" variant="outline" className="rounded-full" disabled>Clear Draft</Button>
          </div>
        </section>

        <aside className="glass-panel min-h-[520px] rounded-[32px] border border-white/75 p-5">
          <div className="text-[11px] uppercase tracking-[0.24em] text-primary">Runner Brain</div>
          <h2 className="serif-flow mt-2 text-[30px] tracking-[-0.05em]">Current task</h2>
          <div className="mt-5 rounded-[24px] border border-white/75 bg-white/58 p-4">
            <div className="flex items-center gap-2 text-[12px] uppercase tracking-[0.18em] text-muted-foreground"><CircleDot className="size-4 text-primary" />{bro.status}</div>
            <div className="mt-3 text-[18px] font-medium text-foreground">{bro.taskTitle}</div>
            <BroProgress bro={bro} talking={false} />
          </div>
          <div className="mt-4 rounded-[24px] border border-white/75 bg-white/58 p-4">
            <div className="text-[12px] uppercase tracking-[0.18em] text-muted-foreground">Latest summary</div>
            <p className="mt-3 text-[14px] leading-7 text-foreground/80">{summary?.conversational_summary ?? summary?.operational_summary ?? bro.idleNote}</p>
          </div>
          <Button type="button" variant="outline" className="mt-5 w-full rounded-full" disabled={bro.status !== "busy"}><Square className="mr-2 size-4" />Stop Task</Button>
        </aside>
      </div>
    </div>
  );
}
