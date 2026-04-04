"""Tests for TelemetryWriter."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ouroboros.telemetry.types import AgentTokens, TelemetryRecord
from ouroboros.telemetry.writer import TelemetryWriter


def _make_record(run_id: str = "test_001", iteration: int = 1, outcome: str = "MERGED") -> TelemetryRecord:
    return TelemetryRecord(
        run_id=run_id,
        iteration=iteration,
        timestamp="2026-04-03T14:00:00Z",
        prompt_observer="v1",
        prompt_strategist="v1",
        prompt_implementer="v1",
        observer_output="{}",
        strategist_output="{}",
        implementer_output="{}",
        tokens_observer=AgentTokens(input=100, output=50, cost_usd=0.001),
        tokens_strategist=AgentTokens(input=200, output=100, cost_usd=0.002),
        tokens_implementer=AgentTokens(input=300, output=150, cost_usd=0.005),
        files_changed=("a.py",),
        git_diff="diff",
        eval_score=0.12,
        outcome=outcome,
        failure_reason="" if outcome == "MERGED" else "failed",
        traceback_output="",
        cost_usd=0.008,
        input_tokens=600,
        output_tokens=300,
    )


class TestTelemetryWriter:
    def test_writes_markdown_file(self, tmp_path: Path):
        writer = TelemetryWriter(archive_dir=tmp_path)
        record = _make_record()
        path = writer.write(record)
        assert path.exists()
        assert path.suffix == ".md"
        content = path.read_text()
        assert "---" in content
        assert "## Observation" in content

    def test_appends_to_index_jsonl(self, tmp_path: Path):
        writer = TelemetryWriter(archive_dir=tmp_path)
        writer.write(_make_record("run_001", 1))
        writer.write(_make_record("run_002", 2, "ABANDONED"))

        index_path = tmp_path / "index.jsonl"
        assert index_path.exists()
        lines = index_path.read_text().strip().splitlines()
        assert len(lines) == 2

        first = json.loads(lines[0])
        assert first["run_id"] == "run_001"
        assert first["outcome"] == "MERGED"

        second = json.loads(lines[1])
        assert second["run_id"] == "run_002"
        assert second["outcome"] == "ABANDONED"

    def test_frontmatter_is_valid_yaml(self, tmp_path: Path):
        writer = TelemetryWriter(archive_dir=tmp_path)
        path = writer.write(_make_record())
        content = path.read_text()
        parts = content.split("---")
        assert len(parts) >= 3
        import yaml
        frontmatter = yaml.safe_load(parts[1])
        assert frontmatter["run_id"] == "test_001"
        assert frontmatter["outcome"] == "MERGED"
