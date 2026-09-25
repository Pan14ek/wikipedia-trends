"""Deterministic tests for the agent-facing CLI execution protocol."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wiki_trends import cli
from wiki_trends.pipeline import AnalysisRunResult


def _write_config(tmp_path: Path, output: dict[str, bool] | None = None) -> Path:
    path = tmp_path / "analysis.json"
    payload: dict[str, object] = {
        "query": {"mode": "article", "value": "Astronomy"},
        "languages": ["en"],
    }
    if output is not None:
        payload["output"] = output
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("outputs", "expected_json", "expected_charts", "expected_pdf"),
    [
        ({"json": True, "charts": True, "pdf": True}, "analysis.json", ["trend.png"], "report.pdf"),
        ({"json": False, "charts": True, "pdf": True}, None, ["trend.png"], "report.pdf"),
        ({"json": True, "charts": False, "pdf": True}, "analysis.json", [], "report.pdf"),
        ({"json": True, "charts": True, "pdf": False}, "analysis.json", ["trend.png"], None),
        ({"json": False, "charts": False, "pdf": False}, None, [], None),
    ],
)
def test_success_payload_has_explicit_optional_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    outputs: dict[str, bool],
    expected_json: str | None,
    expected_charts: list[str],
    expected_pdf: str | None,
) -> None:
    config_path = _write_config(tmp_path, outputs)

    def run_stub(config: object, _: Path) -> AnalysisRunResult:
        assert config.output.json_output is outputs["json"]  # type: ignore[attr-defined]
        return AnalysisRunResult(
            tmp_path / "analysis.json" if outputs["json"] else None,
            [tmp_path / "trend.png"] if outputs["charts"] else [],
            tmp_path / "report.pdf" if outputs["pdf"] else None,
        )

    monkeypatch.setattr(cli, "run_analysis", run_stub)

    assert cli.main(["--config", str(config_path), "--output-dir", str(tmp_path / "out")]) == 0
    stdout = capsys.readouterr().out
    payload = json.loads(stdout)

    assert payload == {
        "cli_schema_version": "1.0.0",
        "status": "success",
        "analysis_json": str(tmp_path / expected_json) if expected_json else None,
        "charts": [str(tmp_path / path) for path in expected_charts],
        "pdf": str(tmp_path / expected_pdf) if expected_pdf else None,
    }
    assert stdout == json.dumps(payload, ensure_ascii=False) + "\n"
    assert '"None"' not in stdout


def test_configuration_failure_is_structured_on_stderr(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text('{"query":{"mode":"article","value":"Astronomy"},"languages":["en","en"]}')

    assert cli.main(["--config", str(invalid_path), "--output-dir", str(tmp_path / "out")]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    error = json.loads(captured.err)
    assert error["cli_schema_version"] == "1.0.0"
    assert error["status"] == "error"
    assert error["error_type"] == "configuration_error"
    assert "languages must be unique" in error["message"]


def test_analysis_failure_is_structured_on_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = _write_config(tmp_path)

    def fail_analysis(_: object, __: Path) -> AnalysisRunResult:
        raise RuntimeError("simulated analysis failure")

    monkeypatch.setattr(cli, "run_analysis", fail_analysis)

    assert cli.main(["--config", str(config_path), "--output-dir", str(tmp_path / "out")]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "cli_schema_version": "1.0.0",
        "status": "error",
        "error_type": "analysis_error",
        "message": "simulated analysis failure",
    }
    assert "Traceback" not in captured.err
