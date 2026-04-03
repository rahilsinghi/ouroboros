import json
from pathlib import Path
import pytest
from ouroboros.scoreboard.tool_selection import ToolSelectionScorer, RoutingChallenge


@pytest.fixture
def challenges_path(tmp_path: Path) -> Path:
    challenges = [
        {"prompt": "list files", "expected_tool": "BashTool", "distractors": ["FileReadTool"], "category": "filesystem"},
        {"prompt": "read config.json", "expected_tool": "FileReadTool", "distractors": ["BashTool"], "category": "filesystem"},
        {"prompt": "search for TODO", "expected_tool": "GrepTool", "distractors": ["BashTool"], "category": "search"},
    ]
    path = tmp_path / "challenges.json"
    path.write_text(json.dumps(challenges))
    return path


class TestToolSelectionScorer:
    def test_load_challenges(self, challenges_path: Path):
        scorer = ToolSelectionScorer(challenges_path=challenges_path)
        assert len(scorer.challenges) == 3

    def test_score_perfect(self, challenges_path: Path):
        scorer = ToolSelectionScorer(challenges_path=challenges_path)
        results = {"list files": "BashTool", "read config.json": "FileReadTool", "search for TODO": "GrepTool"}
        score = scorer.score(results)
        assert score.value == 1.0
        assert score.name == "tool_selection"

    def test_score_partial(self, challenges_path: Path):
        scorer = ToolSelectionScorer(challenges_path=challenges_path)
        results = {"list files": "BashTool", "read config.json": "BashTool", "search for TODO": "GrepTool"}
        score = scorer.score(results)
        assert abs(score.value - 2.0 / 3.0) < 0.01

    def test_score_zero(self, challenges_path: Path):
        scorer = ToolSelectionScorer(challenges_path=challenges_path)
        results = {"list files": "GrepTool", "read config.json": "GrepTool", "search for TODO": "BashTool"}
        score = scorer.score(results)
        assert score.value == 0.0

    def test_missing_prompt_counted_as_failure(self, challenges_path: Path):
        scorer = ToolSelectionScorer(challenges_path=challenges_path)
        results = {"list files": "BashTool"}
        score = scorer.score(results)
        assert abs(score.value - 1.0 / 3.0) < 0.01
