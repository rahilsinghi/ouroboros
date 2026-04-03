import pytest

from ouroboros.history.dashboard import render_scoreboard_ascii, render_ledger_summary
from ouroboros.types import (
    DimensionScore,
    IterationOutcome,
    LedgerEntry,
    ScoreboardSnapshot,
)


class TestDashboard:
    def test_render_scoreboard(self):
        snap = ScoreboardSnapshot(
            iteration=5,
            dimensions=(
                DimensionScore("correctness", 0.85),
                DimensionScore("tool_selection", 0.72),
                DimensionScore("regression", 1.0),
            ),
        )
        output = render_scoreboard_ascii(snap)
        assert "correctness" in output
        assert "0.85" in output
        assert "tool_selection" in output

    def test_render_empty_scoreboard(self):
        snap = ScoreboardSnapshot(iteration=0, dimensions=())
        output = render_scoreboard_ascii(snap)
        assert "no data" in output.lower() or "empty" in output.lower() or output.strip() != ""

    def test_render_ledger_summary(self):
        entries = [
            LedgerEntry(
                iteration=1, timestamp="t", observation_summary="obs",
                hypothesis="hyp1", files_changed=("a.py",), diff="",
                scoreboard_before=ScoreboardSnapshot(0, ()), scoreboard_after=ScoreboardSnapshot(1, ()),
                outcome=IterationOutcome.MERGED, reason="good",
            ),
            LedgerEntry(
                iteration=2, timestamp="t", observation_summary="obs",
                hypothesis="hyp2", files_changed=("b.py",), diff="",
                scoreboard_before=ScoreboardSnapshot(1, ()), scoreboard_after=ScoreboardSnapshot(2, ()),
                outcome=IterationOutcome.ROLLED_BACK, reason="bad",
            ),
        ]
        output = render_ledger_summary(entries)
        assert "hyp1" in output
        assert "MERGED" in output
        assert "ROLLED_BACK" in output
