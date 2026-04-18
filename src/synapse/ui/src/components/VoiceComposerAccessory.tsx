import { startTransition, useEffect, useMemo, useRef, useState } from "react";
import { CircleAlert, LoaderCircle, Mic, Radio, RotateCcw, Square, Volume2 } from "lucide-react";
import { Button } from "./ui/button";
import { cn } from "../lib/utils";
import {
  activateGatewaySession,
  getGatewayConfig,
  prepareGatewaySession,
  stopGatewaySession,
  type GatewayActivateResponse,
  type GatewayConfig,
  type GatewayPrepareResponse,
} from "../lib/gateway-client";

type VoicePhase = "loading" | "ready" | "starting" | "connected" | "stopping" | "error";

type TranscriptTurn = {
  turn_id?: string | number;
  uid?: string | number;
  text?: string;
  status?: string;
};

type ActiveVoiceResources = {
  bindingId: string;
  rtcClient: any;
  micTrack: any;
  rtmClient: any;
  voiceAi: any;
};

function describePhase(phase: VoicePhase, hasConfig: boolean) {
  if (phase === "loading") {
    return "Checking voice gateway";
  }
  if (phase === "ready") {
    return "Voice ready";
  }
  if (phase === "starting") {
    return "Joining voice channel";
  }
  if (phase === "connected") {
    return "Voice live";
  }
  if (phase === "stopping") {
    return "Stopping voice";
  }
  return hasConfig ? "Voice needs attention" : "Voice unavailable";
}

async function loadAgoraBrowserStack() {
  const agoraRtcModule = await import("agora-rtc-sdk-ng");
  const agoraRtmModule = await import("agora-rtm");
  const toolkitModule = await import("agora-agent-client-toolkit");
  return {
    AgoraRTC: agoraRtcModule.default,
    AgoraRTM: agoraRtmModule.default,
    AgoraVoiceAI: toolkitModule.AgoraVoiceAI,
    AgoraVoiceAIEvents: toolkitModule.AgoraVoiceAIEvents,
    TranscriptHelperMode: toolkitModule.TranscriptHelperMode,
  };
}

export function VoiceComposerAccessory() {
  const [config, setConfig] = useState<GatewayConfig | null>(null);
  const [phase, setPhase] = useState<VoicePhase>("loading");
  const [error, setError] = useState<string | null>(null);
  const [agentState, setAgentState] = useState("idle");
  const [transcript, setTranscript] = useState<TranscriptTurn[]>([]);
  const [activeSession, setActiveSession] = useState<GatewayActivateResponse | null>(null);
  const resourcesRef = useRef<ActiveVoiceResources | null>(null);

  async function refreshConfig() {
    setError(null);
    setPhase("loading");
    try {
      const loaded = await getGatewayConfig();
      setConfig(loaded);
      if (!loaded.ready) {
        setPhase("error");
        setError(
          loaded.missing_requirements.length > 0
            ? `Voice gateway is missing: ${loaded.missing_requirements.join(", ")}`
            : "Voice gateway is not ready.",
        );
        return;
      }
      setPhase("ready");
    } catch (loadError) {
      const message =
        loadError instanceof Error ? loadError.message : "Failed to load voice gateway config.";
      setConfig(null);
      setPhase("error");
      setError(message);
    }
  }

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const loaded = await getGatewayConfig();
        if (cancelled) {
          return;
        }
        setConfig(loaded);
        if (!loaded.ready) {
          setPhase("error");
          setError(
            loaded.missing_requirements.length > 0
              ? `Voice gateway is missing: ${loaded.missing_requirements.join(", ")}`
              : "Voice gateway is not ready.",
          );
          return;
        }
        setPhase("ready");
      } catch (loadError) {
        if (cancelled) {
          return;
        }
        const message =
          loadError instanceof Error ? loadError.message : "Failed to load voice gateway config.";
        setConfig(null);
        setPhase("error");
        setError(message);
      }
    })();
    return () => {
      cancelled = true;
      void teardownVoiceSession(resourcesRef.current, false);
      resourcesRef.current = null;
    };
  }, []);

  async function connectVoiceSession(prepared: GatewayPrepareResponse) {
    const { AgoraRTC, AgoraRTM, AgoraVoiceAI, AgoraVoiceAIEvents, TranscriptHelperMode } =
      await loadAgoraBrowserStack();

    let rtcClient: any | null = null;
    let micTrack: any | null = null;
    let rtmClient: any | null = null;
    let voiceAi: any | null = null;

    try {
      rtcClient = AgoraRTC.createClient({ mode: "rtc", codec: "vp8" });
      rtcClient.on("user-published", async (user: any, mediaType: string) => {
        await rtcClient.subscribe(user, mediaType);
        if (mediaType === "audio") {
          user.audioTrack?.play();
        }
      });
      rtcClient.on("user-unpublished", (user: any, mediaType: string) => {
        if (mediaType === "audio") {
          user.audioTrack?.stop();
        }
      });

      rtmClient = new AgoraRTM.RTM(prepared.app_id, prepared.user_rtm_uid);
      await rtmClient.login({ token: prepared.token });
      await rtmClient.subscribe(prepared.channel_name, { withMessage: true });

      voiceAi = await AgoraVoiceAI.init({
        rtcEngine: rtcClient,
        rtmConfig: { rtmEngine: rtmClient },
        renderMode: TranscriptHelperMode.TEXT,
      });
      voiceAi.on(AgoraVoiceAIEvents.TRANSCRIPT_UPDATED, (nextTranscript: TranscriptTurn[]) => {
        startTransition(() => {
          setTranscript(nextTranscript);
        });
      });
      voiceAi.on(AgoraVoiceAIEvents.AGENT_STATE_CHANGED, (_agentUserId: string, next: any) => {
        setAgentState(next?.state ?? "idle");
      });
      voiceAi.on(AgoraVoiceAIEvents.AGENT_ERROR, (_agentUserId: string, next: any) => {
        setError(next?.message ?? "Voice agent pipeline error.");
      });
      voiceAi.on(AgoraVoiceAIEvents.MESSAGE_ERROR, (_agentUserId: string, next: any) => {
        setError(next?.message ?? "Voice agent message delivery failed.");
      });

      await rtcClient.join(prepared.app_id, prepared.channel_name, prepared.token, prepared.uid);
      micTrack = await AgoraRTC.createMicrophoneAudioTrack();
      await rtcClient.publish([micTrack]);
      voiceAi.subscribeMessage(prepared.channel_name);

      const activated = await activateGatewaySession({
        prepared_session_id: prepared.prepared_session_id,
      });

      resourcesRef.current = {
        bindingId: activated.binding_id,
        rtcClient,
        micTrack,
        rtmClient,
        voiceAi,
      };
      return activated;
    } catch (connectError) {
      await teardownVoiceSession(
        {
          bindingId: "",
          rtcClient,
          micTrack,
          rtmClient,
          voiceAi,
        },
        false,
      );
      throw connectError;
    }
  }

  async function handleStart() {
    if (!config?.ready || phase === "starting" || phase === "connected" || phase === "stopping") {
      return;
    }
    setError(null);
    setPhase("starting");
    setTranscript([]);
    setAgentState("idle");
    try {
      const prepared = await prepareGatewaySession();
      const activated = await connectVoiceSession(prepared);
      setActiveSession(activated);
      setPhase("connected");
    } catch (startError) {
      resourcesRef.current = null;
      setActiveSession(null);
      setAgentState("idle");
      setTranscript([]);
      setPhase(config.ready ? "ready" : "error");
      setError(startError instanceof Error ? startError.message : "Failed to start voice mode.");
    }
  }

  async function handleStop() {
    setPhase("stopping");
    setError(null);
    try {
      await teardownVoiceSession(resourcesRef.current, true);
      resourcesRef.current = null;
      setActiveSession(null);
      setTranscript([]);
      setAgentState("idle");
      setPhase(config?.ready ? "ready" : "error");
    } catch (stopError) {
      setPhase("error");
      setError(stopError instanceof Error ? stopError.message : "Failed to stop voice mode.");
    }
  }

  const transcriptItems = useMemo(
    () => transcript.filter((item) => Boolean(item.text?.trim())),
    [transcript],
  );

  return (
    <div
      data-testid="voice-accessory-shell"
      className="mb-3 rounded-[1.3rem] border border-[rgba(214,255,100,0.12)] bg-[linear-gradient(180deg,rgba(20,22,26,0.9),rgba(28,31,36,0.86))] px-3 py-3 text-white shadow-[0_22px_48px_-30px_rgba(0,0,0,0.55)] backdrop-blur-xl sm:px-4"
    >
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2.5">
          <span
            className={cn(
              "inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-[0.68rem] font-bold uppercase tracking-[0.18em]",
              phase === "connected"
                ? "bg-[#d6ff64]/14 text-[#d6ff64]"
                : phase === "error"
                  ? "bg-rose-400/10 text-rose-200"
                  : "bg-white/8 text-white/75",
            )}
          >
            {phase === "loading" || phase === "starting" || phase === "stopping" ? (
              <LoaderCircle className="size-3.5 animate-spin" />
            ) : phase === "error" ? (
              <CircleAlert className="size-3.5" />
            ) : phase === "connected" ? (
              <Radio className="size-3.5" />
            ) : (
              <Mic className="size-3.5" />
            )}
            <span>{describePhase(phase, Boolean(config))}</span>
          </span>

          {activeSession ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/6 px-3 py-1.5 text-[0.68rem] font-semibold tracking-[0.08em] text-white/68">
              <Volume2 className="size-3.5 text-[#d6ff64]" />
              <span>{activeSession.channel_name}</span>
            </span>
          ) : null}

          <div className="ml-auto flex items-center gap-2">
            {phase === "error" ? (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => void refreshConfig()}
                className="rounded-full bg-white/8 px-3 text-white hover:bg-white/12"
              >
                <RotateCcw className="size-4" />
                <span className="ml-1">Retry</span>
              </Button>
            ) : null}
            {phase === "connected" ? (
              <Button
                data-testid="voice-accessory-stop"
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => void handleStop()}
                className="rounded-full bg-white px-3 text-[#111612] hover:bg-white/90"
              >
                <Square className="size-4 fill-current" />
                <span className="ml-1">Stop Voice</span>
              </Button>
            ) : (
              <Button
                data-testid="voice-accessory-start"
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => void handleStart()}
                disabled={!config?.ready || phase === "loading" || phase === "starting" || phase === "stopping"}
                className="rounded-full bg-[#d6ff64] px-3 text-[#14180c] shadow-[0_12px_24px_-14px_rgba(214,255,100,0.88)] hover:bg-[#e0ff84] disabled:bg-[#d6ff64]/50 disabled:text-[#14180c]/60"
              >
                <Mic className="size-4" />
                <span className="ml-1">Start Voice</span>
              </Button>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[0.76rem] text-white/52">
          <span>Agent state: <strong className="font-semibold text-white/78">{agentState}</strong></span>
          {activeSession ? (
            <span>
              Voice session:{" "}
              <strong className="font-semibold text-white/78">{activeSession.synapse_session_id}</strong>
            </span>
          ) : (
            <span>
              Voice stays parallel to the main workbench session.
            </span>
          )}
        </div>

        {error ? (
          <div
            data-testid="voice-accessory-error"
            className="rounded-[1rem] border border-rose-400/14 bg-rose-400/8 px-3 py-2.5 text-sm leading-5 text-rose-100"
          >
            {error}
          </div>
        ) : null}

        {phase === "connected" ? (
          <div
            data-testid="voice-accessory-transcript"
            className="rounded-[1rem] border border-white/8 bg-white/5 px-3 py-3"
          >
            <div className="mb-2 flex items-center justify-between gap-3">
              <div className="text-[0.68rem] font-bold uppercase tracking-[0.18em] text-white/44">
                Voice Transcript
              </div>
              <div className="text-[0.72rem] text-white/48">{transcriptItems.length} turns</div>
            </div>

            {transcriptItems.length === 0 ? (
              <p className="text-sm leading-5 text-white/54">
                Join the voice channel and start speaking. Transcript updates will appear here.
              </p>
            ) : (
              <div className="space-y-2">
                {transcriptItems.slice(-3).map((item, index) => (
                  <div
                    key={`${item.turn_id ?? "turn"}-${item.uid ?? "uid"}-${index}`}
                    className="rounded-[0.9rem] bg-black/16 px-3 py-2.5"
                  >
                    <div className="mb-1 flex items-center justify-between gap-3 text-[0.66rem] uppercase tracking-[0.14em] text-white/38">
                      <span>UID {item.uid ?? "unknown"}</span>
                      <span>{item.status ?? "unknown"}</span>
                    </div>
                    <p className="text-sm leading-5 text-white/78">{item.text}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}

async function teardownVoiceSession(resources: ActiveVoiceResources | null, notifyBackend: boolean) {
  if (!resources) {
    return;
  }

  try {
    resources.voiceAi?.unsubscribe();
  } catch {}

  try {
    resources.voiceAi?.destroy();
  } catch {}

  try {
    resources.micTrack?.stop();
    resources.micTrack?.close();
  } catch {}

  try {
    await resources.rtmClient?.logout();
  } catch {}

  try {
    await resources.rtcClient?.leave();
  } catch {}

  if (notifyBackend && resources.bindingId) {
    await stopGatewaySession(resources.bindingId);
  }
}
