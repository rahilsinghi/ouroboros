import tempfile
from pathlib import Path

import pytest

from ouroboros.config import OuroborosConfig, load_config, DEFAULT_CONFIG


class TestDefaultConfig:
    def test_has_all_required_fields(self):
        cfg = DEFAULT_CONFIG
        assert cfg.target_path == "src/"
        assert cfg.target_cli_command == "python -m src.main"
        assert cfg.target_test_command == "python -m pytest tests/src/"
        assert cfg.model_observer == "claude-sonnet-4-6"
        assert cfg.model_strategist == "claude-opus-4-6"
        assert cfg.model_implementer == "claude-opus-4-6"
        assert cfg.model_evaluator == "claude-sonnet-4-6"
        assert cfg.max_iterations == 10
        assert cfg.time_budget_minutes == 180
        assert cfg.max_tokens_per_iteration == 100_000
        assert cfg.cooldown_seconds == 30
        assert cfg.sandbox_timeout_seconds == 300
        assert cfg.merge_gate_regression_floor == 1.0
        assert cfg.merge_gate_noise_tolerance == 0.02
        assert cfg.max_usd_per_run == 10.0
        assert cfg.max_usd_per_iteration == 2.0
        assert cfg.budget_warn_percentage == 80

    def test_allowed_commands(self):
        cfg = DEFAULT_CONFIG
        assert "python -m src.main" in cfg.sandbox_allowed_commands
        assert "python -m pytest" in cfg.sandbox_allowed_commands
        assert "mypy --strict src/" in cfg.sandbox_allowed_commands
        assert "ruff check src/" in cfg.sandbox_allowed_commands

    def test_blocked_paths(self):
        cfg = DEFAULT_CONFIG
        assert "ouroboros/" in cfg.sandbox_blocked_paths
        assert "tests/" in cfg.sandbox_blocked_paths
        assert "benchmarks/" in cfg.sandbox_blocked_paths
        assert ".git/" in cfg.sandbox_blocked_paths


class TestLoadConfig:
    def test_loads_from_yaml_file(self, tmp_path: Path):
        yaml_content = """
target:
  path: custom/
  cli_command: "python custom.py"
  test_command: "pytest custom/"

models:
  observer: claude-haiku-4-5-20251001
  strategist: claude-sonnet-4-6
  implementer: claude-sonnet-4-6
  evaluator: claude-haiku-4-5-20251001

loop:
  max_iterations: 5
  time_budget_minutes: 60
"""
        config_file = tmp_path / "ouroboros.yaml"
        config_file.write_text(yaml_content)
        cfg = load_config(config_file)
        assert cfg.target_path == "custom/"
        assert cfg.target_cli_command == "python custom.py"
        assert cfg.model_observer == "claude-haiku-4-5-20251001"
        assert cfg.max_iterations == 5
        assert cfg.cooldown_seconds == 30

    def test_missing_file_returns_default(self, tmp_path: Path):
        cfg = load_config(tmp_path / "nonexistent.yaml")
        assert cfg == DEFAULT_CONFIG

    def test_cli_overrides(self):
        overrides = {"max_iterations": 20, "model_evaluator": "claude-haiku-4-5-20251001"}
        cfg = DEFAULT_CONFIG.with_overrides(overrides)
        assert cfg.max_iterations == 20
        assert cfg.model_evaluator == "claude-haiku-4-5-20251001"
        assert cfg.model_observer == "claude-sonnet-4-6"
