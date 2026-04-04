"""Telemetry record dataclass for iteration archive."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentTokens:
    """Per-agent token usage and cost."""

    input: int
    output: int
    cost_usd: float


@dataclass(frozen=True)
class TelemetryRecord:
    """Complete record of a single inner-loop iteration."""

    run_id: str
    iteration: int
    timestamp: str

    prompt_observer: str
    prompt_strategist: str
    prompt_implementer: str

    observer_output: str
    strategist_output: str
    implementer_output: str

    tokens_observer: AgentTokens
    tokens_strategist: AgentTokens
    tokens_implementer: AgentTokens

    files_changed: tuple[str, ...]
    git_diff: str
    eval_score: float
    outcome: str
    failure_reason: str
    traceback_output: str

    cost_usd: float
    input_tokens: int
    output_tokens: int

    def to_frontmatter(self) -> dict:
        """Return flat dict suitable for YAML frontmatter."""
        return {
            "run_id": self.run_id,
            "iteration": self.iteration,
            "outcome": self.outcome,
            "eval_score": self.eval_score,
            "prompt_observer": self.prompt_observer,
            "prompt_strategist": self.prompt_strategist,
            "prompt_implementer": self.prompt_implementer,
            "tokens_observer_in": self.tokens_observer.input,
            "tokens_observer_out": self.tokens_observer.output,
            "cost_observer": self.tokens_observer.cost_usd,
            "tokens_strategist_in": self.tokens_strategist.input,
            "tokens_strategist_out": self.tokens_strategist.output,
            "cost_strategist": self.tokens_strategist.cost_usd,
            "tokens_implementer_in": self.tokens_implementer.input,
            "tokens_implementer_out": self.tokens_implementer.output,
            "cost_implementer": self.tokens_implementer.cost_usd,
            "cost_usd": self.cost_usd,
            "tokens_in": self.input_tokens,
            "tokens_out": self.output_tokens,
            "failure_reason": self.failure_reason,
        }

    def to_markdown_body(self) -> str:
        """Return the markdown body (cognitive traces, diff, traceback)."""
        sections = [
            f"## Observation\n{self.observer_output}",
            f"## Strategy\n{self.strategist_output}",
            f"## Implementation\n{self.implementer_output}",
            f"## Diff\n{self.git_diff}" if self.git_diff else "## Diff\n(no diff)",
            f"## Traceback\n{self.traceback_output}" if self.traceback_output else "## Traceback\n(none)",
            f"## Result\n{self.outcome}. eval_score={self.eval_score:.4f}. {self.failure_reason}",
        ]
        return "\n\n".join(sections)
