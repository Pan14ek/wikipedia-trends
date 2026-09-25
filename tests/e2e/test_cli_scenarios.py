"""Deterministic CLI scenarios for M17's three product configurations."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wiki_trends import cli


@pytest.mark.parametrize(
    ("name", "query", "languages"),
    [
        ("astronomy", {"mode": "article", "value": "Astronomy", "source_language": "uk"}, ["uk"]),
        ("fasting", {"mode": "article", "value": "Intermittent fasting", "source_language": "pl"}, ["pl", "cs"]),
        ("learning-english", {"mode": "topic", "value": "Learning English"}, ["pl", "cs", "uk"]),
    ],
)
def test_cli_invokes_the_shared_analysis_pipeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    query: dict[str, str],
    languages: list[str],
) -> None:
    """Ensure every canonical config reaches the one shared CLI execution seam."""
    config_path = tmp_path / f"{name}.json"
    config_path.write_text(json.dumps({"query": query, "languages": languages}), encoding="utf-8")
    expected_paths = (tmp_path / "analysis.json", tmp_path / "trend.png", tmp_path / "report.pdf")
    received_languages: list[list[str]] = []

    def run_stub(config: object, output_root: Path) -> tuple[Path, Path, Path]:
        received_languages.append(config.languages)  # type: ignore[attr-defined]
        assert output_root == tmp_path / "output"
        return expected_paths

    monkeypatch.setattr(cli, "run_analysis", run_stub)

    assert cli.main(["--config", str(config_path), "--output-dir", str(tmp_path / "output")]) == 0
    assert received_languages == [languages]
