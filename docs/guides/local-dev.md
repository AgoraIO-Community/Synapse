# Local Development

Preferred backend run command:

```bash
uvicorn synopse.api.app:app --reload
```

Current test command:

```bash
pytest
```

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
