# Local Development

Preferred local bootstrap and run flow:

```bash
./synapse setup
./synapse doctor
./synapse dev
```

By default, diagnostics timeline polling requests from the frontend inspector are
filtered out of `uvicorn.access` output so local access logs are less noisy. Set
`SYNAPSE_QUIET_DIAGNOSTICS_ACCESS_LOGS=false` if you want to see those polling
requests during development.

Current test command:

```bash
.venv/bin/python -m pytest
```

To use the Codex executor locally, make sure the `codex` CLI is installed and keep
`SYNAPSE_CODEX_EXECUTOR_ENABLED=true` in `.env.local`. Set `SYNAPSE_CODEX_COMMAND`
only if Synapse should launch a non-default Codex binary path.

Backend-only and frontend-only commands:

```bash
./synapse backend
./synapse frontend
```

The repo-root bootstrap launcher keeps first-run setup working even before the
package is installed. After setup, the installed console script and module entry
are also available:

```bash
.venv/bin/synapse dev
.venv/bin/python -m synapse dev
```
