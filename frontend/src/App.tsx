import { useEffect, useRef, useState, type FormEvent } from "react";
import { createSession, openSessionStream, sendCommand, sendMessage } from "./client";
import type {
  CommandType,
  CommunicationEventPayload,
  ConnectionStatus,
  ExecutionEventPayload,
  SessionSnapshot,
  StreamEvent,
  Task,
  TimelineMessage,
} from "./types";

const MAX_EVENTS = 40;

function formatTime(timestamp: string) {
  return new Date(timestamp).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function canRunCommand(task: Task, command: CommandType) {
  if (command === "pause_task") {
    return task.status === "running";
  }
  if (command === "resume_task") {
    return task.status === "paused" || task.status === "blocked";
  }
  if (command === "cancel_task") {
    return ["queued", "running", "blocked", "paused"].includes(task.status);
  }
  return false;
}

export default function App() {
  const socketRef = useRef<WebSocket | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("booting");
  const [composer, setComposer] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [timeline, setTimeline] = useState<TimelineMessage[]>([]);
  const [tasks, setTasks] = useState<Record<string, Task>>({});
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingTaskCommand, setPendingTaskCommand] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function boot() {
      setConnectionStatus("booting");
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
    };
  }, []);

  useEffect(() => {
    if (!sessionId) {
      return;
    }

    setConnectionStatus("connecting");
    socketRef.current?.close();
    const socket = openSessionStream(sessionId, {
      onOpen: () => {
        setConnectionStatus("connected");
      },
      onClose: () => {
        setConnectionStatus((current) => (current === "error" ? current : "disconnected"));
      },
      onError: () => {
        setConnectionStatus("error");
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

  function applyEvent(event: StreamEvent) {
    if (event.event_type === "session_snapshot") {
      const snapshot = event.payload as unknown as SessionSnapshot;
      const nextTasks = Object.fromEntries(
        snapshot.task_registry.map((task) => [task.task_id, task]),
      );
      setTasks(nextTasks);
      return;
    }

    if (event.category === "communication") {
      const payload = event.payload as unknown as CommunicationEventPayload;
      setTimeline((current) => [
        ...current,
        {
          id: payload.event_id,
          kind: "assistant",
          text: payload.action.render_text ?? payload.action.reason ?? payload.action.action_type,
          timestamp: payload.timestamp,
          taskId: payload.action.target_task_id,
        },
      ]);
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
            output_summary:
              payload.event_type === "completed"
                ? payload.progress_message ?? existing.output_summary
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

  async function handleSendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!sessionId || !composer.trim()) {
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
    ["queued", "running", "blocked", "paused"].includes(task.status),
  );
  const archivedTasks = orderedTasks.filter(
    (task) => !["queued", "running", "blocked", "paused"].includes(task.status),
  );

  return (
    <main className="shell">
      <section className="hero">
        <div>
          <p className="eyebrow">Synopse Runtime Experience</p>
          <h1>Front-stage conversation, back-stage execution.</h1>
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

          <div className="timeline">
            {timeline.length === 0 ? (
              <div className="empty-state">
                Start with a task request like “search flights to Tokyo tomorrow” or ask for
                a draft that needs clarification.
              </div>
            ) : (
              timeline.map((item) => (
                <article key={item.id} className={`bubble bubble-${item.kind}`}>
                  <div className="bubble-meta">
                    <span>{item.kind === "user" ? "You" : "Synopse"}</span>
                    <span>{formatTime(item.timestamp)}</span>
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
              placeholder="Ask Synopse to do something while you keep talking..."
              rows={4}
            />
            <button type="submit" disabled={!composer.trim() || isSending || !sessionId}>
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
                    {(["pause_task", "resume_task", "cancel_task"] as CommandType[]).map(
                      (commandType) => {
                        const busy = pendingTaskCommand === `${task.task_id}:${commandType}`;
                        return (
                          <button
                            key={commandType}
                            type="button"
                            className="ghost-button"
                            disabled={!canRunCommand(task, commandType) || busy}
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
                      <p>{task.output_summary ?? task.goal}</p>
                    </div>
                    <span className="task-status">{task.status}</span>
                  </div>
                </article>
              ))
            )}
          </div>
        </section>

        <section className="panel panel-events">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Runtime Bus</p>
              <h2>Live Activity</h2>
            </div>
          </div>

          <div className="events">
            {events.length === 0 ? (
              <div className="empty-state">Waiting for stream events.</div>
            ) : (
              events.map((event) => {
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
        </section>
      </section>
    </main>
  );
}
