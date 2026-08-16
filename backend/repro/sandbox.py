"""Isolation layer.

The untrusted repository is copied into a workspace directory and executed
with a stripped environment, a hard timeout, and no host secrets. When
Docker is available and REPRO_USE_DOCKER=1, commands run inside a
`python:3.x` container with read-write access only to the sandbox copy.

The user's repository is NEVER modified from here — patches are applied to
the sandbox copy on a dedicated git branch, and only an explicit
`POST /investigations/{id}/apply` writes back to the user's checkout.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .config import cfg
from . import repo as repo_mod

# Minimal, functional environment. Everything else (tokens, keys, host vars)
# is deliberately dropped.
_WINDOWS_BASE = {"SYSTEMROOT", "SYSTEMDRIVE", "TEMP", "TMP", "PATHEXT",
                 "COMSPEC", "WINDIR", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
                 "PROCESSOR_IDENTIFIER", "PROCESSOR_LEVEL", "PROCESSOR_REVISION",
                 "OS", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "APPDATA",
                 "LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA",
                 "PUBLIC", "COMPUTERNAME", "USERNAME", "USERDOMAIN", "ALLUSERSPROFILE",
                 "COMMONPROGRAMFILES", "COMMONPROGRAMFILES(X86)", "PROGRAMW6432",
                 "COMMONPROGRAMW6432", "PSModulePath", "TZ", "HOMEDRIVE"}
_POSIX_BASE = {"HOME", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "USER", "LOGNAME", "SHELL"}

# Keep things like PATH working so python finds its own interpreter/deps.
_KEEP = {"PATH", "PYTHONIOENCODING", "PYTHONUTF8", "VIRTUAL_ENV", "PIP_DISABLE_PIP_VERSION_CHECK",
         "PIP_NO_INPUT", "PIP_QUIET", "PYTHONDONTWRITEBYTECODE", "SystemRoot", "windir"}


def minimal_env() -> dict:
    env = {}
    base = _WINDOWS_BASE if os.name == "nt" else _POSIX_BASE
    for k, v in os.environ.items():
        if k in base or k in _KEEP:
            env[k] = v
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
    env.setdefault("PIP_NO_INPUT", "1")
    return env


class Sandbox:
    """An isolated copy of a repository, ready to execute tests."""

    def __init__(self, work_id: str, source: Path):
        self.id = work_id
        self.root = cfg.workspace_dir / work_id
        if self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)
        repo_mod.copy_dir(source, self.root)
        self.venv = self.root / ".repro-venv"
        self.python = sys.executable
        self.env = minimal_env()
        self.env["REPRO_REPO_ROOT"] = str(self.root)

    # ------------------------------------------------------------- commands
    def run(self, args: list[str], cwd: Path | None = None, timeout: int | None = None,
            extra_env: dict | None = None) -> subprocess.CompletedProcess:
        timeout = timeout or cfg.exec_timeout
        cwd = cwd or self.root
        env = dict(self.env)
        if extra_env:
            env.update(extra_env)
        if cfg.use_docker and self._docker_available():
            return self._run_docker(args, cwd, timeout, env)
        proc = subprocess.run(
            args, capture_output=True, text=True, cwd=str(cwd),
            env=env, timeout=timeout, shell=os.name == "nt",
        )
        return proc

    def run_python(self, args: list[str], cwd: Path | None = None, timeout: int | None = None,
                   extra_env: dict | None = None) -> subprocess.CompletedProcess:
        return self.run([self.python, *args], cwd=cwd, timeout=timeout, extra_env=extra_env)

    # ------------------------------------------------------------- deps/venv
    def install_dependencies(self, overview: dict | None = None) -> tuple[bool, str]:
        """Create a venv and install deps when the project declares any."""
        if not cfg.install_deps:
            return True, "dependency install disabled by config"
        overview = overview or {}
        if not overview.get("has_requirements"):
            return True, "no dependency files — using system python"
        req = self.root / "requirements.txt"
        if not req.exists():
            pyproject = self.root / "pyproject.toml"
            if pyproject.exists() and "dependencies" in pyproject.read_text(errors="replace"):
                req = pyproject
            else:
                return True, "no pip-installable dependency file"
        try:
            self._make_venv()
            pip = [str(self.venv / ("Scripts" if os.name == "nt" else "bin") / "pip")]
            proc = subprocess.run(
                [*pip, "install", "--quiet", "--disable-pip-version-check", "-r", str(req)],
                capture_output=True, text=True, env=self.env, timeout=cfg.exec_timeout * 6,
                cwd=str(self.root), shell=os.name == "nt",
            )
            if proc.returncode == 0:
                self.python = str(self.venv / ("Scripts" if os.name == "nt" else "bin") / "python")
                return True, "dependencies installed into isolated venv"
            return False, f"pip install failed: {proc.stderr.strip()[:400]}"
        except Exception as e:  # noqa: BLE001
            return False, f"venv/pip failure: {e}"

    def _make_venv(self) -> None:
        if (self.venv / "pyvenv.cfg").exists():
            return
        subprocess.run([sys.executable, "-m", "venv", str(self.venv)],
                       capture_output=True, text=True, timeout=180, env=self.env)

    # --------------------------------------------------------------- docker
    def _docker_available(self) -> bool:
        try:
            proc = subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"],
                                  capture_output=True, text=True, timeout=10)
            return proc.returncode == 0
        except Exception:
            return False

    def _run_docker(self, args: list[str], cwd: Path, timeout: int,
                    env: dict) -> subprocess.CompletedProcess:
        rel = cwd.relative_to(self.root)
        cmd = ["docker", "run", "--rm", "--network", "none",
               "-v", f"{self.root}:/app", "-w", f"/app/{rel}",
               "-e", "REPRO_REPO_ROOT=/app",
               "-m", "2g", "--cpus", "2", "--pids-limit", "512",
               "python:" + os.environ.get("REPRO_PYTHON_IMAGE", "3.11-slim"),
               *args]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=self.env)

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)
