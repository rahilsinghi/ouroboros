"""Shared dataclasses for the Ouroboros improvement engine."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum


class IterationOutcome(str, Enum):
    """Outcome of a single improvement iteration attempt."""

    MERGED = "MERGED"
    ROLLED_BACK = "ROLLED_BACK"
    TIMEOUT = "TIMEOUT"
    EVAL_FAILURE = "EVAL_FAILURE"
    ABANDONED = "ABANDONED"


@dataclass(frozen=True)
class DimensionScore:
    """A scored dimension with name and normalized value between 0.0 and 1.0."""

    name: str
    value: float

    def __post_init__(self) -> None:
        """Validate that value is between 0.0 and 1.0."""
        clamped = max(0.0, min(1.0, self.value))
        if clamped != self.value:
            object.__setattr__(self, "value", clamped)


@dataclass(frozen=True)
class ScoreboardSnapshot:
    """A snapshot of all dimension scores at a specific iteration."""

    iteration: int
    dimensions: tuple[DimensionScore, ...]
    timestamp: str = ""

    def get(self, name: str) -> DimensionScore | None:
        """Return the DimensionScore for the named dimension, or None if not found."""
        for dim in self.dimensions:
            if dim.name == name:
                return dim
        return None

    def to_json(self) -> str:
        """Serialize this snapshot to a JSON-compatible dict."""
        return json.dumps(
            {
                "iteration": self.iteration,
                "timestamp": self.timestamp,
                "dimensions": [
                    {"name": d.name, "value": d.value} for d in self.dimensions
                ],
            },
            indent=2,
        )


@dataclass(frozen=True)
class TraceEvent:
    """A single recorded event from an agent run for trace analysis."""

    event_type: str
    timestamp: str
    data: dict[str, object]

    def to_jsonl_line(self) -> str:
        """Serialize this event to a JSONL-formatted string."""
        return json.dumps(
            {
                "event_type": self.event_type,
                "timestamp": self.timestamp,
                **self.data,
            }
        )


@dataclass(frozen=True)
class ObservationReport:
    """Report produced by the Observer agent identifying the weakest dimension."""

    weakest_dimension: str
    current_score: float
    failure_examples: tuple[str, ...]
    patterns: tuple[str, ...]


@dataclass(frozen=True)
class FileChange:
    """A single file modification specified in a change plan."""

    path: str
    action: str
    description: str


@dataclass(frozen=True)
class ChangePlan:
    """A complete plan produced by the Strategist agent with hypothesis and file changes."""

    hypothesis: str
    target_dimension: str
    file_changes: tuple[FileChange, ...]
    expected_impact: str


@dataclass(frozen=True)
class LedgerEntry:
    """A permanent record of a single improvement iteration attempt and its outcome."""

    iteration: int
    timestamp: str
    observation_summary: str
    hypothesis: str
    files_changed: tuple[str, ...]
    diff: str
    scoreboard_before: ScoreboardSnapshot
    scoreboard_after: ScoreboardSnapshot
    outcome: IterationOutcome
    reason: str
