# 0003 Sessionized Execution

Decision:

- Model execution through durable tasks plus `ExecutionSession` and `ExecutionRun`.

Reason:

- preserves user-facing task identity
- gives explicit execution lineage
- supports future executor-native continuity
