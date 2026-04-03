import pytest

from ouroboros.traces.analyzer import TraceAnalyzer
from ouroboros.types import TraceEvent


class TestTraceAnalyzer:
    def test_identify_routing_failures(self):
        traces = [
            TraceEvent("cli_run", "t1", {"prompt": "list files", "stdout": "Routed to: GrepTool", "returncode": 0, "tokens_used": 100, "duration_ms": 500}),
            TraceEvent("cli_run", "t2", {"prompt": "read file", "stdout": "Routed to: BashTool", "returncode": 0, "tokens_used": 120, "duration_ms": 600}),
            TraceEvent("cli_run", "t3", {"prompt": "search code", "stdout": "Routed to: GrepTool", "returncode": 0, "tokens_used": 80, "duration_ms": 400}),
        ]
        analyzer = TraceAnalyzer()
        summary = analyzer.summarize(traces)
        assert summary.total_runs == 3
        assert summary.avg_tokens > 0
        assert summary.avg_duration_ms > 0

    def test_empty_traces(self):
        analyzer = TraceAnalyzer()
        summary = analyzer.summarize([])
        assert summary.total_runs == 0
