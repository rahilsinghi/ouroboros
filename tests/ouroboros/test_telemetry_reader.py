"""Tests for TelemetryReader."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ouroboros.telemetry.reader import TelemetryReader
from ouroboros.telemetry.types import AgentTokens, TelemetryRecord
from ouroboros.telemetry.writer import TelemetryWriter


def _make_record(
    run_id: str,
    iteration: int,
    outcome: str = "MERGED",
    eval_score: float = 0.1,
    prompt_impl: str = "v1",
) -> TelemetryRecord:
    return TelemetryRecord(
        run_id=run_id,
        iteration=iteration,
        timestamp="2026-04-03T14:00:00Z",
        prompt_observer="v1",
        prompt_strategist="v1",
        prompt_implementer=prompt_impl,
        observer_output="{}",
        strategist_output="{}",
        implementer_output="{}",
        tokens_observer=AgentTokens(input=100, output=50, cost_usd=0.001),
        tokens_strategist=AgentTokens(input=200, output=100, cost_usd=0.002),
        tokens_implementer=AgentTokens(input=300, output=150, cost_usd=0.005),
        files_changed=(),
        git_diff="",
        eval_score=eval_score,
        outcome=outcome,
        failure_reason="failed" if outcome != "MERGED" else "",
        traceback_output="",
        cost_usd=0.008,
        input_tokens=600,
        output_tokens=300,
    )


@pytest.fixture
def populated_archive(tmp_path: Path) -> Path:
    writer = TelemetryWriter(archive_dir=tmp_path)
    writer.write(_make_record("r1", 1, "MERGED", 0.12, "v1"))
    writer.write(_make_record("r2", 2, "ABANDONED", 0.0, "v1"))
    writer.write(_make_record("r3", 3, "ROLLED_BACK", 0.01, "v1"))
    writer.write(_make_record("r4", 4, "MERGED", 0.08, "v2"))
    writer.write(_make_record("r5", 5, "ABANDONED", 0.0, "v2"))
    return tmp_path


class TestTelemetryReader:
    def test_get_failures_returns_lowest_scoring(self, populated_archive: Path):
        reader = TelemetryReader(archive_dir=populated_archive)
        failures = reader.get_failures(limit=3)
        assert len(failures) == 3
        assert failures[0]["eval_score"] <= failures[1]["eval_score"]

    def test_get_failures_filters_by_prompt_version(self, populated_archive: Path):
        reader = TelemetryReader(archive_dir=populated_archive)
        failures = reader.get_failures(prompt_version="v2", limit=10)
        for f in failures:
            assert f["prompt_implementer"] == "v2"

    def test_get_by_prompt_version(self, populated_archive: Path):
        reader = TelemetryReader(archive_dir=populated_archive)
        records = reader.get_by_prompt_version(agent="implementer", version="v1")
        assert len(records) == 3
        for r in records:
            assert r["prompt_implementer"] == "v1"

    def test_get_summary(self, populated_archive: Path):
        reader = TelemetryReader(archive_dir=populated_archive)
        summary = reader.get_summary()
        assert "v1" in summary
        assert "v2" in summary
        assert summary["v1"]["total"] == 3
        assert summary["v1"]["merged"] == 1
        assert summary["v2"]["total"] == 2

    def test_empty_archive(self, tmp_path: Path):
        reader = TelemetryReader(archive_dir=tmp_path)
        assert reader.get_failures(limit=5) == []
        assert reader.get_summary() == {}

    def test_read_full_record(self, populated_archive: Path):
        reader = TelemetryReader(archive_dir=populated_archive)
        body = reader.read_full_record("r1")
        assert "## Observation" in body
