"""Sandboxed command execution with allowlist enforcement."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ouroboros.config import OuroborosConfig


class CommandBlocked(Exception):
    pass


@dataclass(frozen=True)
class ExecutionResult:
    command: str
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


class SandboxExecutor:
    def __init__(self, config: OuroborosConfig) -> None:
        self.allowed_commands = config.sandbox_allowed_commands
        self.blocked_paths = config.sandbox_blocked_paths
        self.default_timeout = config.sandbox_timeout_seconds

    def run(
        self,
        command: str,
        cwd: str,
        timeout_override: int | None = None,
    ) -> ExecutionResult:
        if not self._is_allowed(command):
            raise CommandBlocked(
                f"Command '{command}' not in allowlist: {self.allowed_commands}"
            )
        timeout = timeout_override or self.default_timeout
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return ExecutionResult(
                command=command,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                command=command,
                returncode=-1,
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                timed_out=True,
            )

    def is_path_blocked(self, path: str) -> bool:
        return any(path.startswith(blocked) for blocked in self.blocked_paths)

    def _is_allowed(self, command: str) -> bool:
        return any(command.startswith(allowed) for allowed in self.allowed_commands)
