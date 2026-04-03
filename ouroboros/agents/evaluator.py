"""Evaluator agent — runs scoreboard and makes merge/rollback decisions."""

from __future__ import annotations

from enum import Enum

from ouroboros.config import OuroborosConfig
from ouroboros.scoreboard.runner import MergeGate
from ouroboros.types import ScoreboardSnapshot


class EvalDecision(str, Enum):
    MERGE = "MERGE"
    ROLLBACK = "ROLLBACK"


class EvaluatorAgent:
    def __init__(self, config: OuroborosConfig) -> None:
        self.gate = MergeGate(
            regression_floor=config.merge_gate_regression_floor,
            noise_tolerance=config.merge_gate_noise_tolerance,
        )

    def decide(
        self,
        before: ScoreboardSnapshot,
        after: ScoreboardSnapshot,
    ) -> EvalDecision:
        """Compare before/after scoreboard snapshots and decide merge or rollback."""
        if self.gate.can_merge(before, after):
            return EvalDecision.MERGE
        return EvalDecision.ROLLBACK
