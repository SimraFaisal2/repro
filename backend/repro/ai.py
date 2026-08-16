"""AI provider abstraction.

The agent is never tied to a single model vendor. Providers:
  - OpenAI-compatible endpoints (OPENAI_API_KEY / OPENAI_BASE_URL)
  - Anthropic (ANTHROPIC_API_KEY)
  - Ollama local models (OLLAMA_URL)

When no provider is configured (or a provider call fails) the engine uses
the deterministic, evidence-based rules in analyzer.py/patcher.py — so the
product works end-to-end offline while still reasoning over real evidence.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

import httpx

from .config import cfg

SYSTEM_PROMPT = """You are REPRO, an AI software failure investigator.
You reason ONLY over the evidence you are given (real test output, real
stack trace, real runtime values, real source code). You never invent
facts. Distinguish OBSERVED evidence from your INFERRED reasoning.

Respond with JSON only, using this exact shape:
{
  "root_cause": "short statement of the root cause",
  "explanation": "2-4 sentence explanation grounded in the evidence",
  "confidence": 0.0-1.0,
  "risk": "LOW|MEDIUM|HIGH",
  "fix": {
    "file": "relative/path.py",
    "reason": "why this change fixes it",
    "diff": "unified diff (---/+++ with line numbers or plain +/- lines) for the minimal change"
  }
}
If you cannot produce a confident fix, set fix to null."""


class ProviderError(Exception):
    pass


class AIProvider:
    name = "none"

    def analyze_and_fix(self, context: dict) -> Optional[dict]:
        """Return {root_cause, explanation, confidence, risk, fix} or None."""
        raise NotImplementedError


def _prompt(context: dict) -> str:
    return f"""REPOSITORY CONTEXT
{failure_context(context)}

TASK: Identify the root cause and produce a minimal fix. Return JSON."""


def failure_context(context: dict) -> str:
    parts = []
    f = context.get("failure", {})
    parts.append(f"Failing test: {f.get('test_id')}")
    parts.append(f"Error: {f.get('error_type')}: {f.get('error_msg')}")
    parts.append(f"Location: {f.get('file')}:{f.get('line')}")
    parts.append("Stack trace:\n" + (f.get("stack_trace") or "none"))
    src = context.get("source_context", "")
    if src:
        parts.append("Source around failing line:\n" + src)
    ev = context.get("evidence", [])
    if ev:
        lines = []
        for e in ev:
            lines.append(f"[{e.get('kind')}] {e.get('source')}: {e.get('text')}")
        parts.append("Evidence collected:\n" + "\n".join(lines[:25]))
    tr = context.get("trace", [])
    if tr:
        lines = []
        for t in tr[:15]:
            lines.append(f"{t.get('func')}() {t.get('file')}:{t.get('line')} "
                         f"args={t.get('args')} return={t.get('return_value')}")
        parts.append("Runtime trace (real):\n" + "\n".join(lines))
    return "\n".join(parts)


class OpenAIProvider(AIProvider):
    name = "openai"

    def analyze_and_fix(self, context: dict) -> Optional[dict]:
        payload = {
            "model": cfg.openai_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _prompt(context)},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {cfg.openai_api_key}"}
        resp = httpx.post(f"{cfg.openai_base_url}/chat/completions",
                          json=payload, headers=headers, timeout=90)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return _parse_json(content)


class AnthropicProvider(AIProvider):
    name = "anthropic"

    def analyze_and_fix(self, context: dict) -> Optional[dict]:
        payload = {
            "model": cfg.anthropic_model,
            "max_tokens": 2000,
            "temperature": 0.1,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": _prompt(context)}],
        }
        headers = {"x-api-key": cfg.anthropic_api_key, "anthropic-version": "2023-06-01"}
        resp = httpx.post("https://api.anthropic.com/v1/messages",
                          json=payload, headers=headers, timeout=90)
        resp.raise_for_status()
        data = resp.json()
        content = "".join(b.get("text", "") for b in data.get("content", []))
        return _parse_json(content)


class OllamaProvider(AIProvider):
    name = "ollama"

    def analyze_and_fix(self, context: dict) -> Optional[dict]:
        payload = {
            "model": cfg.ollama_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _prompt(context)},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1},
        }
        resp = httpx.post(f"{cfg.ollama_url}/api/chat", json=payload, timeout=180)
        resp.raise_for_status()
        return _parse_json(resp.json()["message"]["content"])


def _parse_json(content: str) -> Optional[dict]:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(json)?", "", content).rstrip("`").strip()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", content, re.S)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    return {
        "root_cause": str(data.get("root_cause", "")),
        "explanation": str(data.get("explanation", "")),
        "confidence": float(data.get("confidence", 0.5)),
        "risk": str(data.get("risk", "MEDIUM")),
        "fix": data.get("fix"),
    }


def get_provider() -> Optional[AIProvider]:
    if cfg.ollama_url and _ollama_reachable():
        return OllamaProvider()
    if cfg.anthropic_api_key:
        return AnthropicProvider()
    if cfg.openai_api_key:
        return OpenAIProvider()
    return None


def _ollama_reachable() -> bool:
    try:
        r = httpx.get(f"{cfg.ollama_url}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def provider_label() -> str:
    p = get_provider()
    return p.name if p else "heuristic-rules"
