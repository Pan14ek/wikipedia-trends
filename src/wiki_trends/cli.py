"""Command-line interface for complete Wikipedia Trends analyses."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from wiki_trends.config import load_config
from wiki_trends.pipeline import run_analysis

__all__ = ["build_parser", "main"]

CLI_SCHEMA_VERSION = "1.0.0"


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Generate Wikipedia Trends analysis artifacts from a JSON configuration."
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        required=True,
        help="Path to an analysis configuration JSON file.",
    )
    parser.add_argument("--output-dir", default="output", help="Directory for generated analysis artifacts.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one validated configuration and print its machine-readable result."""
    args = build_parser().parse_args(argv)

    try:
        config = load_config(args.config)
    except (OSError, ValueError, ValidationError) as error:
        _write_error("configuration_error", error)
        return 2

    try:
        result = run_analysis(config, Path(args.output_dir))
    except Exception as error:
        _write_error("analysis_error", error)
        return 1
    print(
        json.dumps(
            {
                "cli_schema_version": CLI_SCHEMA_VERSION,
                "status": "success",
                "analysis_json": str(result.analysis_json) if result.analysis_json is not None else None,
                "charts": [str(path) for path in result.charts],
                "pdf": str(result.pdf) if result.pdf is not None else None,
            },
            ensure_ascii=False,
        )
    )
    return 0


def _write_error(error_type: str, error: Exception) -> None:
    """Write a structured application failure to stderr without a traceback."""
    print(
        json.dumps(
            {
                "cli_schema_version": CLI_SCHEMA_VERSION,
                "status": "error",
                "error_type": error_type,
                "message": str(error),
            },
            ensure_ascii=False,
        ),
        file=sys.stderr,
    )
