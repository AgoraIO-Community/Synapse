from __future__ import annotations

from dataclasses import dataclass

from .bridge import BridgeRegistry, DuplicateBindingError, MissingRegistrationConfigError
from .convoai_service import (
    ActivatedConvoAISession,
    ConvoAIConfigurationError,
    ConvoAIRuntimeError,
    ConvoAIService,
    PreparedConvoAISession,
)
from .models import (
    FrontendConfigResponse,
    FrontendPrepareAgentModel,
    FrontendSessionActivateRequest,
    FrontendSessionActivateResponse,
    FrontendSessionPrepareRequest,
    FrontendSessionPrepareResponse,
    FrontendSessionStopRequest,
    FrontendSessionStopResponse,
)
from .settings import AgoraBridgeSettings


@dataclass(slots=True)
class FrontendSessionHandle:
    bridge_session_id: str
    synopse_session_id: str
    runtime_agent_id: str
    channel_name: str
    profile: str | None


class FrontendSessionService:
    def __init__(
        self,
        bridge_registry: BridgeRegistry,
        settings: AgoraBridgeSettings,
        *,
        convoai_service: ConvoAIService,
    ) -> None:
        self._bridge_registry = bridge_registry
        self._settings = settings
        self._convoai_service = convoai_service
        self._sessions: dict[str, FrontendSessionHandle] = {}

    def get_config(self) -> FrontendConfigResponse:
        missing: list[str] = []
        if not self._settings.default_app_id:
            missing.append("AGORA_APP_ID")
        if not self._settings.app_certificate:
            missing.append("AGORA_APP_CERTIFICATE")
        if not self._settings.openai_api_key:
            missing.append("OPENAI_API_KEY")
        if not self._settings.deepgram_api_key:
            missing.append("DEEPGRAM_API_KEY")
        if not self._settings.elevenlabs_api_key:
            missing.append("ELEVENLABS_API_KEY")
        if not self._settings.elevenlabs_voice_id:
            missing.append("ELEVENLABS_VOICE_ID")

        return FrontendConfigResponse(
            ready=not missing,
            service_base_url=self._settings.service_base_url.rstrip("/"),
            defaults={
                "profile": self._settings.frontend_default_profile,
                "channel_name": self._settings.frontend_default_channel_name,
                "display_name": self._settings.frontend_default_display_name,
            },
            missing_requirements=missing,
        )

    async def prepare_session(
        self,
        request_payload: FrontendSessionPrepareRequest,
    ) -> FrontendSessionPrepareResponse:
        profile = request_payload.profile or self._settings.frontend_default_profile
        channel_name = (
            request_payload.channel_name or self._settings.frontend_default_channel_name
        )
        display_name = (
            request_payload.display_name or self._settings.frontend_default_display_name
        )
        prepared = await self._convoai_service.prepare_session(
            profile=profile,
            channel_name=channel_name,
            display_name=display_name,
            user_id=request_payload.user_id,
        )
        return self._build_prepare_response(prepared)

    async def activate_session(
        self,
        request_payload: FrontendSessionActivateRequest,
    ) -> FrontendSessionActivateResponse:
        activated = await self._convoai_service.activate_session(request_payload.prepared_session_id)
        try:
            binding = await self._bridge_registry.register(
                agent_id=activated.runtime_agent_id,
                channel_name=activated.channel_name,
                runtime_agent_id=activated.runtime_agent_id,
            )
        except (DuplicateBindingError, MissingRegistrationConfigError, KeyError):
            try:
                await self._convoai_service.stop_session(activated.runtime_agent_id)
            except Exception:
                pass
            raise

        self._sessions[binding.bridge_session_id] = FrontendSessionHandle(
            bridge_session_id=binding.bridge_session_id,
            synopse_session_id=binding.synopse_session_id,
            runtime_agent_id=activated.runtime_agent_id,
            channel_name=activated.channel_name,
            profile=activated.profile,
        )
        return self._build_activate_response(
            binding.bridge_session_id,
            binding.synopse_session_id,
            activated,
        )

    async def stop_session(
        self,
        request_payload: FrontendSessionStopRequest,
    ) -> FrontendSessionStopResponse:
        handle = self._sessions.pop(request_payload.bridge_session_id, None)
        if handle is None:
            raise KeyError("Unknown bridge session.")

        runtime_error: ConvoAIRuntimeError | None = None
        try:
            await self._convoai_service.stop_session(handle.runtime_agent_id)
        except KeyError:
            pass
        except ConvoAIRuntimeError as exc:
            runtime_error = exc

        await self._bridge_registry.unregister(request_payload.bridge_session_id)
        if runtime_error is not None:
            raise runtime_error
        return FrontendSessionStopResponse()

    def _build_prepare_response(
        self,
        prepared: PreparedConvoAISession,
    ) -> FrontendSessionPrepareResponse:
        return FrontendSessionPrepareResponse(
            prepared_session_id=prepared.prepared_session_id,
            app_id=prepared.app_id,
            channel_name=prepared.channel_name,
            token=prepared.token,
            uid=prepared.uid,
            user_rtm_uid=prepared.user_rtm_uid,
            agent=FrontendPrepareAgentModel(uid=prepared.agent_uid),
            agent_rtm_uid=prepared.agent_rtm_uid,
            enable_string_uid=prepared.enable_string_uid,
            profile=prepared.profile,
            display_name=prepared.display_name,
            diagnostics=prepared.diagnostics,
        )

    def _build_activate_response(
        self,
        bridge_session_id: str,
        synopse_session_id: str,
        activated: ActivatedConvoAISession,
    ) -> FrontendSessionActivateResponse:
        return FrontendSessionActivateResponse(
            prepared_session_id=activated.prepared_session_id,
            bridge_session_id=bridge_session_id,
            synopse_session_id=synopse_session_id,
            runtime_agent_id=activated.runtime_agent_id,
            chat_completions_url=(
                f"{self._settings.service_base_url.rstrip('/')}"
                f"/chat/completions?bridge_session_id={bridge_session_id}"
            ),
            app_id=activated.app_id,
            channel_name=activated.channel_name,
            token=activated.token,
            uid=activated.uid,
            user_rtm_uid=activated.user_rtm_uid,
            agent=FrontendPrepareAgentModel(uid=activated.agent_uid),
            agent_rtm_uid=activated.agent_rtm_uid,
            enable_string_uid=activated.enable_string_uid,
            profile=activated.profile,
            display_name=activated.display_name,
            diagnostics=activated.diagnostics,
        )


__all__ = [
    "FrontendSessionService",
    "ConvoAIConfigurationError",
    "ConvoAIRuntimeError",
]
