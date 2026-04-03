"""Core improvement loop — OBSERVE → HYPOTHESIZE → IMPLEMENT → EVALUATE."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ouroboros.agents.evaluator import EvalDecision, EvaluatorAgent
from ouroboros.agents.implementer import ImplementerAgent
from ouroboros.agents.observer import ObserverAgent
from ouroboros.agents.strategist import StrategistAgent
from ouroboros.config import OuroborosConfig
from ouroboros.history.ledger import Ledger
from ouroboros.sandbox.executor import SandboxExecutor
from ouroboros.sandbox.worktree import WorktreeManager
from ouroboros.traces.store import TraceStore
from ouroboros.types import (
    IterationOutcome,
    LedgerEntry,
    ScoreboardSnapshot,
)


@dataclass(frozen=True)
class LoopResult:
    iterations_run: int
    iterations_merged: int
    iterations_rolled_back: int
    total_duration_seconds: float
    stop_reason: str


class ImprovementLoop:
    def __init__(self, config: OuroborosConfig, repo_root: Path) -> None:
        self.config = config
        self.repo_root = repo_root
        self.worktree_mgr = WorktreeManager(repo_root=repo_root)
        self.executor = SandboxExecutor(config=config)
        self.trace_store = TraceStore(base_dir=repo_root / ".ouroboros" / "traces")
        self.ledger = Ledger(base_dir=repo_root / ".ouroboros" / "ledger")
        self.evaluator = EvaluatorAgent(config=config)

        self.observer = ObserverAgent(model=config.model_observer)
        self.strategist = StrategistAgent(model=config.model_strategist)
        self.implementer = ImplementerAgent(
            model=config.model_implementer,
            executor=self.executor,
        )

    def run(self) -> LoopResult:
        """Run the improvement loop for up to max_iterations."""
        start_time = time.time()
        merged = 0
        rolled_back = 0
        stop_reason = "completed"

        start_iteration = self.ledger.latest_iteration() + 1

        for i in range(self.config.max_iterations):
            iteration = start_iteration + i
            elapsed = time.time() - start_time

            # Check time budget
            if elapsed > self.config.time_budget_minutes * 60:
                stop_reason = "time_budget_reached"
                break

            outcome = self._run_iteration(iteration)
            if outcome == IterationOutcome.MERGED:
                merged += 1
            else:
                rolled_back += 1

            # Cooldown between iterations
            if i < self.config.max_iterations - 1:
                time.sleep(self.config.cooldown_seconds)

        return LoopResult(
            iterations_run=i + 1,
            iterations_merged=merged,
            iterations_rolled_back=rolled_back,
            total_duration_seconds=time.time() - start_time,
            stop_reason=stop_reason,
        )

    def _run_iteration(self, iteration: int) -> IterationOutcome:
        """Execute one full OBSERVE → HYPOTHESIZE → IMPLEMENT → EVALUATE cycle."""
        now = datetime.now(timezone.utc).isoformat()

        # Step 1: OBSERVE
        baseline = self._run_scoreboard(self.repo_root)
        traces = self.trace_store.read_events(
            self.trace_store.list_runs()[-1] if self.trace_store.list_runs() else ""
        )
        ledger_entries = self.ledger.read_all()
        ledger_summary = self._summarize_ledger(ledger_entries)

        observation = self.observer.observe(
            scoreboard=baseline,
            traces=traces,
            ledger_summary=ledger_summary,
        )

        # Step 2: HYPOTHESIZE
        source_files = self._read_target_files(observation.weakest_dimension)
        plan = self.strategist.strategize(
            observation=observation,
            source_files=source_files,
            ledger_summary=ledger_summary,
        )

        # Step 3: IMPLEMENT
        worktree = self.worktree_mgr.create(iteration=iteration)
        try:
            impl_result = self.implementer.implement(plan=plan, worktree_path=worktree.path)

            if not impl_result.success:
                self.worktree_mgr.rollback(worktree)
                self._log_iteration(
                    iteration, now, observation, plan, baseline, baseline,
                    IterationOutcome.ROLLED_BACK,
                    f"Implementation failed: {impl_result.error}",
                )
                return IterationOutcome.ROLLED_BACK

            # Step 4: EVALUATE
            after = self._run_scoreboard(worktree.path)
            decision = self.evaluator.decide(before=baseline, after=after)
            diff = self.worktree_mgr.get_diff(worktree)

            if decision == EvalDecision.MERGE:
                self.worktree_mgr.merge(worktree)
                self._log_iteration(
                    iteration, now, observation, plan, baseline, after,
                    IterationOutcome.MERGED,
                    self._describe_improvement(baseline, after),
                )
                return IterationOutcome.MERGED
            else:
                self.worktree_mgr.rollback(worktree)
                self._log_iteration(
                    iteration, now, observation, plan, baseline, after,
                    IterationOutcome.ROLLED_BACK,
                    "Merge gate failed — no improvement or regression detected",
                )
                return IterationOutcome.ROLLED_BACK

        except Exception as e:
            try:
                self.worktree_mgr.rollback(worktree)
            except Exception:
                pass
            self._log_iteration(
                iteration, now, observation, plan, baseline, baseline,
                IterationOutcome.ABANDONED,
                f"Exception: {e}",
            )
            return IterationOutcome.ABANDONED

    def _run_scoreboard(self, target_path: Path) -> ScoreboardSnapshot:
        """Run all benchmark dimensions against a target path. Override in tests."""
        from ouroboros.scoreboard.runner import run_scoreboard

        return run_scoreboard(
            target_path=target_path / self.config.target_path,
            iteration=self.ledger.latest_iteration(),
            test_command=self.config.target_test_command,
            previously_passing=self._get_previously_passing(),
        )

    def _get_previously_passing(self) -> set[str]:
        """Get test names that passed in the most recent merged iteration."""
        entries = self.ledger.read_all()
        for entry in reversed(entries):
            if entry.outcome == IterationOutcome.MERGED:
                # Extract passing tests from the after scoreboard
                correctness = entry.scoreboard_after.get("correctness")
                if correctness and correctness.value > 0:
                    # We don't store individual test names in the snapshot,
                    # so return empty set — regression scorer treats this as "no history"
                    return set()
        return set()

    def _read_target_files(self, dimension: str) -> dict[str, str]:
        """Read relevant source files based on the dimension being targeted."""
        target_dir = self.repo_root / self.config.target_path
        files: dict[str, str] = {}
        if not target_dir.exists():
            return files
        for py_file in sorted(target_dir.rglob("*.py")):
            relative = py_file.relative_to(self.repo_root)
            try:
                content = py_file.read_text()
                # Skip very large files and __pycache__
                if len(content) < 10_000 and "__pycache__" not in str(py_file):
                    files[str(relative)] = content
            except (OSError, UnicodeDecodeError):
                continue
            # Cap at 20 files to stay within LLM context
            if len(files) >= 20:
                break
        return files

    def _summarize_ledger(self, entries: list) -> str:
        if not entries:
            return "No previous iterations."
        lines = []
        for e in entries[-10:]:  # last 10 entries
            lines.append(f"  #{e.iteration} [{e.outcome.value}]: {e.hypothesis} — {e.reason}")
        return "\n".join(lines)

    def _describe_improvement(self, before: ScoreboardSnapshot, after: ScoreboardSnapshot) -> str:
        parts = []
        for ad in after.dimensions:
            bd = before.get(ad.name)
            if bd and ad.value > bd.value:
                delta = ad.value - bd.value
                parts.append(f"{ad.name} +{delta:.2f}")
        return ", ".join(parts) if parts else "marginal improvement"

    def _log_iteration(self, iteration, timestamp, observation, plan, before, after, outcome, reason):
        self.ledger.append(LedgerEntry(
            iteration=iteration,
            timestamp=timestamp,
            observation_summary=f"{observation.weakest_dimension} at {observation.current_score:.2f}",
            hypothesis=plan.hypothesis,
            files_changed=tuple(fc.path for fc in plan.file_changes),
            diff="",
            scoreboard_before=before,
            scoreboard_after=after,
            outcome=outcome,
            reason=reason,
        ))
