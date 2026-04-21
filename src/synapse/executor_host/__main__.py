from __future__ import annotations

import asyncio

from .config import load_executor_host_config
from .service import ExecutorHostService


def main() -> int:
    loaded = load_executor_host_config()
    if not loaded.host_settings.enabled:
        raise SystemExit("executor host is disabled in ~/.synapse/config.yaml")
    service = ExecutorHostService(
        settings=loaded.host_settings,
        executors_config=loaded.executors,
    )
    asyncio.run(service.run_forever())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
