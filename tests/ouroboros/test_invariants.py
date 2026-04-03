"""Tests for pre-merge safety invariants."""
from __future__ import annotations

import pytest

from ouroboros.scoreboard.invariants import InvariantResult, SafetyInvariants


class TestSafetyInvariants:
    def setup_method(self):
        self.invariants = SafetyInvariants(
            allowed_root_configs=("ouroboros.yaml",),
        )

    def test_passes_when_all_clean(self):
        result = self.invariants.check(
            before_test_count=100,
            after_test_count=100,
            before_ruff_violations=0,
            after_ruff_violations=0,
            files_written=["ouroboros/agents/observer.py"],
        )
        assert result.passed is True
        assert result.violation == ""

    def test_fails_when_test_count_decreases(self):
        result = self.invariants.check(
            before_test_count=100,
            after_test_count=99,
            before_ruff_violations=0,
            after_ruff_violations=0,
            files_written=[],
        )
        assert result.passed is False
        assert "test count" in result.violation.lower()

    def test_fails_when_ruff_violations_increase(self):
        result = self.invariants.check(
            before_test_count=100,
            after_test_count=100,
            before_ruff_violations=3,
            after_ruff_violations=4,
            files_written=[],
        )
        assert result.passed is False
        assert "ruff" in result.violation.lower()

    def test_fails_when_conftest_written(self):
        result = self.invariants.check(
            before_test_count=100,
            after_test_count=100,
            before_ruff_violations=0,
            after_ruff_violations=0,
            files_written=["ouroboros/conftest.py"],
        )
        assert result.passed is False
        assert "conftest" in result.violation.lower()

    def test_fails_when_root_config_created(self):
        result = self.invariants.check(
            before_test_count=100,
            after_test_count=100,
            before_ruff_violations=0,
            after_ruff_violations=0,
            files_written=["pytest.ini"],
        )
        assert result.passed is False
        assert "config" in result.violation.lower()

    def test_allows_ouroboros_yaml(self):
        result = self.invariants.check(
            before_test_count=100,
            after_test_count=100,
            before_ruff_violations=0,
            after_ruff_violations=0,
            files_written=["ouroboros.yaml"],
        )
        assert result.passed is True

    def test_fails_when_root_toml_created(self):
        result = self.invariants.check(
            before_test_count=100,
            after_test_count=100,
            before_ruff_violations=0,
            after_ruff_violations=0,
            files_written=["setup.cfg"],
        )
        assert result.passed is False

    def test_test_file_in_nested_dir_ok(self):
        result = self.invariants.check(
            before_test_count=100,
            after_test_count=100,
            before_ruff_violations=0,
            after_ruff_violations=0,
            files_written=["ouroboros/agents/observer.py"],
        )
        assert result.passed is True
