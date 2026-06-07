#!/usr/bin/env python3
"""Session 18 vLLM validation. Run: python runtime-validation/vllm_validation.py"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
for rel in (
    "packages/common-schemas/src",
    "packages/observability/src",
    "services/api-gateway/src",
    "services/control-plane/src",
    "services/scheduler/src",
    "services/inference-adapter/src",
    "runtime-validation",
):
    path = str(ROOT / rel)
    if path not in sys.path:
        sys.path.insert(0, path)

from common_schemas.states import RequestState
from inference_adapter.backends.vllm import VLLMBackend, VLLMBackendConfig
from inference_adapter.config import Settings as AdapterSettings
from scheduler.config import Settings as SchedSettings

from api_gateway.runtime.orchestrator import RequestPathOrchestrator
from harness import ValidationStack, export_metrics, metric_value, submit_request


MODEL = os.environ.get("VLLM_VALIDATION_MODEL", "demo")


def _success_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": MODEL}]})
        if request.url.path == "/v1/chat/completions":
            body = json.loads(request.content.decode())
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": "generated output"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
                },
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def _model_not_loaded_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "other-model"}]})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def _unavailable_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    return httpx.MockTransport(handler)


def _timeout_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": MODEL}]})
        raise httpx.ReadTimeout("timed out")

    return httpx.MockTransport(handler)


def _vllm_backend(transport: httpx.MockTransport) -> VLLMBackend:
    client = httpx.AsyncClient(base_url="http://vllm.test", transport=transport)
    return VLLMBackend(
        VLLMBackendConfig.from_values(
            backend_id="vllm",
            base_url="http://vllm.test",
            default_model=MODEL,
            supported_models=(MODEL,),
            request_timeout_seconds=1.0,
            health_timeout_seconds=1.0,
        ),
        client=client,
    )


async def _stack_with_backend(backend: VLLMBackend) -> ValidationStack:
    vstack = ValidationStack(
        adapter_settings=AdapterSettings(register_mock_backend=False, default_backend_id="vllm"),
        sched_settings=SchedSettings(default_backend_id="vllm"),
        backend=backend,
    )
    await vstack.startup()
    return vstack


async def scenario_successful_completion() -> None:
    backend = _vllm_backend(_success_transport())
    vstack = await _stack_with_backend(backend)
    submit = submit_request(model=MODEL)
    entry = await vstack.orchestrator.execute_full_path(submit)
    assert entry.state == RequestState.COMPLETED
    assert entry.completion is not None
    assert entry.completion.generated_text == "generated output"
    assert entry.completion.total_tokens == 16
    metrics = export_metrics(vstack.metrics_registry)
    assert metric_value(metrics, "gpu_inference_backend_prompt_tokens_total") >= 12
    assert metric_value(metrics, "gpu_inference_backend_completion_tokens_total") >= 4
    await vstack.shutdown()
    await backend.close()


async def scenario_model_load_failure() -> None:
    backend = _vllm_backend(_model_not_loaded_transport())
    vstack = await _stack_with_backend(backend)
    submit = submit_request(model=MODEL)
    entry = await vstack.orchestrator.execute_full_path(submit)
    assert entry.state == RequestState.FAILED
    await vstack.shutdown()
    await backend.close()


async def scenario_backend_unavailable() -> None:
    backend = _vllm_backend(_unavailable_transport())
    vstack = await _stack_with_backend(backend)
    health = await backend.health_check()
    assert health.state == "unavailable"
    submit = submit_request(model=MODEL)
    entry = await vstack.orchestrator.execute_full_path(submit)
    assert entry.state == RequestState.FAILED
    await vstack.shutdown()
    await backend.close()


async def scenario_timeout_behavior() -> None:
    backend = _vllm_backend(_timeout_transport())
    vstack = await _stack_with_backend(backend)
    submit = submit_request(model=MODEL)
    entry = await vstack.orchestrator.execute_full_path(submit)
    assert entry.state == RequestState.FAILED
    metrics = export_metrics(vstack.metrics_registry)
    assert metric_value(metrics, "gpu_inference_backend_failures_total") >= 1
    await vstack.shutdown()
    await backend.close()


async def main() -> int:
    await scenario_successful_completion()
    await scenario_model_load_failure()
    await scenario_backend_unavailable()
    await scenario_timeout_behavior()
    print("vllm validation: ok")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
