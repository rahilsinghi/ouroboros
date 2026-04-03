# tests/ouroboros/test_scoreboard_code_quality.py
import tempfile
from pathlib import Path

import pytest

from ouroboros.scoreboard.code_quality import CodeQualityScorer


@pytest.fixture
def clean_python_dir(tmp_path: Path) -> Path:
    """Create a directory with clean Python code."""
    (tmp_path / "clean.py").write_text(
        'def greet(name: str) -> str:\n    return f"Hello, {name}"\n'
    )
    return tmp_path


@pytest.fixture
def messy_python_dir(tmp_path: Path) -> Path:
    """Create a directory with messy Python code."""
    (tmp_path / "messy.py").write_text(
        "import os, sys, json\n"
        "def f(x,y,z,a,b,c,d,e,f,g):\n"
        "  if x:\n"
        "    if y:\n"
        "      if z:\n"
        "        if a:\n"
        "          if b:\n"
        "            return c\n"
        "  return None\n"
    )
    return tmp_path


class TestCodeQualityScorer:
    def test_clean_code_scores_high(self, clean_python_dir: Path):
        scorer = CodeQualityScorer(target_path=clean_python_dir)
        score = scorer.score()
        assert score.name == "code_quality"
        assert score.value >= 0.8

    def test_messy_code_scores_lower(self, messy_python_dir: Path):
        scorer = CodeQualityScorer(target_path=messy_python_dir)
        score = scorer.score()
        assert score.value < 0.8

    def test_empty_dir_scores_perfect(self, tmp_path: Path):
        scorer = CodeQualityScorer(target_path=tmp_path)
        score = scorer.score()
        assert score.value == 1.0

    def test_complexity_score_uses_all_functions(self, clean_python_dir: Path):
        """Verify complexity averaging includes all functions, not just C+ grade."""
        scorer = CodeQualityScorer(target_path=clean_python_dir)
        score = scorer._complexity_score()
        # Simple functions should score 1.0 (avg CC < 5)
        assert score == 1.0, (
            f"Low-complexity code should get 1.0, got {score}. "
            "Likely averaging only high-complexity functions."
        )
