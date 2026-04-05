# 0002 No Message Interpreter

Decision:

- Remove the standalone message-interpreter layer from the primary `v2` design.

Reason:

- lower first-turn latency
- simpler runtime entrance
- interpretation becomes part of Communication Brain tool use
