from __future__ import annotations

from collections.abc import Callable, Iterable

from synapse.gateways.base import BaseGatewayModule, GatewayModuleRegistry

from .catalog import list_gateway_module_specs


def create_gateway_module_registry(enabled_modules: Iterable[str] | None = None) -> GatewayModuleRegistry:
    requested_slugs = set(enabled_modules) if enabled_modules is not None else None
    factories: dict[str, Callable[[], BaseGatewayModule]] = {}
    for spec in list_gateway_module_specs():
        if requested_slugs is not None and spec.slug not in requested_slugs:
            continue
        factories[spec.slug] = lambda spec=spec: spec.load_module_class()()
    return GatewayModuleRegistry(factories=factories)


def list_registered_gateway_modules() -> list[BaseGatewayModule]:
    return create_gateway_module_registry().list()
