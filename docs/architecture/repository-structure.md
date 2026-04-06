# Repository Structure

For open source, Synopse should move toward a `src` layout organized by domain boundaries.

Recommended repository structure:

```text
.
├─ ARCHITECTURE.md
├─ README.md
├─ LICENSE
├─ CONTRIBUTING.md
├─ pyproject.toml
├─ .env.example
├─ docs/
├─ examples/
├─ schemas/
├─ tests/
├─ evals/
├─ fixtures/
├─ replays/
├─ scripts/
├─ frontend/
└─ src/
   └─ synopse/
      ├─ __init__.py
      ├─ protocol/
      ├─ blackboard/
      ├─ communication/
      ├─ execution/
      ├─ executor_core/
      ├─ executor_adapters/
      ├─ notification/
      ├─ runtime/
      ├─ api/
      ├─ cli/
      └─ infrastructure/
```

Recommended package structure inside `src/synopse/`:

```text
src/synopse/
├─ protocol/
├─ blackboard/
├─ communication/
├─ execution/
├─ executor_core/
├─ executor_adapters/
├─ notification/
├─ runtime/
├─ api/
├─ cli/
└─ infrastructure/
```

Organizing rule:

- by domain
- not by framework
- not by generic backend layer names

The most stable public boundaries should be:

- `synopse.protocol`
- `synopse.blackboard.interfaces`
- `synopse.executor_core`

This keeps the project easier to understand and extend in open source.

Additional repository-level guidance:

- `ARCHITECTURE.md`
  - single-entry open-source architecture overview
- `tests/`
  - deterministic correctness
- `evals/`
  - behavior-quality validation
- `fixtures/`
  - shared deterministic scenario inputs
- `replays/`
  - optional captured traces for replay-based inspection
- `scripts/`
  - repository maintenance and dev helpers
- `examples/`
  - minimal runnable demos and integration examples

Migration rule:

- current `runtime/` remains a temporary prototype structure during migration
- target package identity is `synopse`
- avoid introducing a second public package name
