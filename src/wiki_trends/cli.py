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


def build_parser() -> argparse.ArgumentParser:
    """Create the M17 CLI parser."""
    parser = argparse.ArgumentParser(
        description="Generate Wikipedia Trends analysis artifacts from a JSON configuration."
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        help="Path to an analysis configuration JSON file.",
    )
    parser.add_argument("--output-dir", default="output", help="Directory for generated analysis artifacts.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one validated configuration through the M17 artifact pipeline."""
    args = build_parser().parse_args(argv)
    if args.config is None:
        build_parser().error("--config is required")

    try:
        config = load_config(args.config)
    except (OSError, ValueError, ValidationError) as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2

    try:
        json_path, chart_path, pdf_path = run_analysis(config, Path(args.output_dir))
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Analysis error: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {"analysis_json": str(json_path), "chart": str(chart_path), "pdf": str(pdf_path)}, ensure_ascii=False
        )
    )
    return 0
