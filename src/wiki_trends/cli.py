"""Command-line interface scaffolding for the Wikipedia Trends skill."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    """Create the M01 CLI parser without implementing analysis behavior."""
    parser = argparse.ArgumentParser(
        description="Analyze Wikipedia pageview trends (project skeleton)."
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        help="Path to an analysis configuration file (not implemented in M01).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI parser and stop before unimplemented analysis work."""
    build_parser().parse_args(argv)
    return 0
