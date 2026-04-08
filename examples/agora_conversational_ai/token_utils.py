from __future__ import annotations

import base64
import secrets
import struct
import time
import zlib
from collections import OrderedDict
from dataclasses import dataclass
from hashlib import sha256
import hmac


def _pack_uint16(x: int) -> bytes:
    return struct.pack("<H", int(x))


def _pack_uint32(x: int) -> bytes:
    return struct.pack("<I", int(x))


def _pack_string(value: str | bytes) -> bytes:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return _pack_uint16(len(value)) + value


def _pack_map_uint32(values: dict[int, int]) -> bytes:
    return _pack_uint16(len(values)) + b"".join(
        [_pack_uint16(k) + _pack_uint32(v) for k, v in values.items()]
    )


class _Service:
    def __init__(self, service_type: int) -> None:
        self._type = service_type
        self._privileges: dict[int, int] = {}

    def add_privilege(self, privilege: int, expire: int) -> None:
        self._privileges[privilege] = expire

    def _pack_type(self) -> bytes:
        return _pack_uint16(self._type)

    def _pack_privileges(self) -> bytes:
        ordered = OrderedDict(sorted(self._privileges.items(), key=lambda item: int(item[0])))
        return _pack_map_uint32(ordered)

    def pack(self) -> bytes:
        return self._pack_type() + self._pack_privileges()


class _ServiceRtc(_Service):
    SERVICE_TYPE = 1
    PRIVILEGE_JOIN_CHANNEL = 1
    PRIVILEGE_PUBLISH_AUDIO_STREAM = 2
    PRIVILEGE_PUBLISH_VIDEO_STREAM = 3
    PRIVILEGE_PUBLISH_DATA_STREAM = 4

    def __init__(self, channel_name: str, uid: str | int = 0) -> None:
        super().__init__(self.SERVICE_TYPE)
        self._channel_name = channel_name.encode("utf-8")
        self._uid = b"" if uid == 0 else str(uid).encode("utf-8")

    def pack(self) -> bytes:
        return super().pack() + _pack_string(self._channel_name) + _pack_string(self._uid)


class _ServiceRtm(_Service):
    SERVICE_TYPE = 2
    PRIVILEGE_LOGIN = 1

    def __init__(self, user_id: str) -> None:
        super().__init__(self.SERVICE_TYPE)
        self._user_id = user_id.encode("utf-8")

    def pack(self) -> bytes:
        return super().pack() + _pack_string(self._user_id)


class _AccessToken:
    VERSION = "007"

    def __init__(self, app_id: str, app_certificate: str, *, expire: int = 900) -> None:
        self._app_id = app_id
        self._app_certificate = app_certificate
        self._issue_ts = int(time.time())
        self._expire = expire
        self._salt = secrets.SystemRandom().randint(1, 99999999)
        self._services: dict[int, _Service] = {}

    def add_service(self, service: _Service) -> None:
        self._services[service._type] = service

    def _signing(self) -> bytes:
        signing = hmac.new(_pack_uint32(self._issue_ts), self._app_certificate.encode("utf-8"), sha256).digest()
        signing = hmac.new(_pack_uint32(self._salt), signing, sha256).digest()
        return signing

    def build(self) -> str:
        app_id = self._app_id.encode("utf-8")
        signing = self._signing()
        signing_info = (
            _pack_string(app_id)
            + _pack_uint32(self._issue_ts)
            + _pack_uint32(self._expire)
            + _pack_uint32(self._salt)
            + _pack_uint16(len(self._services))
        )
        for service in self._services.values():
            signing_info += service.pack()
        signature = hmac.new(signing, signing_info, sha256).digest()
        payload = zlib.compress(_pack_string(signature) + signing_info)
        return self.VERSION + base64.b64encode(payload).decode("utf-8")


@dataclass(slots=True)
class CombinedTokenResult:
    token: str
    rtc_uid: int
    rtm_uid: str


def build_token_with_rtm(
    *,
    channel_name: str,
    rtc_uid: int,
    app_id: str,
    app_certificate: str,
    rtm_uid: str,
    token_expire: int,
    privilege_expire: int | None = None,
) -> CombinedTokenResult:
    token = _AccessToken(app_id, app_certificate, expire=token_expire)
    privilege_expire = privilege_expire if privilege_expire is not None else token_expire

    rtc_service = _ServiceRtc(channel_name, rtc_uid)
    rtc_service.add_privilege(_ServiceRtc.PRIVILEGE_JOIN_CHANNEL, privilege_expire)
    rtc_service.add_privilege(_ServiceRtc.PRIVILEGE_PUBLISH_AUDIO_STREAM, privilege_expire)
    rtc_service.add_privilege(_ServiceRtc.PRIVILEGE_PUBLISH_VIDEO_STREAM, privilege_expire)
    rtc_service.add_privilege(_ServiceRtc.PRIVILEGE_PUBLISH_DATA_STREAM, privilege_expire)
    token.add_service(rtc_service)

    rtm_service = _ServiceRtm(rtm_uid)
    rtm_service.add_privilege(_ServiceRtm.PRIVILEGE_LOGIN, token_expire)
    token.add_service(rtm_service)

    return CombinedTokenResult(token=token.build(), rtc_uid=rtc_uid, rtm_uid=rtm_uid)
