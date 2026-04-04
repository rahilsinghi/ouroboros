"""Versioned prompt storage with atomic symlink swaps."""
from __future__ import annotations

import os
import re
from pathlib import Path

import yaml


class PromptStore:
    """Manage versioned prompt files for each agent."""

    def __init__(self, prompts_dir: Path, defaults: dict[str, str]) -> None:
        self.prompts_dir = prompts_dir
        self.defaults = defaults

    def initialize(self) -> None:
        """Write v1.md and current.md for each agent from defaults (first run)."""
        for agent, content in self.defaults.items():
            agent_dir = self.prompts_dir / agent
            agent_dir.mkdir(parents=True, exist_ok=True)
            v1_path = agent_dir / "v1.md"
            current_path = agent_dir / "current.md"
            if not v1_path.exists():
                frontmatter = {
                    "version": 1,
                    "parent": 0,
                    "created": "",
                    "mutation_reason": "initial baseline",
                    "tournament_score": 0.0,
                    "baseline_score": 0.0,
                    "promoted": True,
                }
                v1_path.write_text(
                    f"---\n{yaml.dump(frontmatter, default_flow_style=False)}---\n\n{content}\n"
                )
            if not current_path.exists():
                current_path.write_text(content + "\n")

    def load(self, agent: str) -> str:
        """Load the current prompt for an agent. Falls back to hardcoded default."""
        current_path = self.prompts_dir / agent / "current.md"
        if current_path.exists():
            return current_path.read_text().strip()
        return self.defaults.get(agent, "")

    def current_version(self, agent: str) -> int:
        """Return the highest version number for an agent."""
        agent_dir = self.prompts_dir / agent
        if not agent_dir.exists():
            return 0
        versions = []
        for f in agent_dir.iterdir():
            match = re.match(r"v(\d+)\.md$", f.name)
            if match:
                versions.append(int(match.group(1)))
        return max(versions) if versions else 0

    def write_version(
        self,
        agent: str,
        content: str,
        mutation_reason: str,
    ) -> int:
        """Write a new prompt version file. Returns the version number."""
        agent_dir = self.prompts_dir / agent
        agent_dir.mkdir(parents=True, exist_ok=True)
        version = self.current_version(agent) + 1
        frontmatter = {
            "version": version,
            "parent": version - 1,
            "created": "",
            "mutation_reason": mutation_reason,
            "tournament_score": 0.0,
            "baseline_score": 0.0,
            "promoted": False,
        }
        path = agent_dir / f"v{version}.md"
        path.write_text(
            f"---\n{yaml.dump(frontmatter, default_flow_style=False)}---\n\n{content}\n"
        )
        return version

    def promote(
        self,
        agent: str,
        version: int,
        tournament_score: float,
        baseline_score: float,
    ) -> None:
        """Promote a version to current via atomic file swap."""
        agent_dir = self.prompts_dir / agent
        version_path = agent_dir / f"v{version}.md"

        raw = version_path.read_text()
        parts = raw.split("---", 2)
        content = parts[2].strip() if len(parts) >= 3 else raw.strip()

        current_path = agent_dir / "current.md"
        tmp_path = agent_dir / "current_tmp.md"
        tmp_path.write_text(content)
        os.replace(str(tmp_path), str(current_path))

        if len(parts) >= 3:
            fm = yaml.safe_load(parts[1])
            fm["promoted"] = True
            fm["tournament_score"] = tournament_score
            fm["baseline_score"] = baseline_score
            version_path.write_text(
                f"---\n{yaml.dump(fm, default_flow_style=False)}---\n\n{content}\n"
            )

    def token_count(self, agent: str, version: int) -> int:
        """Count tokens (words) in a prompt version."""
        path = self.prompts_dir / agent / f"v{version}.md"
        if not path.exists():
            return 0
        raw = path.read_text()
        parts = raw.split("---", 2)
        content = parts[2].strip() if len(parts) >= 3 else raw.strip()
        return len(content.split())
