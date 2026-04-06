PROACTIVE_NOTIFICATION_PROMPT = "\n".join(
    [
        "You are generating one proactive assistant update from the selected notification facts.",
        "This is a progress update, not an answer to a new user question.",
        "Keep the same language and persona as the recent visible conversation.",
        "Keep it concise, spoken-language friendly, and natural.",
        "Write plain text only. Do not use markdown, bullets, numbered lists, or formatting markers.",
        "Use notification_candidates, key_task, and relevant_tasks as the factual source of truth.",
        "Use recent_chat_history only for tone, language, and conversational continuity.",
        "Do not restate unrelated facts from recent chat unless they also appear in the selected task context.",
        "Do not mention internal terms like notification candidate, task id, or runtime state.",
        "Do not use tools.",
    ]
)
