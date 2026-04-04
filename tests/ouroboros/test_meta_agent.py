"""Tests for MetaAgent state machine."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ouroboros.meta.agent import MetaAgent, MetaResult, _check_bloat


class TestMetaAgent:
    def test_insufficient_data_returns_early(self, tmp_path: Path):
        meta = MetaAgent(
            prompts_dir=tmp_path / "prompts",
            archive_dir=tmp_path / "archive",
            benchmark_dir=tmp_path / "benchmarks",
            target_path=tmp_path / "ouroboros",
            model="test-model",
            defaults={"implementer": "test prompt"},
        )
        result = meta.run()
        assert result.state == "IDLE"
        assert "insufficient" in result.reason.lower()

    def test_bloat_gate_rejects_long_mutation(self, tmp_path: Path):
        passed, msg = _check_bloat(parent_tokens=100, mutated_tokens=130)
        assert passed is False
        assert "bloat" in msg.lower()

    def test_bloat_gate_accepts_reasonable_mutation(self, tmp_path: Path):
        passed, msg = _check_bloat(parent_tokens=100, mutated_tokens=115)
        assert passed is True
