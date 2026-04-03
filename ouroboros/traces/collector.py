"""Collect trace events from claw-code CLI runs."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ouroboros.traces.store import TraceStore
from ouroboros.types import TraceEvent


class TraceCollector:
    def __init__(self, store: TraceStore) -> None:
        self.store = store

    def collect_run(
        self,
        prompt: str,
        cli_command: str,
        stdout: str,
        stderr: str,
        returncode: int,
        duration_ms: int,
        tokens_used: int,
    ) -> str:
        run_id = f"run-{uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        events = [
            TraceEvent(
                event_type="cli_run",
                timestamp=now,
                data={
                    "prompt": prompt,
                    "command": cli_command,
                    "stdout": stdout,
                    "stderr": stderr,
                    "returncode": returncode,
                    "duration_ms": duration_ms,
                    "tokens_used": tokens_used,
                },
            )
        ]
        self.store.write_events(run_id, events)
        return run_id
