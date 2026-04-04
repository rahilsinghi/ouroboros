"""Tests for the full scoreboard runner (all 6 dimensions)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from ouroboros.scoreboard.runner import _run_tests, run_scoreboard


@pytest.fixture
def python_project(tmp_path: Path) -> Path:
    """Create a minimal Python project with a test."""
    (tmp_path / "clean.py").write_text(
        'def add(a: int, b: int) -> int:\n    return a + b\n'
    )
    return tmp_path


class TestRunScoreboard:
    def test_returns_all_6_dimensions(self, python_project: Path):
        snapshot = run_scoreboard(target_path=python_project, iteration=1)
        assert len(snapshot.dimensions) == 6
        names = {d.name for d in snapshot.dimensions}
        assert names == {
            "code_quality",
            "correctness",
            "efficiency",
            "regression",
            "tool_selection",
            "real_world",
        }

    def test_all_scores_in_valid_range(self, python_project: Path):
        snapshot = run_scoreboard(target_path=python_project, iteration=1)
        for dim in snapshot.dimensions:
            assert 0.0 <= dim.value <= 1.0, f"{dim.name} out of range: {dim.value}"

    def test_run_tests_uses_configured_test_command(self, python_project: Path):
        """_run_tests must invoke the provided test_command, not a hardcoded one."""
        import shlex
        import sys

        with patch("ouroboros.scoreboard.runner.subprocess.run") as mock_run:
            mock_run.return_value.stdout = "test_foo PASSED\n"
            mock_run.return_value.returncode = 0

            custom_cmd = f"python -m pytest {python_project}/custom_tests -v"
            _run_tests(python_project, custom_cmd)

            called_args = mock_run.call_args
            cmd_list = called_args[0][0] if called_args[0] else called_args[1]["args"]
            # -v/--verbose flags are stripped before appending -q to avoid conflicts.
            # "python" is resolved to sys.executable so venv tools are found.
            expected = [
                p for p in shlex.split(custom_cmd) if p not in ("-v", "--verbose")
            ] + ["--tb=no", "-q"]
            # Replace bare "python" with sys.executable to match runner behavior
            expected = [sys.executable if p in ("python", "python3") else p for p in expected]
            assert cmd_list == expected, (
                f"Expected command to use configured test_command, got: {cmd_list}"
            )

    def test_correctness_nonzero_with_passing_tests(self, python_project: Path):
        """When a real test file exists and passes, correctness > 0."""
        test_dir = python_project / "tests"
        test_dir.mkdir()
        # Use a self-contained test that doesn't need imports
        (test_dir / "test_simple.py").write_text(
            "def test_math():\n    assert 1 + 1 == 2\n"
        )
        snapshot = run_scoreboard(
            target_path=python_project,
            iteration=1,
            test_command=f"python -m pytest {test_dir} -v",
        )
        cq = snapshot.get("correctness")
        assert cq is not None
        assert cq.value > 0.0, f"correctness should be > 0 with passing test, got {cq.value}"

    def test_empty_dir_scores(self, tmp_path: Path):
        snapshot = run_scoreboard(target_path=tmp_path, iteration=0)
        assert len(snapshot.dimensions) == 6
        # code_quality should be 1.0 for empty dir
        cq = snapshot.get("code_quality")
        assert cq is not None
        assert cq.value == 1.0
