from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol
from uuid import uuid4

from synopse.runtime import RuntimeContainer

if TYPE_CHECKING:
    from synopse.runtime.session import SessionRuntime


@dataclass(slots=True)
class ActiveAgentBinding:
    bridge_session_id: str
    synopse_session_id: str
    agent_id: str
    channel_name: str
    runtime_agent_id: str
    queue: asyncio.Queue
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
        runtime_container: RuntimeContainer,
        speaker: BridgeSpeaker,
    ) -> None:
        self._runtime_container = runtime_container
        self._speaker = speaker
        self._bindings: dict[str, ActiveAgentBinding] = {}
        self._lock = asyncio.Lock()

    async def register(
        self,
        *,
        agent_id: str,
        channel_name: str,
        runtime_agent_id: str,
        synopse_session_id: str | None = None,
    ) -> ActiveAgentBinding:
        async with self._lock:
            if any(binding.agent_id == agent_id for binding in self._bindings.values()):
                raise DuplicateBindingError(f"Agent '{agent_id}' is already registered.")
            if (
                synopse_session_id is not None
                and any(
                    binding.synopse_session_id == synopse_session_id
                    for binding in self._bindings.values()
                )
            ):
                raise DuplicateBindingError(
                    f"Synopse session '{synopse_session_id}' is already bound."
                )

            if not runtime_agent_id:
                raise MissingRegistrationConfigError(
                    "runtime_agent_id is required for local ConvoAI session binding."
                )

            session = self._resolve_or_create_session(synopse_session_id)
            queue = session.subscribe()
            bridge_session_id = f"bridge-{uuid4().hex[:8]}"
            binding = ActiveAgentBinding(
                bridge_session_id=bridge_session_id,
                synopse_session_id=session.session_id,
                agent_id=agent_id,
                channel_name=channel_name,
                runtime_agent_id=runtime_agent_id,
                queue=queue,
                task=asyncio.create_task(
                    self._watch_notifications(
                        session=session,
                        queue=queue,
                        bridge_session_id=bridge_session_id,
                    )
                ),
            )
            self._bindings[bridge_session_id] = binding
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

    def _resolve_or_create_session(self, session_id: str | None) -> "SessionRuntime":
        if session_id is None:
            return self._runtime_container.create_session()
        return self._runtime_container.get_session(session_id)

    async def _watch_notifications(
        self,
        *,
        session: "SessionRuntime",
        queue: asyncio.Queue,
        bridge_session_id: str,
    ) -> None:
        try:
            while True:
                event = await queue.get()
                binding = self._bindings.get(bridge_session_id)
                if binding is None:
                    return
                if getattr(event, "type", None) != "conversation_appended":
                    continue
                if getattr(event, "source", None) != "notification":
                    continue
                text = getattr(event, "text", None)
                if not isinstance(text, str) or not text.strip():
                    continue
                try:
                    await self._speaker.speak(binding.runtime_agent_id, text)
                except Exception:
                    continue
        except asyncio.CancelledError:
            raise
        finally:
            session.unsubscribe(queue)
