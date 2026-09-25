"""Command-line interface for validating analysis configurations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from wiki_trends.config import complete_month_range, load_config

__all__ = ["build_parser", "main"]


def build_parser() -> argparse.ArgumentParser:
    """Create the M02 CLI parser."""
    parser = argparse.ArgumentParser(description="Validate a Wikipedia pageview trend analysis configuration.")
    parser.add_argument(
        "--config",
        metavar="FILE",
        help="Path to an analysis configuration JSON file.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Validate a config and print a machine-readable M02 placeholder result."""
    args = build_parser().parse_args(argv)
    if args.config is None:
        build_parser().error("--config is required")

    try:
        config = load_config(args.config)
    except (OSError, ValueError, ValidationError) as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2

    start_month, end_month = complete_month_range(config.period.months)
    result = {
        "schema_version": "1.0",
        "status": "validated",
        "config_path": str(Path(args.config)),
        "query": config.query.model_dump(mode="json"),
        "languages": config.languages,
        "period": {
            **config.period.model_dump(mode="json"),
            "start_month": start_month.isoformat(),
            "end_month": end_month.isoformat(),
        },
        "message": "Configuration is valid. Data collection is not implemented in M02.",
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0
