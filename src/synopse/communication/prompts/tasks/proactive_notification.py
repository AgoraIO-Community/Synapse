PROACTIVE_NOTIFICATION_PROMPT = "\n".join(
    [
        "You are generating one proactive assistant update from the selected notification facts.",
        "This is a progress update, not an answer to a new user question.",
        "Keep the same language and persona as the recent visible conversation.",
        "Keep it concise, spoken-language friendly, and natural.",
        "Do not mention internal terms like notification candidate, task id, or runtime state.",
        "Do not use tools.",
    ]
)
