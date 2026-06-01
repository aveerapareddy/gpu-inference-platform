"""Gateway request lifecycle context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from common_schemas.inference_request import InferenceRequest, RequestContext
from common_schemas.states import RequestState
from control_plane.registry.models import RegisteredRequest
from gpu_inference_observability.tracing import TraceContext

from api_gateway.config import Settings


@dataclass(frozen=True, slots=True)
class GatewayRequestContext:
    """Validated request state attached for the gateway lifecycle.

    correlation_id: client-supplied or generated; equals trace_id unless
    X-Correlation-Id is provided.
    received_timestamp: same instant as RequestContext.arrival_time.
    requested_model: model id from client before registry resolution.
    """

    request_context: RequestContext
    inference_request: InferenceRequest
    correlation_id: str
    received_timestamp: datetime
    requested_model: str
    trace: TraceContext
    lifecycle_state: RequestState
    registered: RegisteredRequest | None = None

    @property
    def request_id(self) -> UUID:
        return self.request_context.request_id


def build_request_context(
    *,
    inference_request: InferenceRequest,
    settings: Settings,
    correlation_id: str,
    received_at: datetime | None = None,
) -> GatewayRequestContext:
    received = received_at or datetime.now(timezone.utc)
    trace = TraceContext.new_trace(inference_request.request_id)
    effective_correlation = correlation_id or trace.trace_id

    request_context = RequestContext(
        request_id=inference_request.request_id,
        trace_id=effective_correlation,
        span_id=trace.span_id,
        arrival_time=received,
        model=inference_request.model,
        stream=inference_request.stream,
        gateway_instance_id=settings.gateway_instance_id,
    )

    return GatewayRequestContext(
        request_context=request_context,
        inference_request=inference_request,
        correlation_id=effective_correlation,
        received_timestamp=received,
        requested_model=inference_request.model,
        trace=trace,
        lifecycle_state=RequestState.VALIDATED,
    )
