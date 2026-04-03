# tests/ouroboros/test_ledger.py
import json
from pathlib import Path

import pytest

from ouroboros.types import (
    DimensionScore,
    IterationOutcome,
    LedgerEntry,
    ScoreboardSnapshot,
)
from ouroboros.history.ledger import Ledger


@pytest.fixture
def ledger_dir(tmp_path: Path) -> Path:
    return tmp_path / ".ouroboros" / "ledger"


class TestLedger:
    def _entry(self, iteration: int, outcome: IterationOutcome) -> LedgerEntry:
        snap = ScoreboardSnapshot(
            iteration=iteration,
            dimensions=(DimensionScore(name="tool_selection", value=0.7),),
        )
        return LedgerEntry(
            iteration=iteration,
            timestamp="2026-04-02T00:00:00Z",
            observation_summary="test obs",
            hypothesis="test hypothesis",
            files_changed=("src/runtime.py",),
            diff="--- a\n+++ b",
            scoreboard_before=snap,
            scoreboard_after=snap,
            outcome=outcome,
            reason="test reason",
        )

    def test_append_and_read(self, ledger_dir: Path):
        ledger = Ledger(base_dir=ledger_dir)
        entry = self._entry(1, IterationOutcome.MERGED)
        ledger.append(entry)
        entries = ledger.read_all()
        assert len(entries) == 1
        assert entries[0].iteration == 1

    def test_multiple_entries(self, ledger_dir: Path):
        ledger = Ledger(base_dir=ledger_dir)
        ledger.append(self._entry(1, IterationOutcome.MERGED))
        ledger.append(self._entry(2, IterationOutcome.ROLLED_BACK))
        ledger.append(self._entry(3, IterationOutcome.MERGED))
        entries = ledger.read_all()
        assert len(entries) == 3

    def test_filter_merged(self, ledger_dir: Path):
        ledger = Ledger(base_dir=ledger_dir)
        ledger.append(self._entry(1, IterationOutcome.MERGED))
        ledger.append(self._entry(2, IterationOutcome.ROLLED_BACK))
        ledger.append(self._entry(3, IterationOutcome.MERGED))
        merged = ledger.read_by_outcome(IterationOutcome.MERGED)
        assert len(merged) == 2

    def test_get_latest_iteration(self, ledger_dir: Path):
        ledger = Ledger(base_dir=ledger_dir)
        assert ledger.latest_iteration() == 0
        ledger.append(self._entry(1, IterationOutcome.MERGED))
        ledger.append(self._entry(2, IterationOutcome.ROLLED_BACK))
        assert ledger.latest_iteration() == 2

    def test_empty_ledger(self, ledger_dir: Path):
        ledger = Ledger(base_dir=ledger_dir)
        assert ledger.read_all() == []
        assert ledger.latest_iteration() == 0
