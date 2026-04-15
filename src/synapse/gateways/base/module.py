from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import APIRouter


class BaseGatewayModule(ABC):
    slug: str

    @abstractmethod
    def build_router(self) -> "APIRouter":
        raise NotImplementedError


class GatewayModuleRegistry:
    def __init__(
        self,
        modules: Iterable[BaseGatewayModule] = (),
        *,
        factories: Mapping[str, Callable[[], BaseGatewayModule]] | None = None,
    ) -> None:
        self._modules = {module.slug: module for module in modules}
        self._factories = dict(factories or {})

    def get(self, slug: str) -> BaseGatewayModule | None:
        module = self._modules.get(slug)
        if module is not None:
            return module

        factory = self._factories.get(slug)
        if factory is None:
            return None

        module = factory()
        self._modules[slug] = module
        return module

    def list(self) -> list[BaseGatewayModule]:
        modules: list[BaseGatewayModule] = []
        for slug in sorted({*self._factories, *self._modules}):
            module = self.get(slug)
            if module is not None:
                modules.append(module)
        return modules
