"""Build a persona identity prompt section from session configuration.

The communication brain has its own configurable persona prompt
(``communication_persona_prompt``) that controls the tone, style, and
personality of the conversation brain itself.

Worker persona ``base_prompt`` values are NOT injected here — they belong
to the execution brain and should not pollute the communication brain's
system identity.
"""

from __future__ import annotations

from synapse.communication.context import CommunicationContext


def build_persona_identity_prompt(context: CommunicationContext) -> str | None:
    """Return the communication brain's persona prompt, or *None* if not configured."""
    if context.communication_persona_prompt.strip():
        return context.communication_persona_prompt.strip()
    return None
