import { startTransition, useEffect, useEffectEvent, useRef, useState } from "react";
import {
  prepareSttSession,
  startSttSession,
  stopSttSession,
  type SttSessionStartResponse,
} from "../../lib/connector-client";
import { submitDraftAsrTurn } from "../../lib/session-client";
import { loadAgoraBrowserStack } from "../../lib/voice-runtime";
import { extractTranscriptText } from "./stt-transcript";

export type SttSessionPhase = "idle" | "starting" | "listening" | "stopping" | "error";

export type SttSessionState = {
  phase: SttSessionPhase;
  error: string | null;
  interimText: string;
  finalTurns: string[];
  sttSession: SttSessionStartResponse | null;
  isMicMuted: boolean;
  activeBroId: string | null;
  lastTranscriptUpdateAt: string | null;
};

const STT_IDLE_TIMEOUT_MS = 10 * 60 * 1000;
const STT_ACTIVITY_EVENTS = ["pointerdown", "keydown", "touchstart", "wheel", "focus"] as const;

const INITIAL_STT_SESSION_STATE: SttSessionState = {
  phase: "idle",
  error: null,
  interimText: "",
  finalTurns: [],
  sttSession: null,
  isMicMuted: true,
  activeBroId: null,
  lastTranscriptUpdateAt: null,
};

type SttResources = {
  rtcClient: any;
  micTrack: any;
  sttSession: SttSessionStartResponse;
};

export function useSttSession({
  sessionId,
  ready,
  defaultBroId,
}: {
  sessionId: string | null;
  ready: boolean;
  defaultBroId: string | null;
}) {
  const [state, setState] = useState<SttSessionState>(INITIAL_STT_SESSION_STATE);
  const resourcesRef = useRef<SttResources | null>(null);
  const mountedRef = useRef(false);
  const startingRef = useRef(false);
  const idleStoppedRef = useRef(false);
  const idleTimerRef = useRef<number | null>(null);
  const activeBroIdRef = useRef<string | null>(null);
  const isMicMutedRef = useRef(true);
  const submittedRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    activeBroIdRef.current = state.activeBroId;
    isMicMutedRef.current = state.isMicMuted;
  }, [state.activeBroId, state.isMicMuted]);

  const clearIdleTimer = useEffectEvent(() => {
    if (idleTimerRef.current !== null) {
      window.clearTimeout(idleTimerRef.current);
      idleTimerRef.current = null;
    }
  });

  const stop = useEffectEvent(async () => {
    clearIdleTimer();
    const resources = resourcesRef.current;
    resourcesRef.current = null;
    if (!resources) {
      if (mountedRef.current) {
        setState((current) => ({
          ...current,
          phase: "idle",
          sttSession: null,
          isMicMuted: true,
        }));
      }
      return;
    }

    if (mountedRef.current) {
      setState((current) => ({ ...current, phase: "stopping", isMicMuted: true }));
    }
    try {
      try {
        await resources.micTrack?.setEnabled?.(false);
      } catch {}
      try {
        resources.micTrack?.stop?.();
        resources.micTrack?.close?.();
      } catch {}
      try {
        await resources.rtcClient?.leave?.();
      } catch {}
      if (resources.sttSession.stt_session_id) {
        await stopSttSession(resources.sttSession.stt_session_id);
      }
      if (mountedRef.current) {
        setState((current) => ({
          ...current,
          phase: "idle",
          error: null,
          sttSession: null,
          isMicMuted: true,
        }));
      }
    } catch (error) {
      if (mountedRef.current) {
        setState((current) => ({
          ...current,
          phase: "error",
          error: error instanceof Error ? error.message : "Failed to stop STT session.",
          isMicMuted: true,
        }));
      }
    }
  });

  const scheduleIdleStop = useEffectEvent(() => {
    clearIdleTimer();
    if (!resourcesRef.current) {
      return;
    }
    idleTimerRef.current = window.setTimeout(() => {
      idleStoppedRef.current = true;
      void stop();
    }, STT_IDLE_TIMEOUT_MS);
  });

  const handleTranscript = useEffectEvent(async (payload: unknown) => {
    if (isMicMutedRef.current || !activeBroIdRef.current || !sessionId) {
      return;
    }
    const parsed = extractTranscriptText(payload);
    if (!parsed) return;
    scheduleIdleStop();
    if (!parsed.final) {
      startTransition(() => {
        setState((current) => ({
          ...current,
          interimText: parsed.text,
          lastTranscriptUpdateAt: new Date().toISOString(),
        }));
      });
      return;
    }

    const key = `${activeBroIdRef.current}:${parsed.text.toLowerCase()}`;
    if (submittedRef.current.has(key)) return;
    submittedRef.current.add(key);
    startTransition(() => {
      setState((current) => ({
        ...current,
        interimText: "",
        finalTurns: [parsed.text, ...current.finalTurns].slice(0, 12),
        lastTranscriptUpdateAt: new Date().toISOString(),
      }));
    });
    await submitDraftAsrTurn(sessionId, {
      raw_text: parsed.text,
      assigned_bro_id: activeBroIdRef.current,
    });
  });

  const start = useEffectEvent(async () => {
    if (!ready || !sessionId || !defaultBroId || resourcesRef.current || startingRef.current) {
      return;
    }
    startingRef.current = true;
    if (mountedRef.current) {
      setState((current) => ({ ...current, phase: "starting", error: null }));
    }

    let rtcClient: any | null = null;
    let micTrack: any | null = null;
    try {
      const prepared = await prepareSttSession({ synapse_session_id: sessionId, channel_name: sessionId });
      const { AgoraRTC } = await loadAgoraBrowserStack();
      rtcClient = AgoraRTC.createClient({ mode: "rtc", codec: "vp8" });
      rtcClient.on?.("stream-message", (_uid: string | number, payload: unknown) => {
        void handleTranscript(payload);
      });
      rtcClient.on?.("stream-message-error", (_uid: string | number, error: unknown) => {
        if (!mountedRef.current) return;
        setState((current) => ({
          ...current,
          error: error instanceof Error ? error.message : "Failed to receive STT transcript.",
        }));
      });
      await rtcClient.join(prepared.app_id, prepared.channel_name, prepared.token, prepared.uid);
      micTrack = await AgoraRTC.createMicrophoneAudioTrack();
      await micTrack.setEnabled?.(false);
      await rtcClient.publish([micTrack]);
      const sttSession = await startSttSession({
        synapse_session_id: sessionId,
        assigned_bro_id: defaultBroId,
        channel_name: prepared.channel_name,
        user_uid: prepared.uid,
      });
      resourcesRef.current = { rtcClient, micTrack, sttSession };
      idleStoppedRef.current = false;
      if (mountedRef.current) {
        setState((current) => ({
          ...current,
          phase: "listening",
          error: null,
          sttSession,
          isMicMuted: true,
        }));
      }
      scheduleIdleStop();
    } catch (error) {
      try {
        await micTrack?.setEnabled?.(false);
      } catch {}
      try {
        micTrack?.stop?.();
        micTrack?.close?.();
      } catch {}
      try {
        await rtcClient?.leave?.();
      } catch {}
      if (mountedRef.current) {
        setState((current) => ({
          ...current,
          phase: "error",
          error: error instanceof Error ? error.message : "Failed to start STT session.",
          sttSession: null,
          isMicMuted: true,
        }));
      }
    } finally {
      startingRef.current = false;
    }
  });

  const setActiveBro = useEffectEvent((broId: string | null) => {
    activeBroIdRef.current = broId;
    setState((current) => ({ ...current, activeBroId: broId }));
  });

  const setMicMuted = useEffectEvent(async (muted: boolean) => {
    if (!resourcesRef.current) {
      if (!muted) {
        await start();
      }
      if (!resourcesRef.current) {
        return;
      }
    }
    try {
      await resourcesRef.current.micTrack?.setEnabled?.(!muted);
      isMicMutedRef.current = muted;
      idleStoppedRef.current = false;
      setState((current) => ({ ...current, isMicMuted: muted, error: null }));
      scheduleIdleStop();
    } catch (error) {
      setState((current) => ({
        ...current,
        error: error instanceof Error ? error.message : "Failed to change microphone state.",
      }));
    }
  });

  const recordActivity = useEffectEvent(() => {
    if (idleStoppedRef.current) {
      idleStoppedRef.current = false;
      void start();
      return;
    }
    scheduleIdleStop();
  });

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      clearIdleTimer();
      const resources = resourcesRef.current;
      resourcesRef.current = null;
      try {
        void resources?.micTrack?.setEnabled?.(false);
        resources?.micTrack?.stop?.();
        resources?.micTrack?.close?.();
      } catch {}
      try {
        void resources?.rtcClient?.leave?.();
      } catch {}
      if (resources?.sttSession.stt_session_id) {
        void stopSttSession(resources.sttSession.stt_session_id);
      }
    };
  }, []);

  useEffect(() => {
    if (!ready || !sessionId || !defaultBroId || idleStoppedRef.current) {
      return;
    }
    void start();
  }, [defaultBroId, ready, sessionId, start]);

  useEffect(() => {
    for (const eventName of STT_ACTIVITY_EVENTS) {
      window.addEventListener(eventName, recordActivity, { passive: true });
    }
    return () => {
      for (const eventName of STT_ACTIVITY_EVENTS) {
        window.removeEventListener(eventName, recordActivity);
      }
    };
  }, [recordActivity]);

  return {
    state,
    start,
    stop,
    setActiveBro,
    setMicMuted,
  };
}
