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
    parser.add_argument(
        "--enabled-executor",
        action="append",
        choices=["codex", "acpx"],
        help="Override the enabled executor families for this run. Repeat for multiple values.",
    )
    parser.add_argument(
        "--acpx-agent",
        help="Override the ACPX agent for this run, for example codex or openclaw.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    loaded = load_executor_node_config()
    effective_enabled_executors = list(args.enabled_executor or loaded.node_settings.enabled_executors)
    if not effective_enabled_executors:
        raise SystemExit("executor node has no local executors configured in ~/.newbro/config.yaml")
    effective_executors = dict(loaded.executors)
    if args.acpx_agent:
        acpx_config = dict(effective_executors.get("acpx") or {})
        acpx_config["agent"] = args.acpx_agent
        effective_executors["acpx"] = acpx_config
    settings = replace(
        loaded.node_settings,
        synapse_base_url=args.base_url,
        node_id=args.node_id,
        token=args.token,
        enabled_executors=effective_enabled_executors,
    )
    service = ExecutorNodeService(
        settings=settings,
        executors_config=effective_executors,
    )
    try:
        asyncio.run(service.run_forever())
    except KeyboardInterrupt:
        print("[stop] executor node interrupted")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
