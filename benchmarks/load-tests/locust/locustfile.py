"""Locust load test for OpenAI-compatible chat completions."""

from __future__ import annotations

import json
import os

from locust import HttpUser, between, task


class ChatCompletionUser(HttpUser):
    wait_time = between(0.1, 0.5)

    def on_start(self) -> None:
        self.api_key = os.environ.get("BENCHMARK_API_KEY", "test-key")
        self.model = os.environ.get("BENCHMARK_MODEL", "demo")
        self.prompt = os.environ.get(
            "BENCHMARK_PROMPT",
            "Summarize GPU batching in one sentence.",
        )
        self.max_tokens = int(os.environ.get("BENCHMARK_MAX_TOKENS", "32"))
        self.stream = os.environ.get("BENCHMARK_STREAM", "false").lower() == "true"

    @task
    def chat_completion(self) -> None:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": self.prompt}],
            "max_tokens": self.max_tokens,
            "stream": self.stream,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        self.client.post(
            "/v1/chat/completions",
            data=json.dumps(payload),
            headers=headers,
            name="chat_completions",
        )
