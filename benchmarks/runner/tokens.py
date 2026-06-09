"""Token estimation for benchmark workloads. Owner: benchmarks.runner."""

from __future__ import annotations

ESTIMATION_METHOD = "chars_div_4"


def estimate_input_tokens(text: str) -> int:
    """Estimate input tokens using chars/4 heuristic. Marked as estimated, not measured."""
    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, len(stripped) // 4)
