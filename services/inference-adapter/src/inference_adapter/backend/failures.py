"""Backend failure classification. Owner: inference adapter.

Propagation: adapter raises these; scheduler receives result.reason or
re-raises. No retry logic in Session 10.
"""


class BackendUnavailable(Exception):
    category = "backend_unavailable"

    def __init__(self, message: str, *, backend_id: str | None = None) -> None:
        self.message = message
        self.backend_id = backend_id
        super().__init__(message)


class BackendTimeout(Exception):
    category = "backend_timeout"

    def __init__(self, message: str, *, backend_id: str | None = None) -> None:
        self.message = message
        self.backend_id = backend_id
        super().__init__(message)


class BackendRejected(Exception):
    category = "backend_rejected"

    def __init__(
        self,
        message: str,
        *,
        backend_id: str | None = None,
        batch_id: str | None = None,
    ) -> None:
        self.message = message
        self.backend_id = backend_id
        self.batch_id = batch_id
        super().__init__(message)


class BackendMisconfigured(Exception):
    category = "backend_misconfigured"

    def __init__(self, message: str, *, backend_id: str | None = None) -> None:
        self.message = message
        self.backend_id = backend_id
        super().__init__(message)


class BackendInternalFailure(Exception):
    category = "backend_internal_failure"

    def __init__(
        self,
        message: str,
        *,
        backend_id: str | None = None,
        batch_id: str | None = None,
    ) -> None:
        self.message = message
        self.backend_id = backend_id
        self.batch_id = batch_id
        super().__init__(message)
