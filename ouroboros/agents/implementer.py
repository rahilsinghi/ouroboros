"""Implementer agent — writes code changes in a sandboxed worktree."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from ouroboros.agents.base import BaseAgent
from ouroboros.sandbox.executor import SandboxExecutor
from ouroboros.types import ChangePlan

IMPLEMENTER_SYSTEM_PROMPT = """You are the Implementer agent in the Ouroboros self-improvement system.

Your job: given a Change Plan, write the actual code changes. You receive a plan and the current
source code of files to modify. You write the complete new content for each file.

You ONLY write code. You do not analyze, question, or evaluate the plan.

Respond with a JSON object:
{
  "files_written": {
    "path/to/file.py": "<complete file content after changes>"
  }
}

IMPORTANT: Write the COMPLETE file content, not just the changed parts.
Only modify files specified in the Change Plan. Do not modify any other files."""


@dataclass(frozen=True)
class ImplementResult:
    success: bool
    files_written: tuple[str, ...]
    error: str = ""


class ImplementerAgent:
    def __init__(self, model: str, executor: SandboxExecutor) -> None:
        self.agent = BaseAgent(model=model, role="implementer", timeout_seconds=300)
        self.executor = executor

    def implement(self, plan: ChangePlan, worktree_path: Path) -> ImplementResult:
        """Write code changes to the worktree based on the plan."""
        # Check for blocked paths before calling LLM
        for fc in plan.file_changes:
            if self.executor.is_path_blocked(fc.path):
                return ImplementResult(
                    success=False,
                    files_written=(),
                    error=f"Blocked path: {fc.path} is in the blocked paths list",
                )

        # Read current file contents
        source_files: dict[str, str] = {}
        for fc in plan.file_changes:
            file_path = worktree_path / fc.path
            if file_path.exists():
                source_files[fc.path] = file_path.read_text()
            else:
                source_files[fc.path] = ""

        user_prompt = self._build_prompt(plan, source_files)
        response = self.agent.call(
            system_prompt=IMPLEMENTER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        data = self.agent.parse_json(response.text)
        files_written = data.get("files_written", {})

        # Validate no blocked paths in response
        for path in files_written:
            if self.executor.is_path_blocked(path):
                return ImplementResult(
                    success=False,
                    files_written=(),
                    error=f"Blocked path in response: {path}",
                )

        # Write files to worktree
        written: list[str] = []
        for path, content in files_written.items():
            file_path = worktree_path / path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
            written.append(path)

        # Stage and commit
        if written:
            subprocess.run(
                ["git", "-C", str(worktree_path), "add"] + [str(worktree_path / w) for w in written],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(worktree_path), "commit", "-m", f"ouroboros: {plan.hypothesis}"],
                check=True,
                capture_output=True,
            )

        return ImplementResult(success=True, files_written=tuple(written))

    def _build_prompt(self, plan: ChangePlan, source_files: dict[str, str]) -> str:
        file_sections = "\n\n".join(
            f"### {path}\n```python\n{content}\n```" if content
            else f"### {path}\n(new file — create from scratch)"
            for path, content in source_files.items()
        )
        changes = "\n".join(
            f"  - {fc.path} ({fc.action}): {fc.description}"
            for fc in plan.file_changes
        )
        return (
            f"## Change Plan\n"
            f"Hypothesis: {plan.hypothesis}\n"
            f"Target: {plan.target_dimension}\n"
            f"Expected impact: {plan.expected_impact}\n\n"
            f"Changes to make:\n{changes}\n\n"
            f"## Current Source Code\n{file_sections}\n\n"
            "Write the complete updated file content for each file."
        )
