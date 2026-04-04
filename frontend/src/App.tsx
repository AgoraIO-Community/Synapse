import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { createSession, openSessionStream, openTraceStream, sendCommand, sendMessage } from "./client";
import type {
  Artifact,
  CommandType,
  CommunicationChunkPayload,
  CommunicationEventPayload,
  ConnectionStatus,
  ExecutorCapability,
  ExecutionEventPayload,
  SessionSnapshot,
  StreamEvent,
  Task,
  TraceEvent,
  TraceSnapshot,
  TimelineMessage,
} from "./types";

const MAX_EVENTS = 40;
const HIDDEN_RUNTIME_EVENT_TYPES = new Set(["response_chunk"]);
const HIDDEN_TRACE_EVENT_TYPES = new Set([
  "llm_response_stream_request",
  "llm_response_stream_response",
  "llm_response_stream_error",
]);
const TIMELINE_FOLLOW_THRESHOLD_PX = 32;

function formatTime(timestamp: string) {
  return new Date(timestamp).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatMessageTime(timestamp: string) {
  const date = new Date(timestamp);
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  const seconds = String(date.getSeconds()).padStart(2, "0");
  const milliseconds = String(date.getMilliseconds()).padStart(3, "0");
  return `${hours}:${minutes}:${seconds}.${milliseconds}`;
}

function extractFullTaskResult(task: Task) {
  for (const artifact of task.artifacts) {
    if (typeof artifact.inline_value === "string" && artifact.inline_value.trim()) {
      return artifact.inline_value.trim();
    }
  }
  return task.output_summary ?? task.goal;
}

function canRunCommand(
  task: Task,
  command: CommandType,
  capabilitiesByExecutor: Record<string, ExecutorCapability>,
) {
  const capability = task.assigned_executor
    ? capabilitiesByExecutor[task.assigned_executor]
    : undefined;
  if (command === "cancel_task") {
    return (
      ["queued", "running", "blocked"].includes(task.status) &&
      (capability?.supports_cancel ?? true)
    );
  }
  return false;
}

function isNearTimelineBottom(element: HTMLDivElement) {
  return (
    element.scrollHeight - element.scrollTop - element.clientHeight <=
    TIMELINE_FOLLOW_THRESHOLD_PX
  );
}

export default function App() {
  const socketRef = useRef<WebSocket | null>(null);
  const traceSocketRef = useRef<WebSocket | null>(null);
  const timelineRef = useRef<HTMLDivElement | null>(null);
  const shouldFollowTimelineRef = useRef(true);
  const didBootRef = useRef(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("booting");
  const [traceConnectionStatus, setTraceConnectionStatus] = useState<ConnectionStatus>("booting");
  const [composer, setComposer] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isStreamReady, setIsStreamReady] = useState(false);
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [traceEvents, setTraceEvents] = useState<TraceEvent[]>([]);
  const [timeline, setTimeline] = useState<TimelineMessage[]>([]);
  const [tasks, setTasks] = useState<Record<string, Task>>({});
  const [executorCapabilities, setExecutorCapabilities] = useState<
    Record<string, ExecutorCapability>
  >({});
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);
  const [expandedTraceEventId, setExpandedTraceEventId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingTaskCommand, setPendingTaskCommand] = useState<string | null>(null);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const visibleOutcomeEvents = events.filter(
    (event) => !HIDDEN_RUNTIME_EVENT_TYPES.has(event.event_type),
  );

  useEffect(() => {
    const timelineElement = timelineRef.current;
    if (!timelineElement || !shouldFollowTimelineRef.current || timeline.length === 0) {
      return;
    }
    timelineElement.scrollTop = timelineElement.scrollHeight;
  }, [timeline]);

  useEffect(() => {
    if (didBootRef.current) {
      return;
    }
    didBootRef.current = true;
    let active = true;

    async function boot() {
      setConnectionStatus("booting");
      setActionError(null);
      try {
        const session = await createSession();
        if (!active) {
          return;
        }
        setSessionId(session.session_id);
      } catch (error) {
        if (!active) {
          return;
        }
        setConnectionStatus("error");
        setActionError(error instanceof Error ? error.message : "Failed to create session.");
      }
    }

    void boot();
    return () => {
      active = false;
      socketRef.current?.close();
      traceSocketRef.current?.close();
    };
  }, []);

  useEffect(() => {
    if (!sessionId) {
      return;
    }

    setConnectionStatus("connecting");
    setIsStreamReady(false);
    setActionError(null);
    socketRef.current?.close();
    const socket = openSessionStream(sessionId, {
      onOpen: () => {
        setConnectionStatus("connecting");
      },
      onClose: () => {
        setIsStreamReady(false);
        setConnectionStatus((current) => (current === "error" ? current : "disconnected"));
      },
      onError: () => {
        setIsStreamReady(false);
        setConnectionStatus("error");
        setActionError(
          "Live runtime stream could not connect. Check that the backend has WebSocket support and is running.",
        );
      },
      onMessage: (event) => {
        setEvents((current) => [event, ...current].slice(0, MAX_EVENTS));
        applyEvent(event);
      },
    });
    socketRef.current = socket;

    return () => {
      socket.close();
    };
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId) {
      return;
    }

    setTraceConnectionStatus("connecting");
    traceSocketRef.current?.close();
    const traceSocket = openTraceStream(sessionId, {
      onOpen: () => {
        setTraceConnectionStatus("connecting");
      },
      onClose: () => {
        setTraceConnectionStatus((current) =>
          current === "error" ? current : "disconnected",
        );
      },
      onError: () => {
        setTraceConnectionStatus("error");
      },
      onMessage: (event) => {
        applyTraceEvent(event);
      },
    });
    traceSocketRef.current = traceSocket;

    return () => {
      traceSocket.close();
    };
  }, [sessionId]);

  function upsertAssistantTimelineMessage(
    messageId: string,
    text: string,
    timestamp: string,
    taskId: string | null,
    streaming: boolean,
  ) {
    setTimeline((current) => {
      const nextMessage: TimelineMessage = {
        id: messageId,
        kind: "assistant",
        text,
        timestamp,
        taskId,
        streaming,
      };
      const existingIndex = current.findIndex((item) => item.id === messageId);
      if (existingIndex === -1) {
        return [...current, nextMessage];
      }
      const next = current.slice();
      next[existingIndex] = {
        ...next[existingIndex],
        ...nextMessage,
      };
      return next;
    });
  }

  function applyEvent(event: StreamEvent) {
    if (event.event_type === "session_snapshot") {
      setConnectionStatus("connected");
      setIsStreamReady(true);
      setActionError(null);
      const snapshot = event.payload as unknown as SessionSnapshot;
      const nextTasks = Object.fromEntries(
        snapshot.task_registry.map((task) => [task.task_id, task]),
      );
      const nextCapabilities = Object.fromEntries(
        snapshot.executor_capabilities.map((capability) => [
          capability.executor_id,
          capability,
        ]),
      );
      setTasks(nextTasks);
      setExecutorCapabilities(nextCapabilities);
      return;
    }

    if (event.category === "communication") {
      if (event.event_type === "response_chunk") {
        const payload = event.payload as unknown as CommunicationChunkPayload;
        upsertAssistantTimelineMessage(
          payload.action_id,
          payload.render_text,
          payload.timestamp,
          payload.target_task_id,
          true,
        );
        return;
      }

      const payload = event.payload as unknown as CommunicationEventPayload;
      upsertAssistantTimelineMessage(
        payload.action.action_id,
        payload.action.render_text ?? payload.action.reason ?? payload.action.action_type,
        payload.timestamp,
        payload.action.target_task_id,
        false,
      );
      return;
    }

    if (event.category === "task") {
      const payload = event.payload as unknown as Task;
      setTasks((current) => ({
        ...current,
        [payload.task_id]: payload,
      }));
      return;
    }

    if (event.category === "execution") {
      const payload = event.payload as unknown as ExecutionEventPayload;
      setTasks((current) => {
        const existing = current[payload.task_id];
        if (!existing) {
          return current;
        }
        return {
          ...current,
          [payload.task_id]: {
            ...existing,
            status: payload.status,
            updated_at: payload.timestamp,
            artifacts:
              payload.event_type === "completed"
                ? [...existing.artifacts, ...payload.artifacts_delta]
                : existing.artifacts,
            output_summary:
              payload.event_type === "completed"
                ? (() => {
                    const fullResultArtifact = payload.artifacts_delta.find(
                      (artifact: Artifact) =>
                        typeof artifact.inline_value === "string" &&
                        artifact.inline_value.trim().length > 0,
                    );
                    if (
                      fullResultArtifact &&
                      typeof fullResultArtifact.inline_value === "string"
                    ) {
                      return fullResultArtifact.inline_value.trim();
                    }
                    return payload.progress_message ?? existing.output_summary;
                  })()
                : existing.output_summary,
            block_reason:
              payload.event_type === "blocked"
                ? payload.progress_message
                : existing.block_reason,
          },
        };
      });
    }
  }

  function applyTraceEvent(event: TraceEvent) {
    if (event.event_type === "trace_snapshot") {
      setTraceConnectionStatus("connected");
      const snapshot = event.payload as unknown as TraceSnapshot;
      setTraceEvents(
        snapshot.recent_traces
          .filter((trace) => !HIDDEN_TRACE_EVENT_TYPES.has(trace.event_type))
          .slice()
          .reverse(),
      );
      return;
    }

    setTraceConnectionStatus("connected");
    if (HIDDEN_TRACE_EVENT_TYPES.has(event.event_type)) {
      return;
    }
    setTraceEvents((current) => [event, ...current].slice(0, MAX_EVENTS));
  }

  function handleTimelineScroll() {
    const timelineElement = timelineRef.current;
    if (!timelineElement) {
      return;
    }
    shouldFollowTimelineRef.current = isNearTimelineBottom(timelineElement);
  }

  async function handleCopyEvents() {
    if (!sessionId) {
      return;
    }

    const diagnosticPayload = [
      `session_id: ${sessionId}`,
      `runtime_connection: ${connectionStatus}`,
      `trace_connection: ${traceConnectionStatus}`,
      "",
      "== Runtime Events ==",
      JSON.stringify(visibleOutcomeEvents, null, 2),
      "",
      "== Trace Events ==",
      JSON.stringify(traceEvents, null, 2),
    ].join("\n");

    try {
      await navigator.clipboard.writeText(diagnosticPayload);
      setCopyStatus("Copied");
      setActionError(null);
      window.setTimeout(() => setCopyStatus((current) => (current === "Copied" ? null : current)), 2000);
    } catch (error) {
      setCopyStatus(null);
      setActionError(error instanceof Error ? error.message : "Failed to copy events.");
    }
  }

  async function submitComposerMessage() {
    if (!sessionId || !composer.trim() || !isStreamReady) {
      return;
    }

    const text = composer.trim();
    setActionError(null);
    setComposer("");
    setIsSending(true);
    setTimeline((current) => [
      ...current,
      {
        id: `user-${Date.now()}`,
        kind: "user",
        text,
        timestamp: new Date().toISOString(),
      },
    ]);

    try {
      await sendMessage(sessionId, text);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Failed to send message.");
    } finally {
      setIsSending(false);
    }
  }

  async function handleSendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitComposerMessage();
  }

  async function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) {
      return;
    }

    event.preventDefault();
    await submitComposerMessage();
  }

  async function handleCommand(taskId: string, commandType: CommandType) {
    if (!sessionId) {
      return;
    }
    setActionError(null);
    setPendingTaskCommand(`${taskId}:${commandType}`);
    try {
      await sendCommand(sessionId, commandType, taskId);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Failed to send command.");
    } finally {
      setPendingTaskCommand(null);
    }
  }

  const orderedTasks = Object.values(tasks).sort((left, right) =>
    right.updated_at.localeCompare(left.updated_at),
  );
  const activeTasks = orderedTasks.filter((task) =>
    ["queued", "running", "blocked"].includes(task.status),
  );
  const archivedTasks = orderedTasks.filter(
    (task) => !["queued", "running", "blocked"].includes(task.status),
  );

  return (
    <main className="shell">
      <section className="hero">
        <div>
          <p className="eyebrow">Synopse Runtime Experience</p>
          <h1>Synopse</h1>
          <p className="intro">
            This UI lets you experience the communication brain and execution brain as one
            coordinated runtime: speak through the chat lane, watch tasks unfold beside it,
            and inspect the live event stream underneath.
          </p>
        </div>
        <div className={`status-pill status-${connectionStatus}`}>
          <span className="status-dot" />
          <span>{connectionStatus}</span>
          {sessionId ? <code>{sessionId}</code> : null}
        </div>
      </section>

      {actionError ? <div className="error-banner">{actionError}</div> : null}

      <section className="workspace">
        <section className="panel panel-chat">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Communication Brain</p>
              <h2>Conversation</h2>
            </div>
          </div>

          <div ref={timelineRef} className="timeline" onScroll={handleTimelineScroll}>
            {timeline.length === 0 ? (
              <div className="empty-state">
                {isStreamReady
                  ? "Start with a task request like “search flights to Tokyo tomorrow” or ask for a draft that needs clarification."
                  : "Waiting for the runtime stream to connect before accepting messages."}
              </div>
            ) : (
              timeline.map((item) => (
                <article key={item.id} className={`bubble bubble-${item.kind}`}>
                  <div className="bubble-meta">
                    <span>{item.kind === "user" ? "You" : "Synopse"}</span>
                    <span>{formatMessageTime(item.timestamp)}</span>
                  </div>
                  <p>{item.text}</p>
                  {item.taskId ? <small>task: {item.taskId}</small> : null}
                </article>
              ))
            )}
          </div>

          <form className="composer" onSubmit={handleSendMessage}>
            <textarea
              value={composer}
              onChange={(event) => setComposer(event.target.value)}
              onKeyDown={(event) => void handleComposerKeyDown(event)}
              placeholder={
                isStreamReady
                  ? "Ask Synopse to do something while you keep talking..."
                  : "Waiting for runtime stream..."
              }
              disabled={!isStreamReady}
              rows={4}
            />
            <button
              type="submit"
              disabled={!composer.trim() || isSending || !sessionId || !isStreamReady}
            >
              {isSending ? "Sending..." : "Send"}
            </button>
          </form>
        </section>

        <section className="panel panel-tasks">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Execution Brain</p>
              <h2>Tasks</h2>
            </div>
          </div>

          <div className="task-sections">
            <div className="task-section">
              <h3>Active</h3>
              {activeTasks.length === 0 ? (
                <div className="empty-state">No active tasks yet.</div>
              ) : (
                activeTasks.map((task) => (
                  <article key={task.task_id} className={`task-card status-${task.status}`}>
                    <div className="task-head">
                      <div>
                        <strong>{task.title}</strong>
                        <p>{task.goal}</p>
                      </div>
                      <span className="task-status">{task.status}</span>
                    </div>
                    <dl className="task-meta">
                      <div>
                        <dt>Executor</dt>
                        <dd>{task.assigned_executor ?? "unassigned"}</dd>
                      </div>
                      <div>
                        <dt>Updated</dt>
                        <dd>{formatTime(task.updated_at)}</dd>
                      </div>
                      {task.block_reason ? (
                        <div>
                          <dt>Blocked</dt>
                          <dd>{task.block_reason}</dd>
                        </div>
                      ) : null}
                    </dl>
                    <div className="task-actions">
                      {(["cancel_task"] as CommandType[]).map(
                        (commandType) => {
                          const busy = pendingTaskCommand === `${task.task_id}:${commandType}`;
                          return (
                            <button
                              key={commandType}
                              type="button"
                              className="ghost-button"
                              disabled={
                                !canRunCommand(task, commandType, executorCapabilities) || busy
                              }
                              onClick={() => handleCommand(task.task_id, commandType)}
                            >
                              {busy ? "..." : commandType.replace("_task", "").replace("_", " ")}
                            </button>
                          );
                        },
                      )}
                    </div>
                  </article>
                ))
              )}
            </div>

            <div className="task-section">
              <h3>Completed</h3>
              {archivedTasks.length === 0 ? (
                <div className="empty-state">Finished tasks will appear here.</div>
              ) : (
                archivedTasks.map((task) => (
                  <article key={task.task_id} className={`task-card status-${task.status}`}>
                    <div className="task-head">
                      <div>
                        <strong>{task.title}</strong>
                        <p>{extractFullTaskResult(task)}</p>
                      </div>
                      <span className="task-status">{task.status}</span>
                    </div>
                  </article>
                ))
              )}
            </div>
          </div>
        </section>

        <section className="panel panel-events">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Runtime Bus</p>
              <h2>Live Activity</h2>
            </div>
            <button type="button" className="ghost-button" onClick={() => void handleCopyEvents()}>
              {copyStatus ?? "Copy Events"}
            </button>
          </div>

          <div className="events">
            <div className="trace-section">
              <div className="trace-section-header">
                <h3>Outcome Events</h3>
                <span className={`trace-status trace-${connectionStatus}`}>{connectionStatus}</span>
              </div>
              {visibleOutcomeEvents.length === 0 ? (
                <div className="empty-state">Waiting for stream events.</div>
              ) : (
                visibleOutcomeEvents.map((event) => {
                  const expanded = expandedEventId === event.stream_event_id;
                  return (
                    <article key={event.stream_event_id} className="event-row">
                      <button
                        type="button"
                        className="event-summary"
                        onClick={() =>
                          setExpandedEventId((current) =>
                            current === event.stream_event_id ? null : event.stream_event_id,
                          )
                        }
                      >
                        <span className="event-seq">#{event.sequence}</span>
                        <span className="event-type">{event.event_type}</span>
                        <span className="event-category">{event.category}</span>
                        <span className="event-time">{formatTime(event.timestamp)}</span>
                      </button>
                      {expanded ? (
                        <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                      ) : null}
                    </article>
                  );
                })
              )}
            </div>

            <div className="trace-section">
              <div className="trace-section-header">
                <h3>Trace Flow</h3>
                <span className={`trace-status trace-${traceConnectionStatus}`}>
                  {traceConnectionStatus}
                </span>
              </div>
              {traceEvents.length === 0 ? (
                <div className="empty-state">Waiting for trace events.</div>
              ) : (
                traceEvents.map((event) => {
                  const expanded = expandedTraceEventId === event.trace_event_id;
                  return (
                    <article key={event.trace_event_id} className="event-row">
                      <button
                        type="button"
                        className="trace-summary"
                        onClick={() =>
                          setExpandedTraceEventId((current) =>
                            current === event.trace_event_id ? null : event.trace_event_id,
                          )
                        }
                      >
                        <span className="event-seq">#{event.trace_sequence}</span>
                        <span className="trace-stage">{event.stage}</span>
                        <span className="event-type">{event.event_type}</span>
                        <span className="trace-source">{event.source_module}</span>
                        <span className="event-time">{formatTime(event.timestamp)}</span>
                      </button>
                      {expanded ? (
                        <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                      ) : null}
                    </article>
                  );
                })
              )}
            </div>
          </div>
        </section>
      </section>
    </main>
  );
}
