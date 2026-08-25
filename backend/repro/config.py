"""Central configuration. Every value can be overridden by environment variables."""
from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = PACKAGE_DIR.parent
REPRO_ROOT = BACKEND_DIR.parent


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


class Config:
    data_dir: Path = Path(_env("REPRO_DATA_DIR", str(REPRO_ROOT / "data")))
    db_path: Path = Path(_env("REPRO_DB", str(data_dir / "repro.db")))
    projects_dir: Path = data_dir / "projects"
    workspace_dir: Path = Path(_env("REPRO_WORKSPACE", str(data_dir / "workspace")))

    # Execution guardrails
    exec_timeout: int = int(_env("REPRO_TIMEOUT", "120"))        # seconds per command
    max_attempts: int = int(_env("REPRO_MAX_ATTEMPTS", "3"))     # autonomous repair attempts
    debug_budget: int = int(_env("REPRO_DEBUG_BUDGET", "8"))     # max state-machine iterations
    # Benchmark strategy mode: "rules" (deterministic only), "llm" (LLM only)
    # or "hybrid" (rules first, escalate to LLM). Drives the state-machine
    # strategy ladder in agent.run().
    strategy_mode: str = _env("REPRO_STRATEGY_MODE", "hybrid")
    use_docker: bool = _env("REPRO_USE_DOCKER", "").lower() in ("1", "true", "yes")
    install_deps: bool = _env("REPRO_INSTALL_DEPS", "1").lower() in ("1", "true", "yes")

    # AI providers (see ai.py). Heuristic engine is always the fallback.
    openai_api_key: str = _env("OPENAI_API_KEY", "")
    openai_base_url: str = _env("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_model: str = _env("OPENAI_MODEL", "gpt-4o-mini")
    anthropic_api_key: str = _env("ANTHROPIC_API_KEY", "")
    anthropic_model: str = _env("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    ollama_url: str = _env("OLLAMA_URL", "http://localhost:11434")
    ollama_model: str = _env("OLLAMA_MODEL", "qwen2.5-coder:7b")


def strategy_ladder(mode: str | None = None) -> list[str]:
    """The state-machine strategy ladder for a benchmark mode.

    - rules:  deterministic rule engine only (never touches the network)
    - llm:    LLM provider only (skips the rule engine)
    - hybrid: rules first, escalating to LLM / deep-evidence
    """
    mode = (mode or cfg.strategy_mode or "hybrid").lower()
    if mode == "rules":
        return ["rules", "terminate"]
    if mode == "llm":
        return ["llm", "deep-evidence", "terminate"]
    return ["rules", "llm", "deep-evidence", "terminate"]


cfg = Config()


def ensure_dirs() -> None:
    for d in (cfg.data_dir, cfg.projects_dir, cfg.workspace_dir):
        d.mkdir(parents=True, exist_ok=True)
