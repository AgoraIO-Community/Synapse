from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol
from uuid import uuid4

from .synopse_client import SynopseBridgeClient


@dataclass(slots=True)
class ActiveAgentBinding:
    bridge_session_id: str
    synopse_session_id: str
    channel_name: str | None
    runtime_agent_id: str | None
    task: asyncio.Task[None]


class DuplicateBindingError(RuntimeError):
    pass


class MissingRegistrationConfigError(RuntimeError):
    pass


class BridgeSpeaker(Protocol):
    async def speak(self, runtime_agent_id: str, text: str) -> None:
        ...


class BridgeRegistry:
    def __init__(
        self,
        synopse_client: SynopseBridgeClient,
        speaker: BridgeSpeaker,
    ) -> None:
        self._synopse_client = synopse_client
        self._speaker = speaker
        self._bindings: dict[str, ActiveAgentBinding] = {}
        self._lock = asyncio.Lock()

    async def reserve(
        self,
        *,
        channel_name: str | None = None,
        synopse_session_id: str | None = None,
    ) -> ActiveAgentBinding:
        async with self._lock:
            resolved_session_id = synopse_session_id or await self._synopse_client.create_session()
            if (
                synopse_session_id is not None
                and any(
                    binding.synopse_session_id == resolved_session_id
                    for binding in self._bindings.values()
                )
            ):
                raise DuplicateBindingError(
                    f"Synopse session '{resolved_session_id}' is already bound."
                )

            bridge_session_id = f"bridge-{uuid4().hex[:8]}"
            binding = ActiveAgentBinding(
                bridge_session_id=bridge_session_id,
                synopse_session_id=resolved_session_id,
                channel_name=channel_name,
                runtime_agent_id=None,
                task=asyncio.create_task(
                    self._watch_notifications(
                        synopse_session_id=resolved_session_id,
                        bridge_session_id=bridge_session_id,
                    )
                ),
            )
            self._bindings[bridge_session_id] = binding
            return binding

    async def finalize(
        self,
        bridge_session_id: str,
        *,
        channel_name: str,
        runtime_agent_id: str,
    ) -> ActiveAgentBinding:
        async with self._lock:
            binding = self._bindings.get(bridge_session_id)
            if binding is None:
                raise KeyError(f"Unknown bridge session: {bridge_session_id}")

            if not runtime_agent_id:
                raise MissingRegistrationConfigError(
                    "runtime_agent_id is required for local ConvoAI session binding."
                )

            if any(
                candidate.bridge_session_id != bridge_session_id
                and candidate.runtime_agent_id == runtime_agent_id
                for candidate in self._bindings.values()
            ):
                raise DuplicateBindingError(
                    f"Runtime agent '{runtime_agent_id}' is already registered."
                )

            binding.channel_name = channel_name
            binding.runtime_agent_id = runtime_agent_id
            return binding

    async def unregister(self, bridge_session_id: str) -> bool:
        async with self._lock:
            binding = self._bindings.pop(bridge_session_id, None)
        if binding is None:
            return False
        binding.task.cancel()
        try:
            await binding.task
        except asyncio.CancelledError:
            pass
        return True

    async def close(self) -> None:
        bridge_session_ids = list(self._bindings.keys())
        for bridge_session_id in bridge_session_ids:
            await self.unregister(bridge_session_id)

    def get(self, bridge_session_id: str) -> ActiveAgentBinding | None:
        return self._bindings.get(bridge_session_id)

    async def _watch_notifications(
        self,
        *,
        synopse_session_id: str,
        bridge_session_id: str,
    ) -> None:
        try:
            async for text in self._synopse_client.watch_notification_texts(synopse_session_id):
                binding = self._bindings.get(bridge_session_id)
                if binding is None:
                    return
                if not binding.runtime_agent_id:
                    continue
                try:
                    await self._speaker.speak(binding.runtime_agent_id, text)
                except Exception:
                    continue
        except asyncio.CancelledError:
            raise
