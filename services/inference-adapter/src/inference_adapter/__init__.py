"""Inference adapter service. Session 10 — backend abstraction; no model execution."""

from inference_adapter.application import InferenceAdapterApplication, create_application
from inference_adapter.backend.contract import InferenceBackend
from inference_adapter.backend.failures import (
    BackendInternalFailure,
    BackendMisconfigured,
    BackendRejected,
    BackendTimeout,
    BackendUnavailable,
)
from inference_adapter.backend.models import (
    BackendMetadata,
    BatchSubmitResult,
    CancelRequestResult,
    HealthCheckResult,
    RequestExecutionStatus,
    RequestStatusResult,
)
from inference_adapter.backend.state import BackendState
from inference_adapter.backends.mock import MockInferenceBackend
from inference_adapter.config import Settings, get_settings
from inference_adapter.registry.registry import BackendRegistry, RegisteredBackend

__version__ = "0.1.0"

__all__ = [
    "BackendInternalFailure",
    "BackendMetadata",
    "BackendMisconfigured",
    "BackendRegistry",
    "BackendRejected",
    "BackendState",
    "BackendTimeout",
    "BackendUnavailable",
    "BatchSubmitResult",
    "CancelRequestResult",
    "HealthCheckResult",
    "InferenceAdapterApplication",
    "InferenceBackend",
    "MockInferenceBackend",
    "RegisteredBackend",
    "RequestExecutionStatus",
    "RequestStatusResult",
    "Settings",
    "create_application",
    "get_settings",
]
