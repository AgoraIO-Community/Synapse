import { useState } from "react";

import type { AttentionItem, InteractionRequest } from "../types";
import { Button } from "./ui/button";

export function AttentionPanel({
  attentionItems,
  interactionRequests,
  onResolve,
  onJump,
}: {
  attentionItems: AttentionItem[];
  interactionRequests: InteractionRequest[];
  onResolve: (
    requestId: string,
    action: "approve" | "deny" | "answer" | "confirm" | "cancel",
    options?: { answerText?: string },
  ) => Promise<void>;
  onJump?: (taskId: string) => void;
}) {
  const [answerDrafts, setAnswerDrafts] = useState<Record<string, string>>({});
  const [answering, setAnswering] = useState<Record<string, boolean>>({});
  const [pendingRequestId, setPendingRequestId] = useState<string | null>(null);

  const activeItems = attentionItems.filter((item) => item.status === "active");

  if (activeItems.length === 0) {
    return null;
  }

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold tracking-tight text-[#212723]">Attention</h3>
        <p className="text-[0.65rem] font-bold uppercase tracking-[0.18em] text-[#6d766f]">
          Action needed
        </p>
      </div>
      <div className="space-y-3">
        {activeItems.map((item) => {
          const request =
            item.request_id != null
              ? interactionRequests.find((candidate) => candidate.request_id === item.request_id) ?? null
              : null;
          const isAnswering = item.request_id ? answering[item.request_id] === true : false;
          const answerDraft = item.request_id ? answerDrafts[item.request_id] ?? "" : "";
          return (
            <div
              key={item.attention_id}
              className="rounded-[1.15rem] border border-[rgba(214,255,100,0.12)] bg-[linear-gradient(180deg,rgba(29,31,35,0.96),rgba(24,26,30,0.92))] px-4 py-4 text-white shadow-[0_22px_40px_-30px_rgba(0,0,0,0.55)]"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-[#d7ff1f]/10 px-2.5 py-1 text-[0.6rem] font-black uppercase tracking-[0.18em] text-[#d7ff1f]">
                  {item.kind.replaceAll("_", " ")}
                </span>
                <span className="rounded-full bg-white/8 px-2.5 py-1 text-[0.6rem] font-bold uppercase tracking-[0.16em] text-white/55">
                  {item.priority}
                </span>
              </div>
              <h4 className="mt-3 text-base font-bold tracking-tight text-white">{item.title}</h4>
              <p className="mt-2 text-sm leading-5 text-slate-300">{item.body}</p>

              {request && request.kind === "question" && isAnswering ? (
                <div className="mt-3 space-y-2">
                  <textarea
                    value={answerDraft}
                    onChange={(event) =>
                      setAnswerDrafts((current) => ({
                        ...current,
                        [request.request_id]: event.target.value,
                      }))
                    }
                    rows={3}
                    className="w-full rounded bg-white/8 px-3 py-2 text-sm text-white outline-none ring-1 ring-white/10 focus:ring-[#d7ff1f]/40"
                    placeholder="Type your answer..."
                  />
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      size="sm"
                      disabled={!answerDraft.trim() || pendingRequestId === request.request_id}
                      onClick={async () => {
                        setPendingRequestId(request.request_id);
                        try {
                          await onResolve(request.request_id, "answer", {
                            answerText: answerDraft,
                          });
                          setAnswering((current) => ({ ...current, [request.request_id]: false }));
                          setAnswerDrafts((current) => ({ ...current, [request.request_id]: "" }));
                        } finally {
                          setPendingRequestId(null);
                        }
                      }}
                      className="bg-[#d7ff1f] text-[#1b2212] hover:bg-[#dff86f]"
                    >
                      {pendingRequestId === request.request_id ? "Sending..." : "Submit answer"}
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      onClick={() =>
                        setAnswering((current) => ({ ...current, [request.request_id]: false }))
                      }
                      className="bg-white/8 text-white hover:bg-white/12"
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : null}

              <div className="mt-3 flex flex-wrap gap-2">
                {request ? (
                  request.available_actions.map((action) => {
                    if (action === "answer") {
                      return (
                        <Button
                          key={action}
                          type="button"
                          size="sm"
                          variant="secondary"
                          onClick={() =>
                            setAnswering((current) => ({ ...current, [request.request_id]: true }))
                          }
                          className="bg-[#d7ff1f] text-[#1b2212] hover:bg-[#dff86f]"
                        >
                          Answer
                        </Button>
                      );
                    }
                    return (
                      <Button
                        key={action}
                        type="button"
                        size="sm"
                        variant="secondary"
                        disabled={pendingRequestId === request.request_id}
                        onClick={async () => {
                          setPendingRequestId(request.request_id);
                          try {
                            await onResolve(
                              request.request_id,
                              action as "approve" | "deny" | "confirm" | "cancel",
                            );
                          } finally {
                            setPendingRequestId(null);
                          }
                        }}
                        className={
                          action === "approve" || action === "confirm"
                            ? "bg-[#d7ff1f] text-[#1b2212] hover:bg-[#dff86f]"
                            : "bg-white/8 text-white hover:bg-white/12"
                        }
                      >
                        {pendingRequestId === request.request_id
                          ? "Working..."
                          : action === "approve"
                            ? "Allow"
                            : action === "deny"
                              ? "Deny"
                              : action === "confirm"
                                ? "Confirm"
                                : "Cancel"}
                      </Button>
                    );
                  })
                ) : null}
                {item.task_id && onJump ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    onClick={() => onJump(item.task_id!)}
                    className="bg-white/8 text-white hover:bg-white/12"
                  >
                    Open task
                  </Button>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
