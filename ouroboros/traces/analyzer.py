"""Trace analysis — pattern detection across runs."""

from __future__ import annotations

from dataclasses import dataclass

from ouroboros.types import TraceEvent


@dataclass(frozen=True)
class TraceSummary:
    total_runs: int
    avg_tokens: float
    avg_duration_ms: float
    tool_frequency: dict[str, int]


class TraceAnalyzer:
    def summarize(self, traces: list[TraceEvent]) -> TraceSummary:
        """Produce aggregate statistics from trace events."""
        cli_runs = [t for t in traces if t.event_type == "cli_run"]

        if not cli_runs:
            return TraceSummary(total_runs=0, avg_tokens=0.0, avg_duration_ms=0.0, tool_frequency={})

        total_tokens = sum(t.data.get("tokens_used", 0) for t in cli_runs)
        total_duration = sum(t.data.get("duration_ms", 0) for t in cli_runs)

        tool_freq: dict[str, int] = {}
        for t in cli_runs:
            stdout = str(t.data.get("stdout", ""))
            if "Routed to:" in stdout:
                tool = stdout.split("Routed to:")[1].strip().split()[0]
                tool_freq[tool] = tool_freq.get(tool, 0) + 1

        return TraceSummary(
            total_runs=len(cli_runs),
            avg_tokens=total_tokens / len(cli_runs),
            avg_duration_ms=total_duration / len(cli_runs),
            tool_frequency=tool_freq,
        )
