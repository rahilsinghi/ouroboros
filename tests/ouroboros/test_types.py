import json
from datetime import datetime, timezone

import pytest

from ouroboros.types import (
    DimensionScore,
    ScoreboardSnapshot,
    ObservationReport,
    ChangePlan,
    FileChange,
    LedgerEntry,
    IterationOutcome,
    TraceEvent,
)


class TestDimensionScore:
    def test_clamps_to_zero_one(self):
        assert DimensionScore(name="test", value=1.5).value == 1.0
        assert DimensionScore(name="test", value=-0.3).value == 0.0

    def test_normal_value_unchanged(self):
        assert DimensionScore(name="test", value=0.72).value == 0.72


class TestScoreboardSnapshot:
    def test_from_dimensions(self):
        dims = [
            DimensionScore(name="correctness", value=0.8),
            DimensionScore(name="efficiency", value=0.6),
        ]
        snap = ScoreboardSnapshot(iteration=1, dimensions=tuple(dims))
        assert snap.get("correctness").value == 0.8
        assert snap.get("efficiency").value == 0.6
        assert snap.get("nonexistent") is None

    def test_to_json_roundtrip(self):
        dims = [DimensionScore(name="correctness", value=0.8)]
        snap = ScoreboardSnapshot(iteration=1, dimensions=tuple(dims))
        data = json.loads(snap.to_json())
        assert data["iteration"] == 1
        assert data["dimensions"][0]["name"] == "correctness"


class TestObservationReport:
    def test_creation(self):
        report = ObservationReport(
            weakest_dimension="tool_selection",
            current_score=0.65,
            failure_examples=("example1", "example2"),
            patterns=("pattern1",),
        )
        assert report.weakest_dimension == "tool_selection"
        assert len(report.failure_examples) == 2


class TestChangePlan:
    def test_creation(self):
        plan = ChangePlan(
            hypothesis="Improve scoring with TF-IDF",
            target_dimension="tool_selection",
            file_changes=(
                FileChange(path="src/runtime.py", action="modify", description="Update _score()"),
            ),
            expected_impact="routing +10%",
        )
        assert plan.hypothesis == "Improve scoring with TF-IDF"
        assert len(plan.file_changes) == 1


class TestLedgerEntry:
    def test_creation(self):
        entry = LedgerEntry(
            iteration=42,
            timestamp=datetime.now(timezone.utc).isoformat(),
            observation_summary="routing accuracy 68%",
            hypothesis="TF-IDF weighting",
            files_changed=("src/runtime.py",),
            diff="--- a\n+++ b",
            scoreboard_before=ScoreboardSnapshot(
                iteration=41,
                dimensions=(DimensionScore(name="tool_selection", value=0.68),),
            ),
            scoreboard_after=ScoreboardSnapshot(
                iteration=42,
                dimensions=(DimensionScore(name="tool_selection", value=0.74),),
            ),
            outcome=IterationOutcome.MERGED,
            reason="routing +6%, no regressions",
        )
        assert entry.outcome == IterationOutcome.MERGED


class TestTraceEvent:
    def test_creation(self):
        event = TraceEvent(
            event_type="tool_call",
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={"tool": "BashTool", "input": "ls", "output": "file.py"},
        )
        assert event.event_type == "tool_call"

    def test_to_jsonl_line(self):
        event = TraceEvent(
            event_type="decision",
            timestamp="2026-04-02T00:00:00+00:00",
            data={"choice": "route_to_bash"},
        )
        line = event.to_jsonl_line()
        parsed = json.loads(line)
        assert parsed["event_type"] == "decision"
