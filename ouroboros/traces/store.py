"""Persistent trace storage in JSONL format."""
from __future__ import annotations

import json
from pathlib import Path

from ouroboros.types import TraceEvent


class TraceStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def write_events(self, run_id: str, events: list[TraceEvent]) -> Path:
        run_dir = self.base_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        trace_file = run_dir / "trace.jsonl"
        with open(trace_file, "a") as f:
            for event in events:
                f.write(event.to_jsonl_line() + "\n")
        return trace_file

    def read_events(self, run_id: str) -> list[TraceEvent]:
        trace_file = self.base_dir / run_id / "trace.jsonl"
        if not trace_file.exists():
            return []
        events: list[TraceEvent] = []
        with open(trace_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                raw = json.loads(line)
                event_type = raw.pop("event_type")
                timestamp = raw.pop("timestamp")
                events.append(TraceEvent(event_type=event_type, timestamp=timestamp, data=raw))
        return events

    def list_runs(self) -> list[str]:
        if not self.base_dir.exists():
            return []
        return sorted(
            d.name
            for d in self.base_dir.iterdir()
            if d.is_dir() and (d / "trace.jsonl").exists()
        )
