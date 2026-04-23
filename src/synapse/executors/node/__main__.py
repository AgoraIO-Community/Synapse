from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace

from .config import load_executor_node_config
from .service import ExecutorNodeService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m synapse.executors.node")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--token", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    loaded = load_executor_node_config()
    if not loaded.node_settings.enabled_executors:
        raise SystemExit("executor node has no local executors configured in ~/.newbro/config.yaml")
    settings = replace(
        loaded.node_settings,
        synapse_base_url=args.base_url,
        node_id=args.node_id,
        token=args.token,
    )
    service = ExecutorNodeService(
        settings=settings,
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
