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
        """Parse JSON from LLM response, handling markdown fences and truncation."""
        cleaned = raw.strip()
        # Remove markdown code fences
        fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", cleaned, re.DOTALL)
        if fence_match:
            cleaned = fence_match.group(1).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to repair truncated JSON by closing open strings/brackets
            repaired = cleaned
            # Close any unterminated string
            if repaired.count('"') % 2 != 0:
                repaired += '"'
            # Balance brackets
            open_braces = repaired.count("{") - repaired.count("}")
            open_brackets = repaired.count("[") - repaired.count("]")
            repaired += "]" * max(0, open_brackets)
            repaired += "}" * max(0, open_braces)
            return json.loads(repaired)

    def call_with_json_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 8192,
    ) -> dict:
        """Call LLM and parse JSON response, retrying once on parse failure."""
        response = self.call(system_prompt, user_prompt, max_tokens=max_tokens)
        try:
            return self.parse_json(response.text)
        except json.JSONDecodeError as first_error:
            retry_prompt = (
                f"Your previous response was invalid JSON. Error: {first_error}\n\n"
                f"Original request:\n{user_prompt}\n\n"
                "Please respond with ONLY the JSON object, no prose or markdown."
            )
            retry_response = self.call(system_prompt, retry_prompt, max_tokens=max_tokens)
            return self.parse_json(retry_response.text)
