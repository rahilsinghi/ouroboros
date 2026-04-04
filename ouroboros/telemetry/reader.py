"""Telemetry reader — query interface over the archive index."""
from __future__ import annotations

import json
from pathlib import Path


class TelemetryReader:
    """Read and query telemetry records from the archive."""

    def __init__(self, archive_dir: Path) -> None:
        self.archive_dir = archive_dir

    def _load_index(self) -> list[dict]:
        """Load all entries from index.jsonl."""
        index_path = self.archive_dir / "index.jsonl"
        if not index_path.exists():
            return []
        entries = []
        for line in index_path.read_text().splitlines():
            line = line.strip()
            if line:
                entries.append(json.loads(line))
        return entries

    def get_failures(
        self,
        prompt_version: str | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """Return lowest-scoring iterations, sorted by eval_score ascending."""
        entries = self._load_index()
        if prompt_version is not None:
            entries = [
                e for e in entries
                if e.get("prompt_implementer") == prompt_version
                or e.get("prompt_observer") == prompt_version
                or e.get("prompt_strategist") == prompt_version
            ]
        entries.sort(key=lambda e: e.get("eval_score", 0.0))
        return entries[:limit]

    def get_by_prompt_version(self, agent: str, version: str) -> list[dict]:
        """All iterations that used a specific prompt version for the given agent."""
        key = f"prompt_{agent}"
        entries = self._load_index()
        return [e for e in entries if e.get(key) == version]

    def get_summary(self) -> dict:
        """Win rate and counts per implementer prompt version."""
        entries = self._load_index()
        summary: dict[str, dict] = {}
        for e in entries:
            version = e.get("prompt_implementer", "unknown")
            if version not in summary:
                summary[version] = {"total": 0, "merged": 0, "abandoned": 0, "avg_score": 0.0}
            summary[version]["total"] += 1
            if e.get("outcome") == "MERGED":
                summary[version]["merged"] += 1
            elif e.get("outcome") == "ABANDONED":
                summary[version]["abandoned"] += 1
            summary[version]["avg_score"] += e.get("eval_score", 0.0)

        for version, stats in summary.items():
            if stats["total"] > 0:
                stats["avg_score"] /= stats["total"]
                stats["win_rate"] = stats["merged"] / stats["total"]

        return summary

    def read_full_record(self, run_id: str) -> str:
        """Read the full markdown body of a specific record."""
        filepath = self.archive_dir / f"{run_id}.md"
        if not filepath.exists():
            return ""
        content = filepath.read_text()
        parts = content.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
        return content
