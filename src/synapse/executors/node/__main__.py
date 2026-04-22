from __future__ import annotations

import asyncio

from .config import load_executor_node_config
from .service import ExecutorNodeService


def main() -> int:
    loaded = load_executor_node_config()
    if not loaded.node_settings.enabled:
        raise SystemExit("executor node is disabled in ~/.synapse/config.yaml")
    service = ExecutorNodeService(
        settings=loaded.node_settings,
        executors_config=loaded.executors,
    )
    try:
        asyncio.run(service.run_forever())
    except KeyboardInterrupt:
        print("[stop] executor node interrupted")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
