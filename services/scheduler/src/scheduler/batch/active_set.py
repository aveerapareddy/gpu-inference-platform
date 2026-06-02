"""Active request set management within batches."""

from __future__ import annotations

from uuid import UUID

from scheduler.batch.models import BatchMember, MemberStatus


class ActiveRequestSet:
    """Tracks active, completed, cancelled, and failed members for one batch."""

    def __init__(self) -> None:
        self._by_id: dict[UUID, BatchMember] = {}

    def add_request(self, member: BatchMember) -> None:
        if member.request_id in self._by_id:
            raise ValueError(f"request already in batch: {member.request_id}")
        self._by_id[member.request_id] = member

    def remove_request(self, request_id: UUID) -> BatchMember | None:
        return self._by_id.pop(request_id, None)

    def replace_request(self, request_id: UUID, member: BatchMember) -> BatchMember | None:
        previous = self._by_id.pop(request_id, None)
        self._by_id[member.request_id] = member
        return previous

    def get(self, request_id: UUID) -> BatchMember | None:
        return self._by_id.get(request_id)

    def list_active_requests(self) -> list[BatchMember]:
        return [m for m in self._by_id.values() if m.status == MemberStatus.ACTIVE]

    def list_by_status(self, status: MemberStatus) -> list[BatchMember]:
        return [m for m in self._by_id.values() if m.status == MemberStatus(status)]

    def all_members(self) -> list[BatchMember]:
        return list(self._by_id.values())

    def active_count(self) -> int:
        return len(self.list_active_requests())

    def set_status(self, request_id: UUID, status: MemberStatus) -> BatchMember | None:
        member = self._by_id.get(request_id)
        if member is None:
            return None
        member.status = status
        return member
