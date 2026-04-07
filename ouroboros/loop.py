"""Core improvement loop — OBSERVE → HYPOTHESIZE → IMPLEMENT → EVALUATE."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ouroboros.agents.evaluator import EvalDecision, EvaluatorAgent
from ouroboros.agents.implementer import IMPLEMENTER_SYSTEM_PROMPT, ImplementerAgent
from ouroboros.agents.observer import OBSERVER_SYSTEM_PROMPT, ObserverAgent
from ouroboros.agents.strategist import STRATEGIST_SYSTEM_PROMPT, StrategistAgent
from ouroboros.meta.prompt_store import PromptStore
from ouroboros.config import OuroborosConfig
from ouroboros.history.ledger import Ledger
from ouroboros.sandbox.executor import SandboxExecutor
from ouroboros.sandbox.worktree import WorktreeManager
from ouroboros.traces.store import TraceStore
from ouroboros.telemetry.types import AgentTokens, TelemetryRecord
from ouroboros.telemetry.writer import TelemetryWriter
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
    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0


class ImprovementLoop:
    def __init__(self, config: OuroborosConfig, repo_root: Path) -> None:
        self.config = config
        self.repo_root = repo_root
        self.worktree_mgr = WorktreeManager(repo_root=repo_root)
        self.executor = SandboxExecutor(config=config)
        self.trace_store = TraceStore(base_dir=repo_root / ".ouroboros" / "traces")
        self.ledger = Ledger(base_dir=repo_root / ".ouroboros" / "ledger")
        self.evaluator = EvaluatorAgent(config=config)

        self.prompt_store = PromptStore(
            prompts_dir=repo_root / ".ouroboros" / "prompts",
            defaults={
                "observer": OBSERVER_SYSTEM_PROMPT,
                "strategist": STRATEGIST_SYSTEM_PROMPT,
                "implementer": IMPLEMENTER_SYSTEM_PROMPT,
            },
        )

        self.telemetry_writer = TelemetryWriter(
            archive_dir=repo_root / ".ouroboros" / "archive",
        )

        obs_prompt = self.prompt_store.load("observer")
        strat_prompt = self.prompt_store.load("strategist")
        impl_prompt = self.prompt_store.load("implementer")

        self.observer = ObserverAgent(model=config.model_observer, system_prompt=obs_prompt)
        self.strategist = StrategistAgent(model=config.model_strategist, system_prompt=strat_prompt)
        self.implementer = ImplementerAgent(
            model=config.model_implementer,
            executor=self.executor,
            system_prompt=impl_prompt,
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

        # Read final accumulated totals from all agents
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost_usd = 0.0
        for agent in (self.observer, self.strategist, self.implementer):
            tokens = self._read_agent_tokens(agent)
            total_input_tokens += tokens[0]
            total_output_tokens += tokens[1]
            total_cost_usd += tokens[2]

        return LoopResult(
            iterations_run=i + 1,
            iterations_merged=merged,
            iterations_rolled_back=rolled_back,
            total_duration_seconds=time.time() - start_time,
            stop_reason=stop_reason,
            total_cost_usd=total_cost_usd,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
        )

    def _run_iteration(self, iteration: int) -> IterationOutcome:
        """Execute one full OBSERVE → HYPOTHESIZE → IMPLEMENT → EVALUATE cycle."""
        now = datetime.now(timezone.utc).isoformat()
        worktree = None
        obs_tokens = (0, 0, 0.0)
        strat_tokens = (0, 0, 0.0)
        impl_tokens = (0, 0, 0.0)

        try:
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
            obs_tokens = self._read_agent_tokens(self.observer)

            # Step 2: HYPOTHESIZE
            source_files = self._read_target_files(observation.weakest_dimension)
            plan = self.strategist.strategize(
                observation=observation,
                source_files=source_files,
                ledger_summary=ledger_summary,
                blocked_paths=self.config.sandbox_blocked_paths,
            )
            strat_tokens = self._read_agent_tokens(self.strategist)

            # Step 3: IMPLEMENT
            worktree = self.worktree_mgr.create(iteration=iteration)
            impl_result = self.implementer.implement(plan=plan, worktree_path=worktree.path)
            impl_tokens = self._read_agent_tokens(self.implementer)

            if not impl_result.success:
                self.worktree_mgr.rollback(worktree)
                self._log_iteration(
                    iteration, now, observation, plan, baseline, baseline,
                    IterationOutcome.ROLLED_BACK,
                    f"Implementation failed: {impl_result.error}",
                )
                self._write_telemetry(
                    iteration, now, "ROLLED_BACK", 0.0,
                    impl_result.error, "", obs_tokens, strat_tokens, impl_tokens,
                    impl_result.files_written, "",
                )
                return IterationOutcome.ROLLED_BACK

            # Step 3.5: SAFETY INVARIANTS
            from ouroboros.scoreboard.invariants import SafetyInvariants
            invariants = SafetyInvariants()
            invariant_result = invariants.check(
                before_test_count=0,
                after_test_count=0,
                before_ruff_violations=0,
                after_ruff_violations=0,
                files_written=list(impl_result.files_written),
            )

            if not invariant_result.passed:
                self.worktree_mgr.rollback(worktree)
                self._log_iteration(
                    iteration, now, observation, plan, baseline, baseline,
                    IterationOutcome.KILLED,
                    f"Safety invariant violated: {invariant_result.violation}",
                )
                self._write_telemetry(
                    iteration, now, "KILLED", 0.0,
                    invariant_result.violation, "", obs_tokens, strat_tokens, impl_tokens,
                    impl_result.files_written, "",
                )
                return IterationOutcome.KILLED

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
                self._write_telemetry(
                    iteration, now, "MERGED", self._eval_score(baseline, after),
                    "", "", obs_tokens, strat_tokens, impl_tokens,
                    impl_result.files_written, diff,
                )
                return IterationOutcome.MERGED
            else:
                self.worktree_mgr.rollback(worktree)
                self._log_iteration(
                    iteration, now, observation, plan, baseline, after,
                    IterationOutcome.ROLLED_BACK,
                    "Merge gate failed — no improvement or regression detected",
                )
                self._write_telemetry(
                    iteration, now, "ROLLED_BACK", self._eval_score(baseline, after),
                    "no improvement", "", obs_tokens, strat_tokens, impl_tokens,
                    impl_result.files_written, diff,
                )
                return IterationOutcome.ROLLED_BACK

        except Exception as e:
            if worktree is not None:
                try:
                    self.worktree_mgr.rollback(worktree)
                except Exception:
                    pass
            # Determine which agent failed based on token accumulation
            if strat_tokens == (0, 0, 0.0) and obs_tokens != (0, 0, 0.0):
                failing_agent = "strategist"
            elif impl_tokens == (0, 0, 0.0) and strat_tokens != (0, 0, 0.0):
                failing_agent = "implementer"
            elif obs_tokens == (0, 0, 0.0):
                failing_agent = "observer"
            else:
                failing_agent = "unknown"
            failure_msg = f"[{failing_agent}] {e}"
            self._log_iteration(
                iteration,
                now,
                locals().get("observation"),
                locals().get("plan"),
                locals().get("baseline"),
                locals().get("baseline"),
                IterationOutcome.ABANDONED,
                f"Exception: {failure_msg}",
            )
            self._write_telemetry(
                iteration, now, "ABANDONED", 0.0,
                failure_msg, "", obs_tokens, strat_tokens, impl_tokens, (), "",
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
        blocked = set(self.config.sandbox_blocked_paths)
        for py_file in sorted(target_dir.rglob("*.py")):
            relative = py_file.relative_to(self.repo_root)
            rel_str = str(relative)
            # Skip files matching blocked paths
            if any(rel_str == bp or rel_str.startswith(bp.rstrip("/") + "/") for bp in blocked):
                continue
            try:
                content = py_file.read_text()
                # Skip very large files and __pycache__
                if len(content) < 10_000 and "__pycache__" not in str(py_file):
                    files[rel_str] = content
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

    def _eval_score(self, before: ScoreboardSnapshot, after: ScoreboardSnapshot) -> float:
        """Compute the net improvement score (sum of dimension deltas)."""
        total = 0.0
        for ad in after.dimensions:
            bd = before.get(ad.name)
            if bd:
                total += ad.value - bd.value
        return total

    def _describe_improvement(self, before: ScoreboardSnapshot, after: ScoreboardSnapshot) -> str:
        parts = []
        for ad in after.dimensions:
            bd = before.get(ad.name)
            if bd and ad.value > bd.value:
                delta = ad.value - bd.value
                parts.append(f"{ad.name} +{delta:.2f}")
        return ", ".join(parts) if parts else "marginal improvement"

    def _read_agent_tokens(self, agent_wrapper: object) -> tuple[int, int, float]:
        """Read accumulated tokens from an agent wrapper. Returns (in, out, cost)."""
        from ouroboros.agents.base import BaseAgent
        agent = getattr(agent_wrapper, "agent", None)
        if not isinstance(agent, BaseAgent):
            return 0, 0, 0.0
        input_t = agent.total_input_tokens
        output_t = agent.total_output_tokens
        cost = 0.0
        if input_t or output_t:
            # Rough cost estimate: $3/M input, $15/M output for Opus; $3/M, $15/M for Sonnet
            cost = (input_t * 3 + output_t * 15) / 1_000_000
        return input_t, output_t, cost

    def _write_telemetry(
        self,
        iteration: int,
        timestamp: str,
        outcome: str,
        eval_score: float,
        failure_reason: str,
        traceback_output: str,
        obs_tokens: tuple[int, int, float],
        strat_tokens: tuple[int, int, float],
        impl_tokens: tuple[int, int, float],
        files_changed: tuple[str, ...],
        git_diff: str,
    ) -> None:
        """Write a telemetry record for this iteration."""
        obs_agent = getattr(self.observer, "agent", None)
        strat_agent = getattr(self.strategist, "agent", None)
        impl_agent = getattr(self.implementer, "agent", None)

        record = TelemetryRecord(
            run_id=f"{timestamp.replace(':', '-').replace('+', '')[:19]}_iter{iteration:03d}",
            iteration=iteration,
            timestamp=timestamp,
            prompt_observer=f"v{self.prompt_store.current_version('observer') or 1}",
            prompt_strategist=f"v{self.prompt_store.current_version('strategist') or 1}",
            prompt_implementer=f"v{self.prompt_store.current_version('implementer') or 1}",
            observer_output=getattr(obs_agent, "last_response_text", "") if obs_agent else "",
            strategist_output=getattr(strat_agent, "last_response_text", "") if strat_agent else "",
            implementer_output=getattr(impl_agent, "last_response_text", "") if impl_agent else "",
            tokens_observer=AgentTokens(input=obs_tokens[0], output=obs_tokens[1], cost_usd=obs_tokens[2]),
            tokens_strategist=AgentTokens(input=strat_tokens[0], output=strat_tokens[1], cost_usd=strat_tokens[2]),
            tokens_implementer=AgentTokens(input=impl_tokens[0], output=impl_tokens[1], cost_usd=impl_tokens[2]),
            files_changed=files_changed,
            git_diff=git_diff,
            eval_score=eval_score,
            outcome=outcome,
            failure_reason=failure_reason,
            traceback_output=traceback_output,
            cost_usd=obs_tokens[2] + strat_tokens[2] + impl_tokens[2],
            input_tokens=obs_tokens[0] + strat_tokens[0] + impl_tokens[0],
            output_tokens=obs_tokens[1] + strat_tokens[1] + impl_tokens[1],
        )
        self.telemetry_writer.write(record)

    def _log_iteration(self, iteration, timestamp, observation, plan, before, after, outcome, reason):
        obs_summary = (
            f"{observation.weakest_dimension} at {observation.current_score:.2f}"
            if observation else "observation failed"
        )
        hypothesis = plan.hypothesis if plan else "planning failed"
        files = tuple(fc.path for fc in plan.file_changes) if plan else ()
        empty_snapshot = ScoreboardSnapshot(iteration=iteration, dimensions=(), timestamp=timestamp)
        self.ledger.append(LedgerEntry(
            iteration=iteration,
            timestamp=timestamp,
            observation_summary=obs_summary,
            hypothesis=hypothesis,
            files_changed=files,
            diff="",
            scoreboard_before=before or empty_snapshot,
            scoreboard_after=after or empty_snapshot,
            outcome=outcome,
            reason=reason,
        ))
