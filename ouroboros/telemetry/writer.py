"""Append-only telemetry writer — serializes records to markdown + index."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from ouroboros.telemetry.types import TelemetryRecord


class TelemetryWriter:
    """Write telemetry records to .ouroboros/archive/ as markdown files."""

    def __init__(self, archive_dir: Path) -> None:
        self.archive_dir = archive_dir

    def write(self, record: TelemetryRecord) -> Path:
        """Serialize a TelemetryRecord to markdown and append to index."""
        self.archive_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{record.run_id}.md"
        filepath = self.archive_dir / filename
        frontmatter = record.to_frontmatter()
        body = record.to_markdown_body()
        content = f"---\n{yaml.dump(frontmatter, default_flow_style=False)}---\n\n{body}\n"
        filepath.write_text(content)

        index_path = self.archive_dir / "index.jsonl"
        with open(index_path, "a") as f:
            f.write(json.dumps(frontmatter) + "\n")

        return filepath
