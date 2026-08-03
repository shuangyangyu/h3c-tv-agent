"""CLI entrypoints."""

from __future__ import annotations

import argparse
import sys

from .config import Settings
from .logging_setup import setup_logging
from .service import AgentService, run_status_once


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="h3c-tv-agent")
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=["run", "status"],
        help="run: MQTT agent; status: one-shot ACL poll",
    )
    args = parser.parse_args(argv)
    settings = Settings()
    setup_logging(settings.log_level)

    if not settings.h3c_password:
        print("H3C_PASSWORD is required", file=sys.stderr)
        return 2

    if args.command == "status":
        return run_status_once(settings)

    if not settings.mqtt_host:
        print("MQTT_HOST is required for run", file=sys.stderr)
        return 2

    AgentService(settings).run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
