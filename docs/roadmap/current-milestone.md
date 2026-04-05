# Current Milestone

This page should stay short and current.

## Active Phase

- `Cutover: Remove Legacy Runtime Path`
- status: `in progress`

## Immediate Next Milestone

- remove the legacy `runtime/` implementation
- remove legacy tests that depend on `runtime.*`
- leave `src/synopse` as the only active backend path

## Explicitly Out of Scope Right Now

- production-grade executor adapters
- finalized proactive notification behavior

## Transition Condition

Move into the next phase when:

- no active code imports `runtime.*`
- no active tests depend on `runtime.*`
- docs and run guidance point only to `synopse.api.app`
