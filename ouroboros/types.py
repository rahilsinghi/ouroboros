"""Shared dataclasses for the Ouroboros improvement engine."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum


class IterationOutcome(str, Enum):
    MERGED = "MERGED"
    ROLLED_BACK = "ROLLED_BACK"
    TIMEOUT = "TIMEOUT"
    EVAL_FAILURE = "EVAL_FAILURE"
    ABANDONED = "ABANDONED"


@dataclass(frozen=True)
class DimensionScore:
    name: str
    value: float

    def __post_init__(self) -> None:
        clamped = max(0.0, min(1.0, self.value))
        if clamped != self.value:
            object.__setattr__(self, "value", clamped)


@dataclass(frozen=True)
class ScoreboardSnapshot:
    iteration: int
    dimensions: tuple[DimensionScore, ...]
    timestamp: str = ""

    def get(self, name: str) -> DimensionScore | None:
        for dim in self.dimensions:
            if dim.name == name:
                return dim
        return None

    def to_json(self) -> str:
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
    event_type: str
    timestamp: str
    data: dict[str, object]

    def to_jsonl_line(self) -> str:
        return json.dumps(
            {
                "event_type": self.event_type,
                "timestamp": self.timestamp,
                **self.data,
            }
        )


@dataclass(frozen=True)
class ObservationReport:
    weakest_dimension: str
    current_score: float
    failure_examples: tuple[str, ...]
    patterns: tuple[str, ...]


@dataclass(frozen=True)
class FileChange:
    path: str
    action: str
    description: str


@dataclass(frozen=True)
class ChangePlan:
    hypothesis: str
    target_dimension: str
    file_changes: tuple[FileChange, ...]
    expected_impact: str


@dataclass(frozen=True)
class LedgerEntry:
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
