"""Configuration loading and validation for Ouroboros."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OuroborosConfig:
    target_path: str = "src/"
    target_cli_command: str = "python -m src.main"
    target_test_command: str = "python -m pytest tests/src/"
    model_observer: str = "claude-sonnet-4-6"
    model_strategist: str = "claude-opus-4-6"
    model_implementer: str = "claude-opus-4-6"
    model_evaluator: str = "claude-sonnet-4-6"
    max_iterations: int = 10
    time_budget_minutes: int = 180
    max_tokens_per_iteration: int = 100_000
    cooldown_seconds: int = 30
    sandbox_allowed_commands: tuple[str, ...] = (
        "python -m src.main",
        "python -m pytest",
        "mypy --strict src/",
        "ruff check src/",
    )
    sandbox_blocked_paths: tuple[str, ...] = (
        "ouroboros/",
        "tests/",
        "benchmarks/",
        ".git/",
    )
    sandbox_timeout_seconds: int = 300
    merge_gate_regression_floor: float = 1.0
    merge_gate_noise_tolerance: float = 0.02
    max_usd_per_run: float = 10.0
    max_usd_per_iteration: float = 2.0
    budget_warn_percentage: int = 80
    dashboard_web_port: int = 8420
    dashboard_refresh_seconds: int = 5

    def with_overrides(self, overrides: dict[str, Any]) -> OuroborosConfig:
        valid = {k: v for k, v in overrides.items() if hasattr(self, k)}
        return replace(self, **valid)


DEFAULT_CONFIG = OuroborosConfig()


def load_config(path: Path) -> OuroborosConfig:
    if not path.exists():
        return DEFAULT_CONFIG

    import yaml

    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    flat: dict[str, Any] = {}

    target = raw.get("target", {})
    if "path" in target:
        flat["target_path"] = target["path"]
    if "cli_command" in target:
        flat["target_cli_command"] = target["cli_command"]
    if "test_command" in target:
        flat["target_test_command"] = target["test_command"]

    models = raw.get("models", {})
    for role in ("observer", "strategist", "implementer", "evaluator"):
        if role in models:
            flat[f"model_{role}"] = models[role]

    loop = raw.get("loop", {})
    for key in (
        "max_iterations",
        "time_budget_minutes",
        "max_tokens_per_iteration",
        "cooldown_seconds",
    ):
        if key in loop:
            flat[key] = loop[key]

    sandbox = raw.get("sandbox", {})
    if "allowed_commands" in sandbox:
        flat["sandbox_allowed_commands"] = tuple(sandbox["allowed_commands"])
    if "blocked_paths" in sandbox:
        flat["sandbox_blocked_paths"] = tuple(sandbox["blocked_paths"])
    if "timeout_seconds" in sandbox:
        flat["sandbox_timeout_seconds"] = sandbox["timeout_seconds"]

    scoreboard = raw.get("scoreboard", {})
    gate = scoreboard.get("merge_gate", {})
    if "regression_rate" in gate:
        flat["merge_gate_regression_floor"] = gate["regression_rate"]
    if "noise_tolerance" in gate:
        flat["merge_gate_noise_tolerance"] = gate["noise_tolerance"]

    budget = raw.get("budget", {})
    if "max_usd_per_run" in budget:
        flat["max_usd_per_run"] = budget["max_usd_per_run"]
    if "max_usd_per_iteration" in budget:
        flat["max_usd_per_iteration"] = budget["max_usd_per_iteration"]
    if "warn_at_percentage" in budget:
        flat["budget_warn_percentage"] = budget["warn_at_percentage"]

    return DEFAULT_CONFIG.with_overrides(flat)
