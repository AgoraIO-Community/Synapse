from __future__ import annotations

from typing import Any

from .jsonrpc import JsonRpcPeer


class CodexAppServerClient:
    def __init__(self, peer: JsonRpcPeer) -> None:
        self._peer = peer

    async def initialize(self) -> dict[str, object]:
        result = await self._peer.request(
            "initialize",
            {
                "clientInfo": {
                    "name": "synapse-codex-executor",
                    "version": "0.1",
                },
                "capabilities": {
                    "experimental_api": True,
                },
            },
        )
        await self._peer.notify("initialized", {})
        return _as_dict(result)

    async def get_account(self) -> dict[str, object]:
        result = await self._peer.request(
            "account/read",
            {"refreshToken": False},
        )
        return _as_dict(result)

    async def thread_start(
        self,
        *,
        cwd: str,
        approval_policy: str = "never",
        sandbox: str = "workspace-write",
    ) -> dict[str, object]:
        result = await self._peer.request(
            "thread/start",
            {
                "cwd": cwd,
                "approvalPolicy": approval_policy,
                "sandbox": sandbox,
            },
        )
        return _as_dict(result)

    async def thread_fork(
        self,
        *,
        thread_id: str,
        cwd: str,
        approval_policy: str = "never",
        sandbox: str = "workspace-write",
    ) -> dict[str, object]:
        result = await self._peer.request(
            "thread/fork",
            {
                "threadId": thread_id,
                "cwd": cwd,
                "approvalPolicy": approval_policy,
                "sandbox": sandbox,
            },
        )
        return _as_dict(result)

    async def thread_read(
        self,
        *,
        thread_id: str,
        include_turns: bool = True,
    ) -> dict[str, object]:
        result = await self._peer.request(
            "thread/read",
            {
                "threadId": thread_id,
                "includeTurns": include_turns,
            },
        )
        return _as_dict(result)

    async def turn_start(
        self,
        *,
        thread_id: str,
        prompt: str,
    ) -> dict[str, object]:
        result = await self._peer.request(
            "turn/start",
            {
                "threadId": thread_id,
                "input": [
                    {
                        "type": "text",
                        "text": prompt,
                        "textElements": [],
                    }
                ],
            },
        )
        return _as_dict(result)

    async def next_event(self) -> dict[str, object]:
        return await self._peer.next_event()

    async def close(self) -> None:
        await self._peer.close()


def _as_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    return {}
