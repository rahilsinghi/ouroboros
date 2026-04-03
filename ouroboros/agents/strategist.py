"""Strategist agent — proposes hypotheses and change plans."""

from __future__ import annotations

from ouroboros.agents.base import BaseAgent
from ouroboros.types import ChangePlan, FileChange, ObservationReport

STRATEGIST_SYSTEM_PROMPT = """You are the Strategist agent in the Ouroboros self-improvement system.

Your job: given an Observation Report identifying the weakest dimension, and the relevant source code,
propose exactly ONE hypothesis for improvement with a specific Change Plan.

You think deeply. You do NOT write code. You produce a plan for the Implementer.

Review the improvement history to avoid repeating failed approaches.

Respond with a JSON object:
{
  "hypothesis": "<clear one-sentence hypothesis>",
  "target_dimension": "<dimension name this targets>",
  "file_changes": [
    {
      "path": "<exact file path>",
      "action": "modify" or "create",
      "description": "<what to change and why, in detail>"
    }
  ],
  "expected_impact": "<expected improvement, e.g., 'tool_selection +10%'>"
}

CRITICAL SAFETY RULES:
- NEVER propose changes to files in the blocked paths list (provided below).
- Only propose changes to files you can see in the source code section.

Be specific in descriptions. The Implementer will use your descriptions to write code.
Reference specific functions, line numbers, and logic."""


class StrategistAgent:
    def __init__(self, model: str = "claude-opus-4-6") -> None:
        self.agent = BaseAgent(model=model, role="strategist", timeout_seconds=180)

    def strategize(
        self,
        observation: ObservationReport,
        source_files: dict[str, str],
        ledger_summary: str,
        blocked_paths: tuple[str, ...] = (),
    ) -> ChangePlan:
        """Propose a change plan based on the observation."""
        user_prompt = self._build_prompt(observation, source_files, ledger_summary, blocked_paths)
        data = self.agent.call_with_json_retry(
            system_prompt=STRATEGIST_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        return ChangePlan(
            hypothesis=data["hypothesis"],
            target_dimension=data["target_dimension"],
            file_changes=tuple(
                FileChange(
                    path=fc["path"],
                    action=fc["action"],
                    description=fc["description"],
                )
                for fc in data["file_changes"]
            ),
            expected_impact=data["expected_impact"],
        )

    def _build_prompt(
        self,
        observation: ObservationReport,
        source_files: dict[str, str],
        ledger_summary: str,
        blocked_paths: tuple[str, ...] = (),
    ) -> str:
        file_sections = "\n\n".join(
            f"### {path}\n```python\n{content}\n```"
            for path, content in source_files.items()
        )
        examples = "\n".join(f"  - {ex}" for ex in observation.failure_examples)
        patterns = "\n".join(f"  - {p}" for p in observation.patterns)
        return (
            f"## Observation Report\n"
            f"Weakest dimension: {observation.weakest_dimension} (score: {observation.current_score:.2f})\n\n"
            f"Failure examples:\n{examples}\n\n"
            f"Patterns:\n{patterns}\n\n"
            f"## Relevant Source Code\n{file_sections}\n\n"
            f"## Previous Attempts\n{ledger_summary}\n\n"
            f"## Blocked Paths (DO NOT MODIFY)\n"
            f"{chr(10).join(f'  - {p}' for p in blocked_paths) if blocked_paths else '  (none)'}\n\n"
            "Propose exactly ONE hypothesis with a specific change plan."
        )
