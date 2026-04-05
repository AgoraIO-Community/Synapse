from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..context import CommunicationContext
from ..model import CommunicationDecision


class ScriptedCommunicationModel:
    def __init__(
        self,
        scripted: dict[
            str,
            CommunicationDecision | Callable[[CommunicationContext], CommunicationDecision],
        ],
    ) -> None:
        self._scripted = scripted

    async def decide(
        self,
        *,
        user_text: str,
        context: CommunicationContext,
    ) -> CommunicationDecision:
        if user_text in self._scripted:
            selected = self._scripted[user_text]
        else:
            selected = self._scripted["__default__"]
        if callable(selected):
            return selected(context)
        return selected
