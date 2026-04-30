from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import APIRouter


class BaseConnectorModule(ABC):
    slug: str

    @abstractmethod
    def build_router(self) -> "APIRouter":
        raise NotImplementedError


class ConnectorModuleRegistry:
    def __init__(
        self,
        modules: Iterable[BaseConnectorModule] = (),
        *,
        factories: Mapping[str, Callable[[], BaseConnectorModule]] | None = None,
    ) -> None:
        self._modules = {module.slug: module for module in modules}
        self._factories = dict(factories or {})

    def get(self, slug: str) -> BaseConnectorModule | None:
        module = self._modules.get(slug)
        if module is not None:
            return module

        factory = self._factories.get(slug)
        if factory is None:
            return None

        module = factory()
        self._modules[slug] = module
        return module

    def list(self) -> list[BaseConnectorModule]:
        modules: list[BaseConnectorModule] = []
        for slug in sorted({*self._factories, *self._modules}):
            module = self.get(slug)
            if module is not None:
                modules.append(module)
        return modules
