# Add Executor Adapter

Future executor adapters should follow the same package template:

- `executor.py`
- `session.py`
- `normalizer.py`
- `config.py`

Before adding an adapter:

1. Read the executor core abstractions.
2. Map adapter capabilities onto `ExecutorCapabilities`.
3. Keep executor-native state inside the adapter boundary.
4. Do not leak provider-specific protocol details into shared task or blackboard models.
