from __future__ import annotations

from dataclasses import dataclass

from synapse.gateways.base import DuplicateBindingError, GatewayBindingRegistry, MissingRegistrationConfigError

from .models import (
    GatewayConfigResponse,
    GatewaySessionDefaults,
    GatewayPrepareAgentModel,
    GatewaySessionActivateRequest,
    GatewaySessionActivateResponse,
    GatewaySessionPrepareRequest,
    GatewaySessionPrepareResponse,
    GatewaySessionStopRequest,
    GatewaySessionStopResponse,
)
from .service import (
    ActivatedConvoAISession,
    ConvoAIRuntimeError,
    ConvoAIService,
    PreparedConvoAISession,
)
from .settings import AgoraConvoAIGatewaySettings


@dataclass(slots=True)
class GatewaySessionHandle:
    binding_id: str
    synapse_session_id: str
    runtime_session_id: str
    channel_name: str
    profile: str | None


class AgoraGatewaySessionService:
    def __init__(
        self,
        binding_registry: GatewayBindingRegistry,
        settings: AgoraConvoAIGatewaySettings,
        *,
        convoai_service: ConvoAIService,
    ) -> None:
        self._binding_registry = binding_registry
        self._settings = settings
        self._convoai_service = convoai_service
        self._sessions: dict[str, GatewaySessionHandle] = {}

    def get_config(self) -> GatewayConfigResponse:
        missing: list[str] = []
        if not self._settings.app_id:
            missing.append(
                "gateways.agora-convoai.app_id"
                if self._settings.uses_yaml_config
                else "SYNAPSE_GATEWAY_AGORA_CONVOAI_APP_ID"
            )
        if not self._settings.synapse_base_url:
            missing.append("SYNAPSE_GATEWAY_SYNAPSE_BASE_URL")
        if not self._settings.app_certificate:
            missing.append(
                "gateways.agora-convoai.app_certificate"
                if self._settings.uses_yaml_config
                else "SYNAPSE_GATEWAY_AGORA_CONVOAI_APP_CERTIFICATE"
            )
        if self._settings.asr.credential_mode == "byok" and not self._settings.asr.api_key:
            missing.append(
                "gateways.agora-convoai.asr.api_key"
                if self._settings.uses_yaml_config
                else "SYNAPSE_GATEWAY_AGORA_CONVOAI_DEEPGRAM_API_KEY"
            )
        if self._settings.tts.credential_mode == "byok" and not self._settings.tts.api_key:
            missing.append(
                "gateways.agora-convoai.tts.api_key"
                if self._settings.uses_yaml_config
                else "SYNAPSE_GATEWAY_AGORA_CONVOAI_ELEVENLABS_API_KEY"
            )
        if self._settings.tts.credential_mode == "byok" and not self._settings.tts.voice:
            missing.append(
                "gateways.agora-convoai.tts.voice"
                if self._settings.uses_yaml_config
                else "SYNAPSE_GATEWAY_AGORA_CONVOAI_ELEVENLABS_VOICE_ID"
            )

        return GatewayConfigResponse(
            ready=not missing,
            service_base_url=self._settings.service_base_url.rstrip("/"),
            defaults=GatewaySessionDefaults(
                profile=self._settings.default_profile,
                channel_name=self._settings.default_channel_name,
                display_name=self._settings.default_display_name,
                agent_instructions=self._settings.agent_instructions,
                agent_greeting=self._settings.agent_greeting,
                agent_uid=self._settings.agent_uid,
                user_uid=self._settings.user_uid,
            ),
            missing_requirements=missing,
        )

    async def prepare_session(
        self,
        request_payload: GatewaySessionPrepareRequest,
    ) -> GatewaySessionPrepareResponse:
        profile = request_payload.profile or self._settings.default_profile
        channel_name = request_payload.channel_name or self._settings.default_channel_name
        display_name = request_payload.display_name or self._settings.default_display_name
        prepared = await self._convoai_service.prepare_session(
            profile=profile,
            channel_name=channel_name,
            display_name=display_name,
            agent_instructions=(
                request_payload.agent_instructions
                if request_payload.agent_instructions is not None
                else self._settings.agent_instructions
            ),
            agent_greeting=(
                request_payload.agent_greeting
                if request_payload.agent_greeting is not None
                else self._settings.agent_greeting
            ),
            agent_uid=(
                request_payload.agent_uid
                if request_payload.agent_uid is not None
                else self._settings.agent_uid
            ),
            user_uid=request_payload.user_uid,
        )
        return self._build_prepare_response(prepared)

    async def activate_session(
        self,
        request_payload: GatewaySessionActivateRequest,
    ) -> GatewaySessionActivateResponse:
        reserved = await self._binding_registry.reserve()
        chat_completions_url = self._build_chat_completions_url(reserved.binding_id)
        activated: ActivatedConvoAISession | None = None
        try:
            activated = await self._convoai_service.activate_session(
                request_payload.prepared_session_id,
                chat_completions_url=chat_completions_url,
            )
            binding = await self._binding_registry.finalize(
                reserved.binding_id,
                runtime_session_id=activated.runtime_session_id,
                metadata={"channel_name": activated.channel_name},
            )
        except (DuplicateBindingError, MissingRegistrationConfigError, KeyError):
            if activated is not None:
                try:
                    await self._convoai_service.stop_session(activated.runtime_session_id)
                except Exception:
                    pass
            await self._binding_registry.unregister(reserved.binding_id)
            raise
        except ConvoAIRuntimeError:
            await self._binding_registry.unregister(reserved.binding_id)
            raise
        except Exception:
            await self._binding_registry.unregister(reserved.binding_id)
            raise

        if binding.runtime_session_id != activated.runtime_session_id:
            try:
                await self._convoai_service.stop_session(activated.runtime_session_id)
            except Exception:
                pass
            await self._binding_registry.unregister(binding.binding_id)
            raise RuntimeError("Gateway binding did not finalize correctly.")

        self._sessions[binding.binding_id] = GatewaySessionHandle(
            binding_id=binding.binding_id,
            synapse_session_id=binding.synapse_session_id,
            runtime_session_id=activated.runtime_session_id,
            channel_name=activated.channel_name,
            profile=activated.profile,
        )
        return self._build_activate_response(
            binding.binding_id,
            binding.synapse_session_id,
            activated,
        )

    async def stop_session(
        self,
        request_payload: GatewaySessionStopRequest,
    ) -> GatewaySessionStopResponse:
        handle = self._sessions.pop(request_payload.binding_id, None)
        if handle is None:
            raise KeyError("Unknown gateway binding.")

        runtime_error: ConvoAIRuntimeError | None = None
        try:
            await self._convoai_service.stop_session(handle.runtime_session_id)
        except KeyError:
            pass
        except ConvoAIRuntimeError as exc:
            runtime_error = exc

        await self._binding_registry.unregister(request_payload.binding_id)
        if runtime_error is not None:
            raise runtime_error
        return GatewaySessionStopResponse()

    def _build_prepare_response(
        self,
        prepared: PreparedConvoAISession,
    ) -> GatewaySessionPrepareResponse:
        return GatewaySessionPrepareResponse(
            prepared_session_id=prepared.prepared_session_id,
            app_id=prepared.app_id,
            channel_name=prepared.channel_name,
            token=prepared.token,
            uid=prepared.uid,
            user_rtm_uid=prepared.user_rtm_uid,
            agent=GatewayPrepareAgentModel(uid=prepared.agent_uid),
            agent_rtm_uid=prepared.agent_rtm_uid,
            enable_string_uid=prepared.enable_string_uid,
            profile=prepared.profile,
            display_name=prepared.display_name,
            diagnostics=prepared.diagnostics,
        )

    def _build_activate_response(
        self,
        binding_id: str,
        synapse_session_id: str,
        activated: ActivatedConvoAISession,
    ) -> GatewaySessionActivateResponse:
        return GatewaySessionActivateResponse(
            prepared_session_id=activated.prepared_session_id,
            binding_id=binding_id,
            synapse_session_id=synapse_session_id,
            runtime_session_id=activated.runtime_session_id,
            chat_completions_url=self._build_chat_completions_url(binding_id),
            app_id=activated.app_id,
            channel_name=activated.channel_name,
            token=activated.token,
            uid=activated.uid,
            user_rtm_uid=activated.user_rtm_uid,
            agent=GatewayPrepareAgentModel(uid=activated.agent_uid),
            agent_rtm_uid=activated.agent_rtm_uid,
            enable_string_uid=activated.enable_string_uid,
            profile=activated.profile,
            display_name=activated.display_name,
            diagnostics=activated.diagnostics,
        )

    def _build_chat_completions_url(self, binding_id: str) -> str:
        return (
            f"{self._settings.service_base_url.rstrip('/')}"
            f"/gateway/agora-convoai/chat/completions?binding_id={binding_id}"
        )
