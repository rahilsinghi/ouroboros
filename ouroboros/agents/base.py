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
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.last_response_text = ""

    def call(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> AgentResponse:
        """Call the LLM with system and user prompts."""
        client = Anthropic()
        response = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        agent_response = AgentResponse(
            text=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        self.total_input_tokens += agent_response.input_tokens
        self.total_output_tokens += agent_response.output_tokens
        self.last_response_text = agent_response.text
        return agent_response

    def call_with_json_retry(
        self, system_prompt: str, user_prompt: str, max_tokens: int = 16384
    ) -> dict:
        """Call LLM and parse JSON response, retrying once on failure."""
        response = self.call(system_prompt, user_prompt, max_tokens=max_tokens)
        if not response.text.strip():
            response = self.call(
                system_prompt,
                user_prompt + "\n\nIMPORTANT: You MUST respond with a JSON object. Do not return empty.",
                max_tokens=max_tokens,
            )
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


# Pricing per 1M tokens (input, output)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-6": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (0.80, 4.0),
}

DEFAULT_PRICING = (3.0, 15.0)  # Sonnet as fallback


def tokens_to_usd(input_tokens: int, output_tokens: int, model: str) -> float:
    """Calculate USD cost from token counts and model name."""
    input_rate, output_rate = DEFAULT_PRICING
    for model_prefix, (i_rate, o_rate) in MODEL_PRICING.items():
        if model.startswith(model_prefix):
            input_rate, output_rate = i_rate, o_rate
            break
    return (input_tokens * input_rate / 1_000_000) + (output_tokens * output_rate / 1_000_000)


class CostTracker:
    """Accumulates API costs across calls."""

    def __init__(self, budget_usd: float = 10.0) -> None:
        self.budget_usd = budget_usd
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_usd = 0.0

    def add(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Record a call's token usage. Returns the cost of this call."""
        cost = tokens_to_usd(input_tokens, output_tokens, model)
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_usd += cost
        return cost

    @property
    def over_budget(self) -> bool:
        return self.total_usd > self.budget_usd
