"""WT-M25 tests for the installed-Skill read-only-safe runtime launcher."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run


def test_python_before_312_fails_with_clear_bootstrap_error() -> None:
    with pytest.raises(RuntimeError, match="Python 3.12 or newer is required"):
        run.require_supported_python((3, 11))


def test_python_before_312_bootstrap_fails_on_stderr_only(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(run.sys, "version_info", (3, 11, 9))

    assert run.main(["--help"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Python 3.12 or newer is required" in captured.err


def test_matching_runtime_cache_skips_dependency_installation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    skill_root = _skill_root(tmp_path)
    install_calls: list[list[str]] = []
    _fake_venv(monkeypatch)
    monkeypatch.setattr(run.subprocess, "run", lambda command, **_: _record_install(install_calls, command))

    first = run.ensure_runtime(skill_root, tmp_path / "runtime", (3, 12))
    second = run.ensure_runtime(skill_root, tmp_path / "runtime", (3, 12))

    assert first == second
    assert len(install_calls) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "creating cached runtime" in captured.err
    assert "reusing cached runtime" in captured.err


def test_runtime_fingerprint_change_selects_a_new_cache_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    skill_root = _skill_root(tmp_path)
    install_calls: list[list[str]] = []
    _fake_venv(monkeypatch)
    monkeypatch.setattr(run.subprocess, "run", lambda command, **_: _record_install(install_calls, command))

    first = run.ensure_runtime(skill_root, tmp_path / "runtime", (3, 12))
    (skill_root / "requirements-runtime.lock").write_text("updated lock\n")
    second = run.ensure_runtime(skill_root, tmp_path / "runtime", (3, 12))

    assert first != second
    assert len(install_calls) == 2


def test_read_only_skill_root_is_never_used_for_runtime_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    skill_root = _skill_root(tmp_path)
    original_files = {
        path.relative_to(skill_root): path.read_bytes() for path in skill_root.rglob("*") if path.is_file()
    }
    for directory in (skill_root, skill_root / "scripts"):
        directory.chmod(0o555)
    for file_path in skill_root.rglob("*"):
        if file_path.is_file():
            file_path.chmod(0o444)

    install_calls: list[list[str]] = []
    _fake_venv(monkeypatch)
    monkeypatch.setattr(run.subprocess, "run", lambda command, **_: _record_install(install_calls, command))
    runtime = tmp_path / "external-runtime"
    runtime_path = run.ensure_runtime(skill_root, runtime, (3, 12))

    assert runtime_path.is_relative_to(runtime)
    assert "-e" not in install_calls[0]
    assert "egg-info" not in " ".join(install_calls[0])
    assert all(
        path.read_bytes() == contents
        for path, contents in ((skill_root / key, value) for key, value in original_files.items())
    )
    assert {path.relative_to(skill_root) for path in skill_root.rglob("*") if path.is_file()} == set(original_files)
    for directory in (skill_root, skill_root / "scripts"):
        directory.chmod(0o755)
    for file_path in skill_root.rglob("*"):
        if file_path.is_file():
            file_path.chmod(0o644)


@pytest.mark.parametrize("exit_code", [0, 1, 2])
def test_launcher_preserves_analysis_exit_code_and_keeps_bootstrap_logs_on_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    exit_code: int,
) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("WIKIPEDIA_TRENDS_RUNTIME_DIR", str(runtime_root))
    monkeypatch.setattr(run, "ensure_runtime", lambda *_: tmp_path / "venv" / "bin" / "python")
    monkeypatch.setattr(run, "resolve_runtime_root", lambda _: runtime_root)
    payload = '{"cli_schema_version":"1.0.0","status":"success","analysis_json":null,"charts":[],"pdf":null}\n'

    def run_analysis(command: list[str], **_: object) -> SimpleNamespace:
        if exit_code == 0:
            print(payload, end="")
        return SimpleNamespace(returncode=exit_code)

    monkeypatch.setattr(run.subprocess, "run", run_analysis)
    result = run.main(["--config", "input.json", "--output-dir", "output"])
    captured = capsys.readouterr()

    assert result == exit_code
    assert captured.out == (payload if exit_code == 0 else "")
    assert "wikipedia-trends bootstrap error" not in captured.err


def test_bootstrap_diagnostics_do_not_prepend_success_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("WIKIPEDIA_TRENDS_RUNTIME_DIR", str(runtime_root))
    monkeypatch.setattr(run, "resolve_runtime_root", lambda _: runtime_root)
    monkeypatch.setattr(run, "ensure_runtime", lambda *_: tmp_path / "venv" / "python")
    monkeypatch.setattr(run.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=0))

    assert run.main(["--help"]) == 0


def _skill_root(tmp_path: Path) -> Path:
    """Create a minimal fake installed Skill directory and lock file."""
    root = tmp_path / "read-only-skill"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "analyze.py").write_text("pass\n")
    (root / "requirements-runtime.lock").write_text("package==1.0 --hash=sha256:abc\n")
    return root


def _fake_venv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Create a fake venv interpreter without installing external packages."""

    class FakeEnvBuilder:
        def __init__(self, *, with_pip: bool) -> None:
            assert with_pip

        def create(self, path: Path) -> None:
            binary_dir = path / "bin"
            binary_dir.mkdir()
            (binary_dir / "python").write_text("fake interpreter")

    monkeypatch.setattr(run.venv, "EnvBuilder", FakeEnvBuilder)


def _record_install(calls: list[list[str]], command: list[str]) -> subprocess.CompletedProcess[str]:
    """Record the dependency command and report a successful installation."""
    calls.append(command)
    return subprocess.CompletedProcess(command, 0)
