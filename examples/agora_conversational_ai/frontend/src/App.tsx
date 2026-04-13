import { startTransition, useEffect, useRef, useState, type FormEvent } from "react";
import AgoraRTC from "agora-rtc-sdk-ng";
import AgoraRTM from "agora-rtm";
import {
  AgoraVoiceAI,
  AgoraVoiceAIEvents,
  ChatMessagePriority,
  ChatMessageType,
  TranscriptHelperMode,
} from "agora-agent-client-toolkit";
import {
  activateFrontendSession,
  getFrontendConfig,
  prepareFrontendSession,
  stopFrontendSession,
  type FrontendActivateResponse,
  type FrontendConfig,
  type FrontendPrepareResponse,
} from "./api";

type Phase = "loading" | "ready" | "starting" | "connected" | "stopping" | "error";

type TranscriptTurn = {
  turn_id?: string | number;
  uid?: string | number;
  text?: string;
  status?: string;
};

type ActiveResources = {
  bindingId: string;
  rtcClient: any;
  micTrack: any;
  rtmClient: any;
  voiceAi: any;
  agentRtmUid: string;
};

type DiagnosticSeverity = "info" | "warning" | "error";
type DiagnosticSource = "backend" | "toolkit" | "rtc" | "rtm";

type DiagnosticEntry = {
  id: string;
  ts: string;
  source: DiagnosticSource;
  eventType: string;
  severity: DiagnosticSeverity;
  summary: string;
  details?: unknown;
};

const MAX_DIAGNOSTICS = 100;

function makeDiagnosticId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `diag-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function statusLabel(phase: Phase) {
  if (phase === "loading") {
    return "Loading local adapter";
  }
  if (phase === "ready") {
    return "Ready to join";
  }
  if (phase === "starting") {
    return "Preparing and activating session";
  }
  if (phase === "connected") {
    return "Live in channel";
  }
  if (phase === "stopping") {
    return "Stopping session";
  }
  return "Needs attention";
}

function formatDiagnosticTime(value: string) {
  const date = new Date(value);
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(
    2,
    "0",
  )}:${String(date.getSeconds()).padStart(2, "0")}`;
}

function formatDiagnosticDetails(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function DiagnosticMetaCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="meta-card">
      <p>{label}</p>
      <strong>{value}</strong>
    </div>
  );
}

export default function App() {
  const [config, setConfig] = useState<FrontendConfig | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState<string | null>(null);
  const [profile, setProfile] = useState("");
  const [channelName, setChannelName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [userId, setUserId] = useState("");
  const [activeSession, setActiveSession] = useState<FrontendActivateResponse | null>(null);
  const [agentState, setAgentState] = useState<string>("idle");
  const [transcript, setTranscript] = useState<TranscriptTurn[]>([]);
  const [draftText, setDraftText] = useState("");
  const [diagnostics, setDiagnostics] = useState<DiagnosticEntry[]>([]);
  const resourcesRef = useRef<ActiveResources | null>(null);

  function appendDiagnostic(entry: Omit<DiagnosticEntry, "id" | "ts">) {
    const next: DiagnosticEntry = {
      id: makeDiagnosticId(),
      ts: new Date().toISOString(),
      ...entry,
    };
    setDiagnostics((current) => [next, ...current].slice(0, MAX_DIAGNOSTICS));
  }

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const loaded = await getFrontendConfig();
        if (cancelled) {
          return;
        }
        setConfig(loaded);
        appendDiagnostic({
          source: "backend",
          eventType: "config_loaded",
          severity: loaded.ready ? "info" : "warning",
          summary: loaded.ready
            ? "Backend config loaded."
            : "Backend config is incomplete.",
          details: loaded,
        });
        setProfile(loaded.defaults.profile ?? "VOICE");
        setChannelName(loaded.defaults.channel_name ?? "synapse-voice-demo");
        setDisplayName(loaded.defaults.display_name ?? "Synapse Tester");
        setPhase(loaded.ready ? "ready" : "error");
        if (!loaded.ready) {
          setError(`Missing backend config: ${loaded.missing_requirements.join(", ")}`);
        }
      } catch (loadError) {
        if (cancelled) {
          return;
        }
        const message =
          loadError instanceof Error ? loadError.message : "Failed to load frontend config.";
        setPhase("error");
        setError(message);
        appendDiagnostic({
          source: "backend",
          eventType: "config_failed",
          severity: "error",
          summary: message,
        });
      }
    })();
    return () => {
      cancelled = true;
      void teardown(resourcesRef.current, false);
      resourcesRef.current = null;
    };
  }, []);

  async function handleStart(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setPhase("starting");
    setDiagnostics([]);
    appendDiagnostic({
      source: "backend",
      eventType: "session_prepare_requested",
      severity: "info",
      summary: "Preparing browser bootstrap for RTC and RTM.",
      details: {
        profile,
        channelName,
        displayName,
        userId: userId || null,
      },
    });

    let activated: FrontendActivateResponse | null = null;
    try {
      const prepared = await prepareFrontendSession({
        profile,
        channel_name: channelName,
        display_name: displayName,
        user_id: userId || undefined,
      });
      appendDiagnostic({
        source: "backend",
        eventType: "session_prepare_succeeded",
        severity: "info",
        summary: "Backend prepared RTC/RTM bootstrap values.",
        details: prepared,
      });
      activated = await connectVoiceSession(prepared);
      appendDiagnostic({
        source: "backend",
        eventType: "session_activate_succeeded",
        severity: "info",
        summary: "Backend activated the local Agora agent session.",
        details: activated,
      });
      setActiveSession(activated);
      setPhase("connected");
    } catch (startError) {
      await teardown(resourcesRef.current, true);
      if (!resourcesRef.current && activated) {
        try {
          await stopFrontendSession(activated.binding_id);
        } catch {}
      }
      resourcesRef.current = null;
      setActiveSession(null);
      setAgentState("idle");
      setTranscript([]);
      setPhase(config?.ready ? "ready" : "error");
      const message =
        startError instanceof Error ? startError.message : "Failed to start session.";
      setError(message);
      appendDiagnostic({
        source: "backend",
        eventType: "session_start_failed",
        severity: "error",
        summary: message,
      });
    }
  }

  async function connectVoiceSession(prepared: FrontendPrepareResponse) {
    let rtcClient: any | null = null;
    let micTrack: any | null = null;
    let rtmClient: any | null = null;
    let voiceAi: any | null = null;
    try {
      rtcClient = AgoraRTC.createClient({ mode: "rtc", codec: "vp8" });
      rtcClient.on("user-published", async (user: any, mediaType: string) => {
        await rtcClient.subscribe(user, mediaType);
        appendDiagnostic({
          source: "rtc",
          eventType: "remote_user_published",
          severity: "info",
          summary: `Subscribed to remote ${mediaType}.`,
          details: {
            uid: user?.uid ?? null,
            mediaType,
          },
        });
        if (mediaType === "audio") {
          user.audioTrack?.play();
          appendDiagnostic({
            source: "rtc",
            eventType: "remote_audio_playing",
            severity: "info",
            summary: "Remote agent audio is playing.",
            details: { uid: user?.uid ?? null },
          });
        }
      });
      rtcClient.on("user-unpublished", (user: any, mediaType: string) => {
        if (mediaType === "audio") {
          user.audioTrack?.stop();
        }
        appendDiagnostic({
          source: "rtc",
          eventType: "remote_user_unpublished",
          severity: "warning",
          summary: `Remote ${mediaType} unpublished.`,
          details: { uid: user?.uid ?? null, mediaType },
        });
      });

      rtmClient = new AgoraRTM.RTM(prepared.app_id, prepared.user_rtm_uid);
      await rtmClient.login({ token: prepared.token });
      appendDiagnostic({
        source: "rtm",
        eventType: "rtm_logged_in",
        severity: "info",
        summary: "Logged into RTM.",
        details: { rtmUserId: prepared.user_rtm_uid },
      });
      await rtmClient.subscribe(prepared.channel_name, { withMessage: true });
      appendDiagnostic({
        source: "rtm",
        eventType: "rtm_subscribed",
        severity: "info",
        summary: "Subscribed to RTM channel before activation.",
        details: {
          channel: prepared.channel_name,
          subscribedBeforeActivate: true,
        },
      });

      voiceAi = await AgoraVoiceAI.init({
        rtcEngine: rtcClient,
        rtmConfig: { rtmEngine: rtmClient },
        renderMode: TranscriptHelperMode.TEXT,
      });
      appendDiagnostic({
        source: "toolkit",
        eventType: "toolkit_initialized",
        severity: "info",
        summary: "AgoraVoiceAI initialized.",
      });

      voiceAi.on(AgoraVoiceAIEvents.TRANSCRIPT_UPDATED, (nextTranscript: TranscriptTurn[]) => {
        startTransition(() => {
          setTranscript(nextTranscript);
        });
      });
      voiceAi.on(AgoraVoiceAIEvents.AGENT_STATE_CHANGED, (_agentUserId: string, next: any) => {
        setAgentState(next?.state ?? "idle");
        appendDiagnostic({
          source: "toolkit",
          eventType: "agent_state_changed",
          severity: "info",
          summary: `Agent state changed to ${next?.state ?? "idle"}.`,
          details: next,
        });
      });
      voiceAi.on(AgoraVoiceAIEvents.AGENT_ERROR, (_agentUserId: string, next: any) => {
        const message = next?.message ?? "Agent pipeline error.";
        setError(message);
        appendDiagnostic({
          source: "toolkit",
          eventType: "agent_error",
          severity: "error",
          summary: message,
          details: next,
        });
      });
      voiceAi.on(AgoraVoiceAIEvents.MESSAGE_ERROR, (_agentUserId: string, next: any) => {
        const message = next?.message ?? "Agent message delivery failed.";
        setError(message);
        appendDiagnostic({
          source: "toolkit",
          eventType: "message_error",
          severity: "error",
          summary: message,
          details: next,
        });
      });
      voiceAi.on(AgoraVoiceAIEvents.AGENT_INTERRUPTED, (_agentUserId: string, next: any) => {
        appendDiagnostic({
          source: "toolkit",
          eventType: "agent_interrupted",
          severity: "warning",
          summary: "Agent speech was interrupted.",
          details: next,
        });
      });
      voiceAi.on(AgoraVoiceAIEvents.AGENT_METRICS, (_agentUserId: string, next: any) => {
        appendDiagnostic({
          source: "toolkit",
          eventType: "agent_metrics",
          severity: "info",
          summary: `Metric ${next?.name ?? "unknown"} = ${String(next?.value ?? "n/a")}`,
          details: next,
        });
      });
      voiceAi.on(AgoraVoiceAIEvents.DEBUG_LOG, (message: string) => {
        appendDiagnostic({
          source: "toolkit",
          eventType: "debug_log",
          severity: "info",
          summary: message,
        });
      });
      voiceAi.on(
        AgoraVoiceAIEvents.MESSAGE_RECEIPT_UPDATED,
        (_agentUserId: string, next: any) => {
          appendDiagnostic({
            source: "toolkit",
            eventType: "message_receipt_updated",
            severity: "info",
            summary: "Message receipt updated.",
            details: next,
          });
        },
      );
      voiceAi.on(AgoraVoiceAIEvents.MESSAGE_SAL_STATUS, (_agentUserId: string, next: any) => {
        appendDiagnostic({
          source: "toolkit",
          eventType: "sal_status",
          severity: "warning",
          summary: "Speech activity level status updated.",
          details: next,
        });
      });

      await rtcClient.join(prepared.app_id, prepared.channel_name, prepared.token, prepared.uid);
      appendDiagnostic({
        source: "rtc",
        eventType: "rtc_joined",
        severity: "info",
        summary: "Joined the RTC channel.",
        details: {
          appId: prepared.app_id,
          channel: prepared.channel_name,
          rtcUid: prepared.uid,
        },
      });

      micTrack = await AgoraRTC.createMicrophoneAudioTrack();
      await rtcClient.publish([micTrack]);
      appendDiagnostic({
        source: "rtc",
        eventType: "microphone_published",
        severity: "info",
        summary: "Published microphone track.",
      });

      voiceAi.subscribeMessage(prepared.channel_name);
      appendDiagnostic({
        source: "toolkit",
        eventType: "subscribed_messages",
        severity: "info",
        summary: "Subscribed to AgoraVoiceAI messages.",
        details: {
          channel: prepared.channel_name,
          agentRtmUid: prepared.agent_rtm_uid,
        },
      });

      appendDiagnostic({
        source: "backend",
        eventType: "session_activate_requested",
        severity: "info",
        summary: "Requesting backend agent activation after RTC and RTM are ready.",
        details: { preparedSessionId: prepared.prepared_session_id },
      });
      const activated = await activateFrontendSession({
        prepared_session_id: prepared.prepared_session_id,
      });

      resourcesRef.current = {
        bindingId: activated.binding_id,
        rtcClient,
        micTrack,
        rtmClient,
        voiceAi,
        agentRtmUid: activated.agent_rtm_uid,
      };
      return activated;
    } catch (error) {
      await teardown(
        {
          bindingId: "",
          rtcClient,
          micTrack,
          rtmClient,
          voiceAi,
          agentRtmUid: "",
        },
        false,
      );
      appendDiagnostic({
        source: "backend",
        eventType: "session_connect_failed",
        severity: "error",
        summary:
          error instanceof Error ? error.message : "Failed during RTC/RTM or toolkit initialization.",
      });
      throw error;
    }
  }

  async function handleStop() {
    const resources = resourcesRef.current;
    setPhase("stopping");
    setError(null);
    appendDiagnostic({
      source: "backend",
      eventType: "session_stop_requested",
      severity: "info",
      summary: "Stopping local Agora session.",
    });
    try {
      await teardown(resources, true);
      resourcesRef.current = null;
      setActiveSession(null);
      setTranscript([]);
      setAgentState("idle");
      setDraftText("");
      setPhase(config?.ready ? "ready" : "error");
      appendDiagnostic({
        source: "backend",
        eventType: "session_stop_completed",
        severity: "info",
        summary: "Session stopped cleanly.",
      });
    } catch (stopError) {
      const message = stopError instanceof Error ? stopError.message : "Failed to stop session.";
      setPhase("error");
      setError(message);
      appendDiagnostic({
        source: "backend",
        eventType: "session_stop_failed",
        severity: "error",
        summary: message,
      });
    }
  }

  async function handleSendText(event: FormEvent) {
    event.preventDefault();
    const resources = resourcesRef.current;
    if (!resources || !activeSession) {
      return;
    }
    const trimmed = draftText.trim();
    if (!trimmed) {
      return;
    }
    try {
      await resources.voiceAi.chat(resources.agentRtmUid, {
        messageType: ChatMessageType.TEXT,
        text: trimmed,
        priority: ChatMessagePriority.INTERRUPTED,
        responseInterruptable: true,
      });
      appendDiagnostic({
        source: "toolkit",
        eventType: "send_text_requested",
        severity: "info",
        summary: "Sent text message to agent RTM identity.",
        details: {
          text: trimmed,
          agentRtmUid: resources.agentRtmUid,
        },
      });
      setDraftText("");
    } catch (sendError) {
      const message = sendError instanceof Error ? sendError.message : "Failed to send text.";
      setError(message);
      appendDiagnostic({
        source: "toolkit",
        eventType: "send_text_failed",
        severity: "error",
        summary: message,
      });
    }
  }

  async function handleInterrupt() {
    const resources = resourcesRef.current;
    if (!resources || !activeSession) {
      return;
    }
    try {
      await resources.voiceAi.interrupt(resources.agentRtmUid);
      appendDiagnostic({
        source: "toolkit",
        eventType: "interrupt_requested",
        severity: "warning",
        summary: "Interrupt requested for the agent RTM identity.",
        details: { agentRtmUid: resources.agentRtmUid },
      });
    } catch (interruptError) {
      const message =
        interruptError instanceof Error
          ? interruptError.message
          : "Failed to interrupt the agent.";
      setError(message);
      appendDiagnostic({
        source: "toolkit",
        eventType: "interrupt_failed",
        severity: "error",
        summary: message,
      });
    }
  }

  const transcriptItems = transcript.filter((item) => item.text && item.text.trim());

  return (
    <main className="page-shell">
      <section className="hero-card">
        <div>
          <p className="eyebrow">Synapse x Agora</p>
          <h1>Voice Test Client</h1>
          <p className="hero-copy">
            Join RTC and RTM first, then activate the local Agora agent, following the official sample flow.
          </p>
        </div>
        <div className={`phase-pill phase-${phase}`}>
          <span className="phase-dot" />
          <strong>{statusLabel(phase)}</strong>
        </div>
      </section>

      {error ? <div className="error-banner">{error}</div> : null}

      <section className="grid-shell">
        <article className="panel form-panel">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Session Setup</p>
              <h2>Prepare Then Activate</h2>
            </div>
            <span className="panel-badge">{config?.service_base_url ?? "Backend unavailable"}</span>
          </div>

          <form className="control-stack" onSubmit={handleStart}>
            <label className="field">
              <span>Profile</span>
              <input
                value={profile}
                onChange={(event) => setProfile(event.target.value)}
                placeholder="VOICE"
                disabled={phase === "starting" || phase === "connected" || phase === "stopping"}
              />
            </label>

            <label className="field">
              <span>Channel name</span>
              <input
                value={channelName}
                onChange={(event) => setChannelName(event.target.value)}
                placeholder="synapse-voice-demo"
                disabled={phase === "starting" || phase === "connected" || phase === "stopping"}
              />
            </label>

            <label className="field">
              <span>Display name</span>
              <input
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                placeholder="Synapse Tester"
                disabled={phase === "starting" || phase === "connected" || phase === "stopping"}
              />
            </label>

            <label className="field">
              <span>User UID override</span>
              <input
                value={userId}
                onChange={(event) => setUserId(event.target.value)}
                placeholder="101"
                disabled={phase === "starting" || phase === "connected" || phase === "stopping"}
              />
            </label>

            <div className="button-row">
              <button
                className="primary-button"
                type="submit"
                disabled={!config?.ready || phase === "starting" || phase === "connected" || phase === "stopping"}
              >
                Start Voice Session
              </button>
              <button
                className="secondary-button"
                type="button"
                disabled={phase !== "connected" && phase !== "error"}
                onClick={() => {
                  void handleStop();
                }}
              >
                Stop Session
              </button>
            </div>
          </form>
        </article>

        <article className="panel session-panel">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Live Session</p>
              <h2>Channel Status</h2>
            </div>
            <span className={`state-pill state-${agentState}`}>{agentState}</span>
          </div>

          <div className="meta-grid">
            <div className="meta-card">
              <p>Gateway binding</p>
              <strong>{activeSession?.binding_id ?? "Not started"}</strong>
            </div>
            <div className="meta-card">
              <p>Synapse session</p>
              <strong>{activeSession?.synapse_session_id ?? "Not started"}</strong>
            </div>
            <div className="meta-card">
              <p>Runtime session</p>
              <strong>{activeSession?.runtime_session_id ?? "Not started"}</strong>
            </div>
            <div className="meta-card">
              <p>Agent RTC UID</p>
              <strong>{activeSession?.agent.uid ?? "Not started"}</strong>
            </div>
            <div className="meta-card">
              <p>App / channel</p>
              <strong>
                {activeSession ? `${activeSession.app_id} / ${activeSession.channel_name}` : "Not started"}
              </strong>
            </div>
            <div className="meta-card">
              <p>User RTC / RTM</p>
              <strong>
                {activeSession
                  ? `${String(activeSession.uid)} / ${activeSession.user_rtm_uid}`
                  : "Not started"}
              </strong>
            </div>
          </div>

          {activeSession?.diagnostics ? (
            <section className="session-diagnostics">
              <header className="session-diagnostics-header">
                <h3>Session Diagnostics</h3>
              </header>
              <div className="meta-grid">
                <DiagnosticMetaCard label="Area" value={activeSession.diagnostics.convoai_area} />
                <DiagnosticMetaCard label="Selected URL" value={activeSession.diagnostics.selected_url} />
                <DiagnosticMetaCard label="Runtime Session" value={activeSession.runtime_session_id} />
                <DiagnosticMetaCard label="Agent RTC UID" value={activeSession.diagnostics.agent_uid} />
                <DiagnosticMetaCard label="Agent RTM UID" value={activeSession.diagnostics.agent_rtm_uid} />
                <DiagnosticMetaCard label="RTC UID" value={String(activeSession.diagnostics.rtc_uid ?? "n/a")} />
                <DiagnosticMetaCard label="RTM User" value={activeSession.diagnostics.rtm_user_id} />
                <DiagnosticMetaCard label="RTM Enabled" value={activeSession.diagnostics.enable_rtm ? "true" : "false"} />
                <DiagnosticMetaCard label="Data Channel" value={activeSession.diagnostics.data_channel ?? "none"} />
                <DiagnosticMetaCard label="Metrics" value={activeSession.diagnostics.enable_metrics ? "true" : "false"} />
                <DiagnosticMetaCard label="Error Messages" value={activeSession.diagnostics.enable_error_message ? "true" : "false"} />
                <DiagnosticMetaCard label="String UID" value={activeSession.diagnostics.enable_string_uid ? "true" : "false"} />
              </div>
            </section>
          ) : null}

          <form className="composer" onSubmit={handleSendText}>
            <textarea
              value={draftText}
              onChange={(event) => setDraftText(event.target.value)}
              rows={4}
              placeholder="Optional text message to the live agent"
              disabled={phase !== "connected"}
            />
            <div className="button-row">
              <button
                className="primary-button"
                type="submit"
                disabled={phase !== "connected" || !draftText.trim()}
              >
                Send Text
              </button>
              <button
                className="secondary-button"
                type="button"
                disabled={phase !== "connected"}
                onClick={() => {
                  void handleInterrupt();
                }}
              >
                Interrupt Agent
              </button>
            </div>
          </form>
        </article>

        <article className="panel transcript-panel">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Transcript</p>
              <h2>Conversation Feed</h2>
            </div>
            <span className="panel-badge">{transcriptItems.length} turns</span>
          </div>

          <div className="transcript-list">
            {transcriptItems.length === 0 ? (
              <div className="empty-state">
                Start a session and speak into the microphone. Transcript updates replace the full history each time, matching the Agora ConvoAI toolkit behavior.
              </div>
            ) : (
              transcriptItems.map((item, index) => (
                <article
                  className="transcript-card"
                  key={`${item.turn_id ?? "turn"}-${item.uid ?? "uid"}-${index}`}
                >
                  <header>
                    <span>UID {item.uid ?? "unknown"}</span>
                    <span>{item.status ?? "unknown"}</span>
                  </header>
                  <p>{item.text}</p>
                </article>
              ))
            )}
          </div>
        </article>

        <article className="panel diagnostics-panel">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Diagnostics</p>
              <h2>Toolkit Timeline</h2>
            </div>
            <span className="panel-badge">{diagnostics.length} events</span>
          </div>

          <div className="diagnostics-list">
            {diagnostics.length === 0 ? (
              <div className="empty-state">
                Start a session to collect toolkit, RTC, RTM, and backend lifecycle diagnostics.
              </div>
            ) : (
              diagnostics.map((entry) => (
                <article className={`diagnostic-card diagnostic-${entry.severity}`} key={entry.id}>
                  <header>
                    <span>{formatDiagnosticTime(entry.ts)}</span>
                    <span className={`diagnostic-source source-${entry.source}`}>{entry.source}</span>
                  </header>
                  <strong>{entry.eventType}</strong>
                  <p>{entry.summary}</p>
                  {entry.details !== undefined ? (
                    <details>
                      <summary>Details</summary>
                      <pre>{formatDiagnosticDetails(entry.details)}</pre>
                    </details>
                  ) : null}
                </article>
              ))
            )}
          </div>
        </article>
      </section>
    </main>
  );
}

async function teardown(resources: ActiveResources | null, notifyBackend: boolean) {
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
    await stopFrontendSession(resources.bindingId);
  }
}
