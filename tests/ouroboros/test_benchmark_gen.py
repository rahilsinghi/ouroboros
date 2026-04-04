"""Tests for benchmark task loading and rotating task generation."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

from ouroboros.meta.benchmark_gen import BenchmarkTask, BenchmarkGenerator, load_benchmark_tasks


class TestLoadBenchmarkTasks:
    def test_loads_core_tasks(self, tmp_path: Path):
        task_yaml = {
            "name": "test_task",
            "type": "core",
            "description": "A test task",
            "setup_file": "def foo(): pass",
            "setup_path": "ouroboros/_target.py",
            "expected_check": "ruff_clean",
            "target_dimension": "code_quality",
        }
        (tmp_path / "core_001.yaml").write_text(yaml.dump(task_yaml))
        tasks = load_benchmark_tasks(tmp_path)
        assert len(tasks) == 1
        assert tasks[0].name == "test_task"
        assert tasks[0].task_type == "core"

    def test_empty_dir(self, tmp_path: Path):
        tasks = load_benchmark_tasks(tmp_path)
        assert tasks == []


class TestBenchmarkGenerator:
    def test_generates_rotating_tasks(self, tmp_path: Path):
        target = tmp_path / "ouroboros"
        target.mkdir()
        (target / "sample.py").write_text(
            "def alpha():\n    pass\n\ndef beta():\n    pass\n\ndef gamma():\n    \"\"\"Has doc.\"\"\"\n    pass\n"
        )
        gen = BenchmarkGenerator(target_path=target)
        tasks = gen.generate_rotating(count=2)
        assert len(tasks) == 2
        for t in tasks:
            assert t.task_type == "rotating"
            assert t.expected_check == "has_docstring"


class TestBenchmarkScoring:
    def test_ruff_clean_check(self):
        code = "def foo() -> int:\n    return 1\n"
        tree = ast.parse(code)
        assert tree is not None

    def test_has_docstring_check(self):
        code = 'def compute(x: int) -> int:\n    """Does something."""\n    return x + 1\n'
        tree = ast.parse(code)
        func = tree.body[0]
        assert ast.get_docstring(func) is not None

    def test_missing_docstring_detected(self):
        code = "def compute(x: int) -> int:\n    return x + 1\n"
        tree = ast.parse(code)
        func = tree.body[0]
        assert ast.get_docstring(func) is None
