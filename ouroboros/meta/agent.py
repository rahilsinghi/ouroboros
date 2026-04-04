"""Meta-Agent — outer loop that evolves agent prompts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ouroboros.agents.base import BaseAgent
from ouroboros.meta.benchmark_gen import BenchmarkGenerator, load_benchmark_tasks
from ouroboros.meta.prompt_store import PromptStore
from ouroboros.meta.tournament import Tournament  # noqa: F401
from ouroboros.telemetry.reader import TelemetryReader


@dataclass(frozen=True)
class MetaResult:
    """Result of a meta-agent cycle."""

    state: str  # Final state: IDLE, PROMOTED, DISCARDED
    agent: str
    reason: str
    old_version: int = 0
    new_version: int = 0
    tournament_score: float = 0.0
    baseline_score: float = 0.0


BLOAT_LIMIT = 1.2


def _check_bloat(parent_tokens: int, mutated_tokens: int) -> tuple[bool, str]:
    """Check if mutation exceeds the bloat limit."""
    if parent_tokens == 0:
        return True, ""
    ratio = mutated_tokens / parent_tokens
    if ratio > BLOAT_LIMIT:
        return False, f"Prompt bloat: {mutated_tokens} tokens vs {parent_tokens} parent ({ratio:.1%})"
    return True, ""


META_SYSTEM_PROMPT = """You are the Meta-Agent in the Ouroboros self-improvement system.

Your job: analyze failed execution traces from inner-loop iterations and mutate agent system prompts
to fix cognitive bottlenecks.

You receive:
1. The current system prompt for a specific agent
2. The 5 worst execution traces (what the agent produced and why it failed)

You must:
1. Identify the failure pattern (what goes wrong repeatedly)
2. Identify the root cause in the prompt (what instruction is missing, ambiguous, or wrong)
3. Produce a MUTATED version of the system prompt that fixes the issue

CRITICAL RULES:
- You must EDIT or REPLACE existing instructions. Do NOT append new rules to the end.
- The mutated prompt must be roughly the same length as the parent prompt.
- Focus on ONE specific fix per mutation — the most impactful bottleneck.

Respond with a JSON object:
{
  "agent": "<agent name>",
  "failure_pattern": "<what goes wrong>",
  "root_cause": "<why the current prompt causes this>",
  "proposed_fix": "<what you changed and why>",
  "mutated_prompt": "<the complete new system prompt>"
}"""


class MetaAgent:
    """Outer loop that evolves agent prompts based on telemetry."""

    def __init__(
        self,
        prompts_dir: Path,
        archive_dir: Path,
        benchmark_dir: Path,
        target_path: Path,
        model: str = "claude-opus-4-6",
        defaults: dict[str, str] | None = None,
        min_records: int = 2,
    ) -> None:
        self.reader = TelemetryReader(archive_dir=archive_dir)
        self.prompt_store = PromptStore(prompts_dir=prompts_dir, defaults=defaults or {})
        self.benchmark_dir = benchmark_dir
        self.target_path = target_path
        self.agent = BaseAgent(model=model, role="meta", timeout_seconds=300)
        self.min_records = min_records

    def run(self, target_agent: str | None = None) -> MetaResult:
        """Run one meta-cycle. Returns the result."""
        summary = self.reader.get_summary()
        if not summary:
            return MetaResult(state="IDLE", agent="", reason="Insufficient telemetry data")

        total_records = sum(s["total"] for s in summary.values())
        if total_records < self.min_records:
            return MetaResult(state="IDLE", agent="", reason="Insufficient telemetry records")

        agent = target_agent or self._select_worst_agent(summary)
        if not agent:
            return MetaResult(state="IDLE", agent="", reason="No agent to optimize")

        current_version = self.prompt_store.current_version(agent)
        version_str = f"v{current_version}" if current_version else "v1"
        failures = self.reader.get_failures(prompt_version=version_str, limit=5)

        if len(failures) < self.min_records:
            return MetaResult(state="IDLE", agent=agent, reason="Insufficient failure data for agent")

        traces = []
        for f in failures:
            body = self.reader.read_full_record(f["run_id"])
            traces.append(f"### {f['run_id']} (score={f.get('eval_score', 0)}, outcome={f.get('outcome')})\n{body}")

        current_prompt = self.prompt_store.load(agent)

        user_prompt = (
            f"## Target Agent: {agent}\n\n"
            f"## Current System Prompt (v{current_version})\n```\n{current_prompt}\n```\n\n"
            f"## 5 Worst Execution Traces\n{'---'.join(traces)}\n\n"
            "Analyze the failures and produce a mutated prompt."
        )
        data = self.agent.call_with_json_retry(
            system_prompt=META_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        mutated_prompt = data.get("mutated_prompt", "")
        if not mutated_prompt:
            return MetaResult(state="DISCARDED", agent=agent, reason="Meta-agent returned empty mutation")

        parent_tokens = len(current_prompt.split())
        mutated_tokens = len(mutated_prompt.split())
        passed, bloat_msg = _check_bloat(parent_tokens, mutated_tokens)
        if not passed:
            retry_prompt = (
                f"Your mutation was {mutated_tokens} tokens but the parent is {parent_tokens} tokens. "
                f"Compress the prompt to stay within 120% of the parent length.\n\n"
                f"Original mutation:\n```\n{mutated_prompt}\n```\n\n"
                "Produce a shorter version. Respond with ONLY JSON."
            )
            data = self.agent.call_with_json_retry(
                system_prompt=META_SYSTEM_PROMPT,
                user_prompt=retry_prompt,
            )
            mutated_prompt = data.get("mutated_prompt", "")
            mutated_tokens = len(mutated_prompt.split())
            passed, bloat_msg = _check_bloat(parent_tokens, mutated_tokens)
            if not passed:
                return MetaResult(state="DISCARDED", agent=agent, reason=bloat_msg)

        new_version = self.prompt_store.write_version(
            agent=agent,
            content=mutated_prompt,
            mutation_reason=data.get("proposed_fix", "meta-mutation"),
        )

        tasks = load_benchmark_tasks(self.benchmark_dir)
        if self.target_path.exists():
            gen = BenchmarkGenerator(target_path=self.target_path)
            tasks.extend(gen.generate_rotating(count=2))

        if not tasks:
            return MetaResult(state="DISCARDED", agent=agent, reason="No benchmark tasks available")

        return MetaResult(
            state="PROMOTED",
            agent=agent,
            reason=data.get("proposed_fix", ""),
            old_version=current_version,
            new_version=new_version,
            tournament_score=0.0,
            baseline_score=0.0,
        )

    def _select_worst_agent(self, summary: dict) -> str:
        """Select the agent with the lowest win rate."""
        agent_stats: dict[str, float] = {}
        for version, stats in summary.items():
            win_rate = stats.get("win_rate", 0.0)
            if "implementer" not in agent_stats or win_rate < agent_stats.get("implementer", 1.0):
                agent_stats["implementer"] = win_rate
        return min(agent_stats, key=agent_stats.get, default="implementer")
