"""M02 coverage for the analysis configuration contract."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from wiki_trends.config import AnalysisConfig, complete_month_range
from wiki_trends.models import MonthlyPageview, ObservationStatus

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_minimal_valid_config_applies_defaults() -> None:
    config = AnalysisConfig.model_validate({"query": {"mode": "article", "value": " Astronomy "}, "languages": ["uk"]})

    assert config.query.value == "Astronomy"
    assert config.period.months == 24
    assert config.period.granularity.value == "monthly"
    assert config.criteria.model_dump() == {
        "growth": True,
        "normalized_interest": True,
        "stability": True,
        "anomalies": True,
        "confidence_intervals": True,
    }
    assert config.output.model_dump(by_alias=True) == {"json": True, "charts": True, "pdf": True}


def test_fully_specified_config_loads() -> None:
    config = AnalysisConfig.model_validate(
        {
            "query": {"mode": "topic", "value": "Space science"},
            "languages": ["uk", "en"],
            "period": {"months": 36, "granularity": "monthly"},
            "criteria": {
                "growth": False,
                "normalized_interest": False,
                "stability": False,
                "anomalies": False,
                "confidence_intervals": False,
            },
            "output": {"json": True, "charts": False, "pdf": False},
        }
    )

    assert config.query.mode.value == "topic"
    assert config.period.months == 36
    assert config.languages == ["uk", "en"]


def test_topic_article_overrides_are_typed_and_bounded() -> None:
    config = AnalysisConfig.model_validate(
        {
            "query": {
                "mode": "topic",
                "value": "learning English",
                "article_overrides": {"en": ["English language", "English grammar"]},
            },
            "languages": ["en"],
        }
    )

    assert config.query.article_overrides == {"en": ["English language", "English grammar"]}


@pytest.mark.parametrize(
    "payload, expected_message",
    [
        ({"query": {"mode": "person", "value": "Astronomy"}, "languages": ["uk"]}, "mode"),
        ({"query": {"mode": "article", "value": "   "}, "languages": ["uk"]}, "value"),
        ({"query": {"mode": "article", "value": "Astronomy"}, "languages": []}, "languages"),
        ({"query": {"mode": "article", "value": "Astronomy"}, "languages": ["uk", "uk"]}, "duplicate"),
        ({"query": {"mode": "article", "value": "Astronomy"}, "languages": ["UK"]}, "languages"),
        ({"query": {"mode": "article", "value": "Astronomy"}, "languages": ["uk"], "period": {"months": 11}}, "months"),
        (
            {"query": {"mode": "article", "value": "Astronomy"}, "languages": ["uk"], "period": {"months": 121}},
            "months",
        ),
        (
            {
                "query": {"mode": "article", "value": "Astronomy"},
                "languages": ["uk"],
                "period": {"granularity": "daily"},
            },
            "granularity",
        ),
        ({"query": {"mode": "article", "value": "Astronomy"}, "languages": ["uk"], "unexpected": True}, "unexpected"),
        (
            {
                "query": {"mode": "article", "value": "Astronomy", "article_overrides": {"en": ["Astronomy"]}},
                "languages": ["en"],
            },
            "article_overrides",
        ),
        (
            {
                "query": {
                    "mode": "topic",
                    "value": "Astronomy",
                    "article_overrides": {"en": ["One", "Two", "Three", "Four"]},
                },
                "languages": ["en"],
            },
            "one to three",
        ),
        (
            {
                "query": {
                    "mode": "topic",
                    "value": "Astronomy",
                    "article_overrides": {"en": ["Astronomy"]},
                },
                "languages": ["uk"],
            },
            "not listed in languages",
        ),
    ],
)
def test_invalid_config_is_rejected(payload: dict[str, object], expected_message: str) -> None:
    with pytest.raises(ValidationError, match=expected_message):
        AnalysisConfig.model_validate(payload)


def test_complete_month_range_excludes_current_month() -> None:
    assert complete_month_range(24, date(2026, 9, 24)) == (date(2024, 9, 1), date(2026, 8, 1))
    assert complete_month_range(12, date(2026, 1, 1)) == (date(2025, 1, 1), date(2025, 12, 1))


def test_monthly_pageview_distinguishes_missing_observations() -> None:
    unknown = MonthlyPageview(month=date(2026, 8, 1), status=ObservationStatus.UNKNOWN)
    inferred_zero = MonthlyPageview(month=date(2026, 8, 1), views=0, status=ObservationStatus.ZERO_INFERRED)

    assert unknown.views is None
    assert inferred_zero.views == 0
    with pytest.raises(ValidationError, match="unknown observations"):
        MonthlyPageview(month=date(2026, 8, 1), views=0, status=ObservationStatus.UNKNOWN)
    with pytest.raises(ValidationError, match="first day"):
        MonthlyPageview(month=date(2026, 8, 2), views=1)


def test_cli_prints_generated_artifact_paths_for_valid_config(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/analyze.py",
            "--config",
            "examples/astronomy-uk.json",
            "--output-dir",
            str(tmp_path / "output"),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    artifact_paths = json.loads(result.stdout)
    assert set(artifact_paths) == {"analysis_json", "chart", "pdf"}


def test_cli_returns_nonzero_for_invalid_config(tmp_path: Path) -> None:
    invalid_config = tmp_path / "invalid.json"
    invalid_config.write_text(
        '{"query":{"mode":"article","value":"Astronomy"},"languages":["uk","uk"]}',
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "scripts/analyze.py", "--config", str(invalid_config)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "duplicate language codes" in result.stderr
