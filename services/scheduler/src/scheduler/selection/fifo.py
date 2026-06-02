"""FIFO candidate selection. No batching or priority policies."""

from __future__ import annotations

from uuid import UUID

from scheduler.models.decision import SchedulingCandidate, SchedulingDecision


class FifoSelector:
    """Select head-of-queue candidates up to max_candidate_requests."""

    def evaluate(
        self,
        candidates: list[SchedulingCandidate],
        *,
        max_candidate_requests: int,
    ) -> tuple[list[SchedulingDecision], list[UUID], list[UUID]]:
        decisions: list[SchedulingDecision] = []
        selected: list[UUID] = []
        skipped: list[UUID] = []

        for index, candidate in enumerate(candidates):
            if index < max_candidate_requests:
                reason = "fifo_selected"
                decisions.append(
                    SchedulingDecision(
                        request_id=candidate.request_id,
                        correlation_id=candidate.correlation_id,
                        selected=True,
                        decision_reason=reason,
                        queue_position=candidate.queue_position,
                    )
                )
                selected.append(candidate.request_id)
            else:
                reason = "max_candidates_reached"
                decisions.append(
                    SchedulingDecision(
                        request_id=candidate.request_id,
                        correlation_id=candidate.correlation_id,
                        selected=False,
                        decision_reason=reason,
                        queue_position=candidate.queue_position,
                    )
                )
                skipped.append(candidate.request_id)

        return decisions, selected, skipped
