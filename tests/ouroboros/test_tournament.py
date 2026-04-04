"""Tests for Tournament benchmark runner."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ouroboros.meta.benchmark_gen import BenchmarkTask
from ouroboros.meta.tournament import score_task_result


class TestScoreTaskResult:
    def test_ruff_clean_scores_1(self):
        code = "def foo() -> int:\n    return 1\n"
        score = score_task_result(code, "ruff_clean", "")
        assert score == 1.0

    def test_ruff_violation_scores_0(self):
        code = "def foo() -> int:\n    unused = 1\n    return 1\n"
        score = score_task_result(code, "ruff_clean", "")
        assert score <= 0.5

    def test_has_docstring_scores_1(self):
        code = 'def compute(x):\n    """Does math."""\n    return x\n'
        score = score_task_result(code, "has_docstring", "compute")
        assert score == 1.0

    def test_missing_docstring_scores_0(self):
        code = "def compute(x):\n    return x\n"
        score = score_task_result(code, "has_docstring", "compute")
        assert score == 0.0

    def test_syntax_error_scores_0(self):
        code = "def compute(x:\n    return x\n"
        score = score_task_result(code, "has_docstring", "compute")
        assert score == 0.0

    def test_low_complexity_simple_function(self):
        code = "def process(x):\n    return x + 1\n"
        score = score_task_result(code, "low_complexity", "process")
        assert score == 1.0
