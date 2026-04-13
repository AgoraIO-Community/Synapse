GUARDRAILS_PROMPT = "\n".join(
    [
        "Do not expose internal tool names, command schemas, or runtime vocabulary unless the user explicitly asks for them.",
        "Do not emit mechanical text like 'task created successfully' or 'command applied'.",
    ]
)
