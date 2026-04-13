# Repository Structure

For open source, Synapse should move toward a `src` layout organized by domain boundaries.

Recommended repository structure:

```text
.
├─ ARCHITECTURE.md
├─ README.md
├─ LICENSE
├─ CONTRIBUTING.md
├─ pyproject.toml
├─ install.sh
├─ .env.example
├─ docs/
├─ examples/
├─ exmaple-ui/
├─ schemas/
├─ tests/
├─ evals/
├─ scripts/
└─ src/
   └─ synapse/
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
      ├─ gateway_host/
      ├─ gateways/
      ├─ cli/
      ├─ ui/
      └─ infrastructure/
```

Recommended package structure inside `src/synapse/`:

```text
src/synapse/
├─ protocol/
├─ blackboard/
├─ communication/
├─ execution/
├─ executor_core/
├─ executor_adapters/
├─ notification/
├─ runtime/
├─ api/
├─ gateway_host/
├─ gateways/
├─ cli/
├─ ui/
└─ infrastructure/
```

Organizing rule:

- by domain
- not by framework
- not by generic backend layer names

The most stable public boundaries should be:

- `synapse.protocol`
- `synapse.blackboard.interfaces`
- `synapse.executor_core`

This keeps the project easier to understand and extend in open source.

Additional repository-level guidance:

- `ARCHITECTURE.md`
  - single-entry open-source architecture overview
- `tests/`
  - deterministic correctness
- `evals/`
  - behavior-quality validation
- `scripts/`
  - repository maintenance and dev helpers
- `examples/`
  - minimal runnable demos and integration examples
- `exmaple-ui/`
  - repo-root example browser clients and first-party demo frontends
  - keep reusable backend and gateway logic out of this directory

Migration rule:

- current `runtime/` remains a temporary prototype structure during migration
- target package identity is `synapse`
- avoid introducing a second public package name
