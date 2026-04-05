# Local Development

Preferred backend run command:

```bash
uvicorn synopse.api.app:app --reload
```

Current test command:

```bash
pytest
```

To use the Codex executor locally, make sure the `codex` CLI is installed and keep
`SYNOPSE_CODEX_EXECUTOR_ENABLED=true` in `.env.local`. Set `SYNOPSE_CODEX_COMMAND`
only if Synopse should launch a non-default Codex binary path.

Current frontend flow:

```bash
cd frontend
bun install
bun run dev
```

For the new app path, make sure the package is installed in editable mode first:

```bash
source .venv/bin/activate
pip install -e '.[dev]'
```
