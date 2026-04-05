from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

from pydantic import PrivateAttr

from synopse.executor_core import ExecutorSession

from .client import CodexAppServerClient
from .jsonrpc import JsonRpcPeer


class CodexExecutorSession(ExecutorSession):
    _process: asyncio.subprocess.Process | None = PrivateAttr(default=None)
    _peer: JsonRpcPeer | None = PrivateAttr(default=None)
    _client: CodexAppServerClient | None = PrivateAttr(default=None)
    _cwd: Path | None = PrivateAttr(default=None)
    _stderr_lines: list[str] = PrivateAttr(default_factory=list)
    _stderr_task: asyncio.Task[None] | None = PrivateAttr(default=None)
    _thread_id: str | None = PrivateAttr(default=None)

    def attach(
        self,
        *,
        process: asyncio.subprocess.Process,
        peer: JsonRpcPeer,
        client: CodexAppServerClient,
        cwd: Path,
    ) -> None:
        self._process = process
        self._peer = peer
        self._client = client
        self._cwd = cwd
        self._stderr_task = asyncio.create_task(self._collect_stderr())

    @property
    def client(self) -> CodexAppServerClient:
        if self._client is None:
            raise RuntimeError("Codex client not attached.")
        return self._client

    @property
    def cwd(self) -> Path:
        if self._cwd is None:
            raise RuntimeError("Codex cwd not attached.")
        return self._cwd

    @property
    def thread_id(self) -> str | None:
        return self._thread_id

    @thread_id.setter
    def thread_id(self, value: str | None) -> None:
        self._thread_id = value

    def is_alive(self) -> bool:
        return self._process is not None and self._process.returncode is None

    async def close(self) -> None:
        if self._process is not None and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=2)
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()
        if self._client is not None:
            await self._client.close()
        if self._stderr_task is not None:
            self._stderr_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._stderr_task

    def stderr_text(self) -> str:
        return "\n".join(self._stderr_lines[-20:])

    async def _collect_stderr(self) -> None:
        if self._process is None or self._process.stderr is None:
            return
        while True:
            line = await self._process.stderr.readline()
            if not line:
                return
            self._stderr_lines.append(line.decode("utf-8", errors="replace").rstrip())
