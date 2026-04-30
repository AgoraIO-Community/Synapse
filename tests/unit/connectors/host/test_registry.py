from __future__ import annotations

from newbro.connectors.host.registry import create_connector_module_registry


class _FakeModule:
    slug = "fake"


class _FakeSpec:
    def __init__(self, *, slug: str, load_counter: list[str], init_counter: list[str]) -> None:
        self.slug = slug
        self._load_counter = load_counter
        self._init_counter = init_counter

    def load_module_class(self):
        self._load_counter.append(self.slug)
        init_counter = self._init_counter
        slug = self.slug

        class _LoadedModule(_FakeModule):
            def __init__(self) -> None:
                init_counter.append(slug)

        _LoadedModule.slug = slug
        return _LoadedModule


def test_create_connector_module_registry_loads_modules_lazily(monkeypatch):
    loaded: list[str] = []
    initialized: list[str] = []
    spec = _FakeSpec(slug="fake", load_counter=loaded, init_counter=initialized)

    monkeypatch.setattr(
        "newbro.connectors.host.registry.list_connector_module_specs",
        lambda: [spec],
    )

    registry = create_connector_module_registry()

    assert loaded == []
    assert initialized == []

    module = registry.get("fake")

    assert module is not None
    assert loaded == ["fake"]
    assert initialized == ["fake"]
    assert registry.get("fake") is module
    assert loaded == ["fake"]
    assert initialized == ["fake"]


def test_create_connector_module_registry_filters_out_unrequested_modules(monkeypatch):
    loaded: list[str] = []
    initialized: list[str] = []
    fake_specs = [
        _FakeSpec(slug="enabled", load_counter=loaded, init_counter=initialized),
        _FakeSpec(slug="disabled", load_counter=loaded, init_counter=initialized),
    ]

    monkeypatch.setattr(
        "newbro.connectors.host.registry.list_connector_module_specs",
        lambda: fake_specs,
    )

    registry = create_connector_module_registry(["enabled"])

    assert registry.get("disabled") is None
    assert loaded == []
    assert initialized == []

    assert registry.get("enabled") is not None
    assert loaded == ["enabled"]
    assert initialized == ["enabled"]
