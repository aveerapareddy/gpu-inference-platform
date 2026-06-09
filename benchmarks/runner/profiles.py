"""Workload profile definitions. Owner: benchmarks.runner."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PROFILES_DIR = Path(__file__).resolve().parents[1]
DATASETS_DIR = PROFILES_DIR / "datasets"
PROMPTS_PATH = DATASETS_DIR / "prompts.json"


@dataclass(frozen=True, slots=True)
class WorkloadProfile:
    profile_id: str
    prompt_key: str
    max_tokens: int
    stream: bool
    input_size_label: str
    output_size_label: str
    expected_behavior: str


def _load_prompts() -> dict[str, str]:
    if not PROMPTS_PATH.is_file():
        return {
            "short": "Hello",
            "medium": "Explain batching.",
            "long": "Write a long technical overview of inference serving.",
        }
    return json.loads(PROMPTS_PATH.read_text())


SHORT_PROMPT_PROFILE = WorkloadProfile(
    profile_id="short_prompt",
    prompt_key="short",
    max_tokens=32,
    stream=False,
    input_size_label="~10 words",
    output_size_label="<=32 tokens",
    expected_behavior="Fast synchronous completion on mock backend",
)

MEDIUM_PROMPT_PROFILE = WorkloadProfile(
    profile_id="medium_prompt",
    prompt_key="medium",
    max_tokens=128,
    stream=False,
    input_size_label="~80 words",
    output_size_label="<=128 tokens",
    expected_behavior="Moderate prompt with standard completion path",
)

LONG_PROMPT_PROFILE = WorkloadProfile(
    profile_id="long_prompt",
    prompt_key="long",
    max_tokens=256,
    stream=False,
    input_size_label="~400 words",
    output_size_label="<=256 tokens",
    expected_behavior="Longer prompt; exercises admission and batch placement",
)

STREAMING_PROFILE = WorkloadProfile(
    profile_id="streaming",
    prompt_key="short",
    max_tokens=64,
    stream=True,
    input_size_label="~10 words",
    output_size_label="<=64 streamed tokens",
    expected_behavior="Streaming path with TTFT and ITL measurement",
)

MIXED_PROFILE = WorkloadProfile(
    profile_id="mixed",
    prompt_key="medium",
    max_tokens=64,
    stream=False,
    input_size_label="~80 words",
    output_size_label="<=64 tokens",
    expected_behavior="Scenario alternates sync and stream requests",
)

PROFILES: dict[str, WorkloadProfile] = {
    p.profile_id: p
    for p in (
        SHORT_PROMPT_PROFILE,
        MEDIUM_PROMPT_PROFILE,
        LONG_PROMPT_PROFILE,
        STREAMING_PROFILE,
        MIXED_PROFILE,
    )
}


def get_profile(profile_id: str) -> WorkloadProfile:
    profile = PROFILES.get(profile_id)
    if profile is None:
        raise KeyError(f"unknown workload profile: {profile_id}")
    return profile


def prompt_for_profile(profile: WorkloadProfile) -> str:
    prompts = _load_prompts()
    return prompts.get(profile.prompt_key, profile.prompt_key)
