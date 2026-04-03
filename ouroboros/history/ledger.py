# ouroboros/history/ledger.py
"""Improvement ledger — permanent record of every iteration attempt."""

from __future__ import annotations

import json
from pathlib import Path

from ouroboros.types import (
    DimensionScore,
    IterationOutcome,
    LedgerEntry,
    ScoreboardSnapshot,
)


class Ledger:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.ledger_file = base_dir / "ledger.jsonl"

    def append(self, entry: LedgerEntry) -> None:
        """Append an iteration record to the ledger."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        with open(self.ledger_file, "a") as f:
            f.write(json.dumps(self._serialize(entry)) + "\n")

    def read_all(self) -> list[LedgerEntry]:
        """Read all ledger entries."""
        if not self.ledger_file.exists():
            return []
        entries: list[LedgerEntry] = []
        with open(self.ledger_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(self._deserialize(json.loads(line)))
        return entries

    def read_by_outcome(self, outcome: IterationOutcome) -> list[LedgerEntry]:
        """Filter entries by outcome."""
        return [e for e in self.read_all() if e.outcome == outcome]

    def latest_iteration(self) -> int:
        """Get the highest iteration number, or 0 if empty."""
        entries = self.read_all()
        if not entries:
            return 0
        return max(e.iteration for e in entries)

    def _serialize(self, entry: LedgerEntry) -> dict:
        return {
            "iteration": entry.iteration,
            "timestamp": entry.timestamp,
            "observation_summary": entry.observation_summary,
            "hypothesis": entry.hypothesis,
            "files_changed": list(entry.files_changed),
            "diff": entry.diff,
            "scoreboard_before": self._serialize_snapshot(entry.scoreboard_before),
            "scoreboard_after": self._serialize_snapshot(entry.scoreboard_after),
            "outcome": entry.outcome.value,
            "reason": entry.reason,
        }

    def _serialize_snapshot(self, snap: ScoreboardSnapshot) -> dict:
        return {
            "iteration": snap.iteration,
            "timestamp": snap.timestamp,
            "dimensions": [{"name": d.name, "value": d.value} for d in snap.dimensions],
        }

    def _deserialize(self, data: dict) -> LedgerEntry:
        return LedgerEntry(
            iteration=data["iteration"],
            timestamp=data["timestamp"],
            observation_summary=data["observation_summary"],
            hypothesis=data["hypothesis"],
            files_changed=tuple(data["files_changed"]),
            diff=data["diff"],
            scoreboard_before=self._deserialize_snapshot(data["scoreboard_before"]),
            scoreboard_after=self._deserialize_snapshot(data["scoreboard_after"]),
            outcome=IterationOutcome(data["outcome"]),
            reason=data["reason"],
        )

    def _deserialize_snapshot(self, data: dict) -> ScoreboardSnapshot:
        return ScoreboardSnapshot(
            iteration=data["iteration"],
            timestamp=data.get("timestamp", ""),
            dimensions=tuple(
                DimensionScore(name=d["name"], value=d["value"])
                for d in data["dimensions"]
            ),
        )
