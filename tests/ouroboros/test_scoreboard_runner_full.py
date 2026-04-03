"""Tests for the full scoreboard runner (all 6 dimensions)."""

from pathlib import Path

import pytest

from ouroboros.scoreboard.runner import run_scoreboard


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

    def test_empty_dir_scores(self, tmp_path: Path):
        snapshot = run_scoreboard(target_path=tmp_path, iteration=0)
        assert len(snapshot.dimensions) == 6
        # code_quality should be 1.0 for empty dir
        cq = snapshot.get("code_quality")
        assert cq is not None
        assert cq.value == 1.0
