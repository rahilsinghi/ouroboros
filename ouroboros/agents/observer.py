"""Observer agent — reads traces and scoreboard to identify weaknesses."""

from __future__ import annotations

import json

from ouroboros.agents.base import BaseAgent
from ouroboros.types import ObservationReport, ScoreboardSnapshot, TraceEvent

OBSERVER_SYSTEM_PROMPT = """You are the Observer agent in the Ouroboros self-improvement system.

Your job: analyze the current scoreboard and recent trace data to identify the WEAKEST dimension
that has the most room for improvement.

You are READ-ONLY. You never modify code. You produce an Observation Report.

## Dimension Reference
- code_quality (0-1): Composite of ruff lint violations (60%) and radon cyclomatic complexity (40%).
  Score 1.0 = zero violations and low complexity. Each ruff violation costs 0.1 points.
  To improve: fix specific ruff violations or reduce function complexity.

- correctness (0-1): Fraction of tests passing. Score = passed / total.
  To improve: fix failing tests or add missing functionality that tests expect.

- efficiency (0-1): Source code size vs baseline. Smaller = better.
  To improve: remove dead code, simplify implementations.

- regression (0-1): Previously-passing tests still passing. Score 1.0 = no regressions.
  DO NOT target this dimension — it measures side effects, not direct improvements.

- tool_selection (0-1): Routing accuracy (currently placeholder at 1.0). Skip.

- real_world (0-1): LLM-graded quality (currently placeholder at 0.5). Skip.

## Strategy
Focus on dimensions with real scores below 0.8. Prefer code_quality and correctness
as they have the most actionable improvements. Never target placeholders (tool_selection, real_world).

Respond with a JSON object:
{
  "weakest_dimension": "<dimension name>",
  "current_score": <float 0-1>,
  "failure_examples": ["<specific example 1>", "<specific example 2>", ...],
  "patterns": ["<pattern 1>", "<pattern 2>", ...]
}

Be specific in failure examples — include the prompt, what happened, and what should have happened.
Be specific in patterns — identify what categories of inputs fail and why."""


class ObserverAgent:
    def __init__(self, model: str = "claude-sonnet-4-6") -> None:
        self.agent = BaseAgent(model=model, role="observer", timeout_seconds=120)

    def observe(
        self,
        scoreboard: ScoreboardSnapshot,
        traces: list[TraceEvent],
        ledger_summary: str,
    ) -> ObservationReport:
        """Analyze scoreboard and traces, return an ObservationReport."""
        user_prompt = self._build_prompt(scoreboard, traces, ledger_summary)
        data = self.agent.call_with_json_retry(
            system_prompt=OBSERVER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        return ObservationReport(
            weakest_dimension=data["weakest_dimension"],
            current_score=data["current_score"],
            failure_examples=tuple(data["failure_examples"]),
            patterns=tuple(data["patterns"]),
        )

    def _build_prompt(
        self,
        scoreboard: ScoreboardSnapshot,
        traces: list[TraceEvent],
        ledger_summary: str,
    ) -> str:
        score_lines = "\n".join(
            f"  {d.name}: {d.value:.2f}" for d in scoreboard.dimensions
        )
        trace_lines = "\n".join(
            json.dumps({"type": t.event_type, **t.data})
            for t in traces[-20:]  # last 20 traces
        )
        return (
            f"## Current Scoreboard\n{score_lines}\n\n"
            f"## Recent Traces (last 20)\n{trace_lines}\n\n"
            f"## Improvement History\n{ledger_summary}\n\n"
            "Identify the weakest dimension and provide specific failure examples and patterns."
        )
