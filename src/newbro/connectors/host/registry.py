from __future__ import annotations

from collections.abc import Callable, Iterable

from newbro.connectors.base import BaseConnectorModule, ConnectorModuleRegistry

from .catalog import list_connector_module_specs


def create_connector_module_registry(enabled_modules: Iterable[str] | None = None) -> ConnectorModuleRegistry:
    requested_slugs = set(enabled_modules) if enabled_modules is not None else None
    factories: dict[str, Callable[[], BaseConnectorModule]] = {}
    for spec in list_connector_module_specs():
        if requested_slugs is not None and spec.slug not in requested_slugs:
            continue
        factories[spec.slug] = lambda spec=spec: spec.load_module_class()()
    return ConnectorModuleRegistry(factories=factories)


def list_registered_connector_modules() -> list[BaseConnectorModule]:
    return create_connector_module_registry().list()
