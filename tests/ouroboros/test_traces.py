import json
from pathlib import Path
import pytest
from ouroboros.types import TraceEvent
from ouroboros.traces.store import TraceStore
from ouroboros.traces.collector import TraceCollector

@pytest.fixture
def trace_dir(tmp_path: Path) -> Path:
    return tmp_path / ".ouroboros" / "traces"

class TestTraceStore:
    def test_write_and_read_events(self, trace_dir: Path):
        store = TraceStore(base_dir=trace_dir)
        run_id = "run-001"
        events = [
            TraceEvent(event_type="tool_call", timestamp="2026-04-02T00:00:00Z", data={"tool": "BashTool"}),
            TraceEvent(event_type="decision", timestamp="2026-04-02T00:00:01Z", data={"choice": "route"}),
        ]
        store.write_events(run_id, events)
        loaded = store.read_events(run_id)
        assert len(loaded) == 2
        assert loaded[0].event_type == "tool_call"
        assert loaded[1].event_type == "decision"

    def test_list_runs(self, trace_dir: Path):
        store = TraceStore(base_dir=trace_dir)
        store.write_events("run-001", [TraceEvent("a", "t", {})])
        store.write_events("run-002", [TraceEvent("b", "t", {})])
        runs = store.list_runs()
        assert "run-001" in runs
        assert "run-002" in runs

    def test_read_nonexistent_run(self, trace_dir: Path):
        store = TraceStore(base_dir=trace_dir)
        events = store.read_events("nonexistent")
        assert events == []

class TestTraceCollector:
    def test_collect_from_cli_output(self, trace_dir: Path):
        collector = TraceCollector(store=TraceStore(base_dir=trace_dir))
        cli_stdout = "Routed to: BashTool (score=5)"
        run_id = collector.collect_run(
            prompt="show me the workspace",
            cli_command="python -m src.main route 'show me the workspace'",
            stdout=cli_stdout, stderr="", returncode=0, duration_ms=1200, tokens_used=150,
        )
        assert run_id.startswith("run-")
        events = collector.store.read_events(run_id)
        assert len(events) >= 1
        assert events[0].event_type == "cli_run"
