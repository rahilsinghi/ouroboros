"""Base agent class with LLM call wrapper."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from anthropic import Anthropic


@dataclass(frozen=True)
class AgentResponse:
    text: str
    input_tokens: int
    output_tokens: int


class BaseAgent:
    def __init__(self, model: str, role: str, timeout_seconds: int) -> None:
        self.model = model
        self.role = role
        self.timeout_seconds = timeout_seconds

    def call(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> AgentResponse:
        """Call the LLM with system and user prompts."""
        client = Anthropic()
        response = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return AgentResponse(
            text=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    def parse_json(self, raw: str) -> dict:
        """Parse JSON from LLM response, handling markdown fences."""
        cleaned = raw.strip()
        # Remove markdown code fences
        fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", cleaned, re.DOTALL)
        if fence_match:
            cleaned = fence_match.group(1).strip()
        return json.loads(cleaned)
