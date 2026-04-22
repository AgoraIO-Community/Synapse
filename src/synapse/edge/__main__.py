from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from .app import DEFAULT_FRONTEND_DIST_DIR, EdgeSettings, create_app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m synapse.edge", description="Run the Synapse edge transport.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--backend-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--gateway-base-url")
    parser.add_argument("--frontend-dist", default=str(DEFAULT_FRONTEND_DIST_DIR))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    app = create_app(
        settings=EdgeSettings(
            backend_base_url=args.backend_base_url,
            gateway_base_url=args.gateway_base_url,
            frontend_dist=Path(args.frontend_dist),
        )
    )
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
