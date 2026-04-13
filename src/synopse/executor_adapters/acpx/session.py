from __future__ import annotations

from pathlib import Path

from pydantic import PrivateAttr

from synopse.executor_core import ExecutorSession


class AcpxExecutorSession(ExecutorSession):
    _cwd: Path | None = PrivateAttr(default=None)
    _session_name: str | None = PrivateAttr(default=None)
    _agent: str | None = PrivateAttr(default=None)
    _acpx_record_id: str | None = PrivateAttr(default=None)
    _acp_session_id: str | None = PrivateAttr(default=None)
    _agent_session_id: str | None = PrivateAttr(default=None)

    def attach(
        self,
        *,
        cwd: Path,
        session_name: str,
        agent: str,
    ) -> None:
        self._cwd = cwd
        self._session_name = session_name
        self._agent = agent
        self.session_id = session_name
        self.metadata.update(
            {
                "cwd": str(cwd),
                "session_name": session_name,
                "agent": agent,
            }
        )

    @property
    def cwd(self) -> Path:
        if self._cwd is None:
            raise RuntimeError("ACPX cwd not attached.")
        return self._cwd

    @property
    def session_name(self) -> str:
        if self._session_name is None:
            raise RuntimeError("ACPX session name not attached.")
        return self._session_name

    @session_name.setter
    def session_name(self, value: str) -> None:
        self._session_name = value
        self.session_id = value
        self.metadata["session_name"] = value

    @property
    def agent(self) -> str:
        if self._agent is None:
            raise RuntimeError("ACPX agent not attached.")
        return self._agent

    @agent.setter
    def agent(self, value: str) -> None:
        self._agent = value
        self.metadata["agent"] = value

    @property
    def acpx_record_id(self) -> str | None:
        return self._acpx_record_id

    @property
    def acp_session_id(self) -> str | None:
        return self._acp_session_id

    @property
    def agent_session_id(self) -> str | None:
        return self._agent_session_id

    def update_identity(
        self,
        *,
        acpx_record_id: str | None = None,
        acp_session_id: str | None = None,
        agent_session_id: str | None = None,
    ) -> None:
        if acpx_record_id is not None:
            self._acpx_record_id = acpx_record_id
            self.metadata["acpx_record_id"] = acpx_record_id
        if acp_session_id is not None:
            self._acp_session_id = acp_session_id
            self.metadata["acp_session_id"] = acp_session_id
        if agent_session_id is not None:
            self._agent_session_id = agent_session_id
            self.metadata["agent_session_id"] = agent_session_id

    def hydrate_resume_handle(
        self,
        *,
        cwd: str | None = None,
        session_name: str | None = None,
        agent: str | None = None,
        acpx_record_id: str | None = None,
        acp_session_id: str | None = None,
        agent_session_id: str | None = None,
    ) -> None:
        if cwd:
            resolved = Path(cwd).resolve()
            self._cwd = resolved
            self.metadata["cwd"] = str(resolved)
        if session_name:
            self.session_name = session_name
        if agent:
            self.agent = agent
        self.update_identity(
            acpx_record_id=acpx_record_id,
            acp_session_id=acp_session_id,
            agent_session_id=agent_session_id,
        )
