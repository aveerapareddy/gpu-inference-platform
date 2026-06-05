"""SQLite schema for runtime persistence."""

SCHEMA_VERSION = 1

CREATE_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS requests (
        request_id TEXT PRIMARY KEY,
        correlation_id TEXT NOT NULL,
        model TEXT,
        terminal_state TEXT NOT NULL,
        failure_reason TEXT,
        failure_message TEXT,
        batch_id TEXT,
        backend_id TEXT,
        captured_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        terminal_outcome_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS lifecycle_transitions (
        request_id TEXT NOT NULL,
        sequence_num INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        from_state TEXT,
        to_state TEXT,
        timestamp TEXT NOT NULL,
        PRIMARY KEY (request_id, sequence_num)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS scheduler_decisions (
        request_id TEXT NOT NULL,
        sequence_num INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        decision_reason TEXT,
        scheduler_cycle_id TEXT,
        batch_id TEXT,
        timestamp TEXT NOT NULL,
        details_json TEXT NOT NULL,
        PRIMARY KEY (request_id, sequence_num)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS batch_decisions (
        request_id TEXT NOT NULL,
        sequence_num INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        batch_id TEXT,
        decision_reason TEXT,
        timestamp TEXT NOT NULL,
        details_json TEXT NOT NULL,
        PRIMARY KEY (request_id, sequence_num)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS execution_records (
        request_id TEXT PRIMARY KEY,
        record_json TEXT NOT NULL,
        captured_at TEXT NOT NULL,
        source_request_id TEXT,
        replay_id TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS failures (
        failure_id TEXT PRIMARY KEY,
        request_id TEXT NOT NULL,
        failure_type TEXT NOT NULL,
        failure_owner TEXT NOT NULL,
        failure_component TEXT NOT NULL,
        failure_category TEXT NOT NULL,
        failure_reason TEXT NOT NULL,
        failure_state TEXT NOT NULL,
        failure_timestamp TEXT NOT NULL,
        correlation_id TEXT NOT NULL,
        batch_id TEXT,
        backend_id TEXT
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_failures_request_id ON failures(request_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_failures_owner ON failures(failure_owner)
    """,
    """
    CREATE TABLE IF NOT EXISTS replay_executions (
        replay_id TEXT PRIMARY KEY,
        source_request_id TEXT,
        replay_request_id TEXT NOT NULL,
        outcome TEXT NOT NULL,
        terminal_state TEXT NOT NULL,
        failure_reason TEXT,
        failure_message TEXT,
        started_at TEXT NOT NULL,
        completed_at TEXT NOT NULL,
        replay_events_json TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_replay_source_request ON replay_executions(source_request_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS replay_comparisons (
        comparison_id TEXT PRIMARY KEY,
        original_request_id TEXT NOT NULL,
        replay_request_id TEXT NOT NULL,
        generated_at TEXT NOT NULL,
        terminal_state_match INTEGER NOT NULL,
        matches INTEGER NOT NULL,
        differences_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trace_summaries (
        request_id TEXT PRIMARY KEY,
        correlation_id TEXT NOT NULL,
        event_count INTEGER NOT NULL,
        failure_count INTEGER NOT NULL,
        stage_durations_json TEXT NOT NULL,
        span_metadata_json TEXT NOT NULL,
        captured_at TEXT NOT NULL
    )
    """,
)
