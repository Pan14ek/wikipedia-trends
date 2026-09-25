#!/usr/bin/env python3
"""Bootstrap a cached writable runtime and run the installed Wikipedia Trends Skill."""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import venv
from collections.abc import Sequence
from pathlib import Path

MINIMUM_PYTHON = (3, 12)


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the analysis CLI through a cached runtime outside the Skill root."""
    skill_root = Path(__file__).resolve().parents[1]
    try:
        require_supported_python(sys.version_info[:2])
        runtime_root = resolve_runtime_root(skill_root)
        runtime_python = ensure_runtime(skill_root, runtime_root, sys.version_info[:2])
        environment = _runtime_environment(skill_root, runtime_root)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"wikipedia-trends bootstrap error: {error}", file=sys.stderr)
        return 1

    command = [str(runtime_python), str(skill_root / "scripts" / "analyze.py"), *(arguments or sys.argv[1:])]
    try:
        completed = subprocess.run(command, env=environment, check=False)
    except OSError as error:
        print(f"wikipedia-trends bootstrap error: unable to start analysis CLI: {error}", file=sys.stderr)
        return 1
    return completed.returncode


def require_supported_python(version: Sequence[int]) -> None:
    """Reject interpreters older than the project's supported Python version."""
    if tuple(version[:2]) < MINIMUM_PYTHON:
        actual = ".".join(str(part) for part in version[:2])
        raise RuntimeError(f"Python 3.12 or newer is required; found Python {actual}.")


def resolve_runtime_root(skill_root: Path) -> Path:
    """Select a writable cache root without ever placing runtime data in the Skill."""
    configured_root = os.environ.get("WIKIPEDIA_TRENDS_RUNTIME_DIR")
    if configured_root:
        root = Path(configured_root).expanduser()
    elif platform.system() == "Windows":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "wikipedia-trends"
    elif platform.system() == "Darwin":
        root = Path.home() / "Library" / "Caches" / "wikipedia-trends"
    else:
        root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "wikipedia-trends"
    resolved = root.resolve()
    if resolved == skill_root or skill_root in resolved.parents:
        raise ValueError("WIKIPEDIA_TRENDS_RUNTIME_DIR must be outside the Skill root")
    return resolved


def runtime_fingerprint(skill_root: Path, python_version: Sequence[int]) -> str:
    """Hash the Python major/minor version and checked-in runtime lock."""
    lock_path = skill_root / "requirements-runtime.lock"
    digest = hashlib.sha256(lock_path.read_bytes()).hexdigest()
    return f"py{python_version[0]}.{python_version[1]}-{digest}"


def ensure_runtime(skill_root: Path, runtime_root: Path, python_version: Sequence[int]) -> Path:
    """Reuse a matching venv or create and install one in the writable cache."""
    fingerprint = runtime_fingerprint(skill_root, python_version)
    runtime_root.mkdir(parents=True, exist_ok=True)
    runtime_path = runtime_root / "runtimes" / fingerprint
    python_path = _venv_python(runtime_path)
    if python_path.is_file():
        print(f"wikipedia-trends: reusing cached runtime {fingerprint}", file=sys.stderr)
        return python_path

    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    stage_root = Path(tempfile.mkdtemp(prefix=f".{fingerprint}-", dir=runtime_path.parent))
    try:
        print(f"wikipedia-trends: creating cached runtime {fingerprint}", file=sys.stderr)
        venv.EnvBuilder(with_pip=True).create(stage_root)
        stage_python = _venv_python(stage_root)
        lock_path = skill_root / "requirements-runtime.lock"
        cache_root = runtime_root / "cache"
        cache_root.mkdir(parents=True, exist_ok=True)
        install_environment = os.environ.copy()
        install_environment["XDG_CACHE_HOME"] = str(cache_root)
        install_environment["PIP_CACHE_DIR"] = str(cache_root / "pip")
        installation = subprocess.run(
            [
                str(stage_python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--require-hashes",
                "-r",
                str(lock_path),
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            env=install_environment,
        )
        if installation.returncode != 0:
            raise RuntimeError(f"runtime dependency installation failed with exit code {installation.returncode}")
        if runtime_path.exists():
            shutil.rmtree(runtime_path)
        stage_root.replace(runtime_path)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        shutil.rmtree(stage_root, ignore_errors=True)
        raise
    return _venv_python(runtime_path)


def _venv_python(venv_root: Path) -> Path:
    """Return the platform-specific Python executable inside a venv."""
    executable = venv_root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return executable


def _runtime_environment(skill_root: Path, runtime_root: Path) -> dict[str, str]:
    """Set Python import and Matplotlib cache paths to writable locations."""
    environment = os.environ.copy()
    cache_root = runtime_root / "cache"
    matplotlib_root = cache_root / "matplotlib"
    matplotlib_root.mkdir(parents=True, exist_ok=True)
    environment["MPLCONFIGDIR"] = str(matplotlib_root)
    environment["XDG_CACHE_HOME"] = str(cache_root)
    source_path = str(skill_root / "src")
    prior_python_path = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(part for part in (source_path, prior_python_path) if part)
    return environment


if __name__ == "__main__":
    raise SystemExit(main())
