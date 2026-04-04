"""Observer agent — reads traces and scoreboard to identify weaknesses."""

from __future__ import annotations

import json

from ouroboros.agents.base import BaseAgent
from ouroboros.types import ObservationReport, ScoreboardSnapshot, TraceEvent

OBSERVER_SYSTEM_PROMPT = """You are the Observer agent in the Ouroboros self-improvement system.

Your job: analyze the current scoreboard and recent trace data to identify the WEAKEST dimension
that has the most room for improvement.

You are READ-ONLY. You never modify code. You produce an Observation Report.

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
    def __init__(self, model: str = "claude-sonnet-4-6", system_prompt: str = "") -> None:
        self.agent = BaseAgent(model=model, role="observer", timeout_seconds=120)
        self.system_prompt = system_prompt or OBSERVER_SYSTEM_PROMPT

    def observe(
        self,
        scoreboard: ScoreboardSnapshot,
        traces: list[TraceEvent],
        ledger_summary: str,
    ) -> ObservationReport:
        """Analyze scoreboard and traces, return an ObservationReport."""
        user_prompt = self._build_prompt(scoreboard, traces, ledger_summary)
        response = self.agent.call(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
        )
        data = self.agent.parse_json(response.text)
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
