from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, AsyncIterator, Protocol
from urllib.parse import urlparse, urlunparse

import httpx
import websockets


class SynopseBridgeError(RuntimeError):
    pass


@dataclass(slots=True)
class SynopseMessageResult:
    reply_text: str


class SynopseBridgeClient(Protocol):
    async def create_session(self) -> str:
        ...

    async def send_message(self, session_id: str, text: str) -> SynopseMessageResult:
        ...

    def stream_message(
        self,
        session_id: str,
        text: str,
        *,
        request_id: str,
    ) -> AsyncIterator[dict[str, Any]]:
        ...

    def watch_notification_texts(self, session_id: str) -> AsyncIterator[str]:
        ...

    async def close(self) -> None:
        ...


class ExternalSynopseClient:
    def __init__(
        self,
        base_url: str,
        *,
        request_timeout_seconds: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._request_timeout_seconds = request_timeout_seconds
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=request_timeout_seconds,
        )

    async def create_session(self) -> str:
        response = await self._request("POST", "/sessions")
        payload = response.json()
        session_id = payload.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise SynopseBridgeError("Synopse session creation returned no session_id.")
        return session_id

    async def send_message(self, session_id: str, text: str) -> SynopseMessageResult:
        response = await self._request(
            "POST",
            f"/sessions/{session_id}/messages",
            json={"text": text},
        )
        payload = response.json()
        reply_text = payload.get("reply_text")
        if not isinstance(reply_text, str):
            raise SynopseBridgeError("Synopse message response returned no reply_text.")
        return SynopseMessageResult(reply_text=reply_text)

    async def stream_message(
        self,
        session_id: str,
        text: str,
        *,
        request_id: str,
    ) -> AsyncIterator[dict[str, Any]]:
        ws_url = self._session_stream_url(session_id)
        try:
            async with websockets.connect(
                ws_url,
                open_timeout=self._request_timeout_seconds,
                close_timeout=self._request_timeout_seconds,
            ) as websocket:
                await self._recv_json(websocket, timeout=self._request_timeout_seconds)
                await websocket.send(
                    json.dumps(
                        {
                            "type": "send_message",
                            "request_id": request_id,
                            "text": text,
                        }
                    )
                )
                while True:
                    event = await self._recv_json(
                        websocket,
                        timeout=self._request_timeout_seconds,
                    )
                    event_type = event.get("type")
                    if event_type == "action_rejected" and event.get("request_id") == request_id:
                        raise SynopseBridgeError(str(event.get("message") or "Synopse rejected the message action."))
                    if event_type not in {
                        "assistant_response_started",
                        "assistant_response_delta",
                        "assistant_response_completed",
                        "assistant_response_failed",
                    }:
                        continue
                    if event.get("request_id") != request_id:
                        continue
                    yield event
                    if event_type in {"assistant_response_completed", "assistant_response_failed"}:
                        break
        except SynopseBridgeError:
            raise
        except Exception as exc:
            raise SynopseBridgeError(
                f"Failed to stream message from Synopse session '{session_id}'."
            ) from exc

    async def watch_notification_texts(self, session_id: str) -> AsyncIterator[str]:
        ws_url = self._session_stream_url(session_id)
        try:
            async with websockets.connect(
                ws_url,
                open_timeout=self._request_timeout_seconds,
                close_timeout=self._request_timeout_seconds,
            ) as websocket:
                await self._recv_json(websocket, timeout=self._request_timeout_seconds)
                while True:
                    event = await self._recv_json(websocket, timeout=None)
                    if event.get("type") != "conversation_appended":
                        continue
                    if event.get("source") != "notification":
                        continue
                    text = event.get("text")
                    if isinstance(text, str) and text.strip():
                        yield text.strip()
        except asyncio.CancelledError:
            raise
        except Exception:
            return

    async def close(self) -> None:
        await self._http.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        try:
            response = await self._http.request(method, path, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip() or exc.response.reason_phrase
            raise SynopseBridgeError(
                f"Synopse API request failed for {method} {path}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise SynopseBridgeError(
                f"Failed to reach Synopse API for {method} {path}."
            ) from exc

    async def _recv_json(
        self,
        websocket: Any,
        *,
        timeout: float | None,
    ) -> dict[str, Any]:
        raw = await asyncio.wait_for(websocket.recv(), timeout=timeout)
        if not isinstance(raw, str):
            raise SynopseBridgeError("Synopse websocket returned a non-text payload.")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise SynopseBridgeError("Synopse websocket returned a non-object payload.")
        return payload

    def _session_stream_url(self, session_id: str) -> str:
        parsed = urlparse(self._base_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        path = parsed.path.rstrip("/") + f"/sessions/{session_id}/stream"
        return urlunparse((scheme, parsed.netloc, path, "", "", ""))
