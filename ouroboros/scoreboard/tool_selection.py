"""Tool selection accuracy benchmark dimension."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ouroboros.types import DimensionScore


@dataclass(frozen=True)
class RoutingChallenge:
    prompt: str
    expected_tool: str
    distractors: tuple[str, ...]
    category: str


class ToolSelectionScorer:
    def __init__(self, challenges_path: Path) -> None:
        self.challenges = self._load(challenges_path)

    def score(self, results: dict[str, str]) -> DimensionScore:
        if not self.challenges:
            return DimensionScore(name="tool_selection", value=0.0)
        correct = sum(1 for c in self.challenges if results.get(c.prompt) == c.expected_tool)
        return DimensionScore(name="tool_selection", value=correct / len(self.challenges))

    def _load(self, path: Path) -> list[RoutingChallenge]:
        with open(path) as f:
            raw = json.load(f)
        return [
            RoutingChallenge(
                prompt=entry["prompt"],
                expected_tool=entry["expected_tool"],
                distractors=tuple(entry.get("distractors", [])),
                category=entry.get("category", ""),
            )
            for entry in raw
        ]
